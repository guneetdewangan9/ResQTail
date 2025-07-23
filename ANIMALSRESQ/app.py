from flask import Flask, render_template, request, redirect, session, flash
from flask_mysqldb import MySQL
from flask_mail import Mail, Message
from flask_socketio import SocketIO
from cloudinary_helper import upload_image
from config import Config
import os

app = Flask(__name__)
app.config.from_object(Config)

mysql = MySQL(app)
mail = Mail(app)
socketio = SocketIO(app)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']

        cursor = mysql.connection.cursor()
        cursor.execute("INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s)",
                       (name, email, password, role))
        mysql.connection.commit()
        flash('✅ Registration successful. Please login.')
        return redirect('/login')

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        cursor = mysql.connection.cursor()
        cursor.execute("SELECT id, name, role FROM users WHERE email=%s AND password=%s", (email, password))
        user = cursor.fetchone()

        if user:
            session['user_id'] = user[0]
            session['name'] = user[1]
            session['role'] = user[2]
            return redirect('/dashboard')
        else:
            flash("❌ Invalid credentials. Try again.")
            return redirect('/login')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect('/login')

    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM reports ORDER BY id DESC")
    reports = cursor.fetchall()
    return render_template('dashboard.html', reports=reports, role=session['role'])

@app.route('/report', methods=['GET', 'POST'])
def report():
    if 'user_id' not in session:
        return redirect('/login')

    if request.method == 'POST':
        description = request.form['description']
        lat = request.form['lat']
        lon = request.form['lon']
        image_file = request.files['image']

        try:
            image_url, _ = upload_image(image_file)
        except Exception as e:
            flash(f"❌ Image upload failed: {e}")
            return redirect('/report')

        cursor = mysql.connection.cursor()
        cursor.execute("INSERT INTO reports (user_id, description, image_url, lat, lon, status) VALUES (%s, %s, %s, %s, %s, %s)",
                       (session['user_id'], description, image_url, lat, lon, 'Pending'))
        mysql.connection.commit()

        # Send mail to all volunteers
        cursor.execute("SELECT email FROM users WHERE role='Volunteer'")
        volunteers = cursor.fetchall()
        for v in volunteers:
            send_email(v[0], description, image_url, lat, lon)

        # Emit socket event
        socketio.emit('new_report', {'description': description})

        flash('✅ Report submitted successfully.')
        return redirect('/dashboard')

    return render_template('report_form.html')

@app.route('/mark_cared/<int:report_id>')
def mark_cared(report_id):
    if 'user_id' not in session or session['role'] != 'Volunteer':
        return redirect('/login')

    cursor = mysql.connection.cursor()
    cursor.execute("UPDATE reports SET status='Cared' WHERE id=%s", (report_id,))
    mysql.connection.commit()
    flash('✅ Marked as cared.')
    return redirect('/dashboard')

@app.route('/delete_report/<int:report_id>')
def delete_report(report_id):
    if 'user_id' not in session:
        return redirect('/login')

    cursor = mysql.connection.cursor()
    cursor.execute("SELECT user_id FROM reports WHERE id=%s", (report_id,))
    result = cursor.fetchone()

    if result and result[0] == session['user_id']:
        cursor.execute("DELETE FROM reports WHERE id=%s", (report_id,))
        mysql.connection.commit()
        flash('✅ Report deleted successfully.')
    else:
        flash("❌ You're not authorized to delete this report.")

    return redirect('/dashboard')

def send_email(to, description, image_url, lat, lon):
    try:
        msg = Message("🐾 New Animal Reported!",
                      sender=app.config['MAIL_USERNAME'],
                      recipients=[to])
        msg.body = f"""A new injured animal has been reported.

Description: {description}
Location: https://www.google.com/maps?q={lat},{lon}
Image: {image_url}
"""
        mail.send(msg)
    except Exception as e:
        print(f"❌ Error in send_email: {e}")

if __name__ == '__main__':
    socketio.run(app, debug=True)



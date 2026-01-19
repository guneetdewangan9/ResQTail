from flask import Flask, render_template, request, redirect, session, flash, url_for
from flask_mysqldb import MySQL
from flask_mail import Mail, Message
from flask_socketio import SocketIO
from werkzeug.security import generate_password_hash, check_password_hash 
from cloudinary_helper import upload_image 
from config import Config 
import os
import MySQLdb 

print("--- 1. Imports Completed ---") # DIAGNOSTIC PRINT 1

app = Flask(__name__)
app.config.from_object(Config)

print("--- 2. App Config Applied ---") # DIAGNOSTIC PRINT 2

mysql = MySQL(app)
mail = Mail(app)
socketio = SocketIO(app)

print("--- 3. Extensions Initialized ---") # DIAGNOSTIC PRINT 3

# =======================================================================
# 📩 Helper Function: Send Email
# =======================================================================

def send_email(to, description, image_url, lat, lon):
    try:
        msg = Message("🐾 New Animal Reported!",
                      sender=app.config['MAIL_USERNAME'],
                      recipients=[to])
        
        # CORRECTED Google Maps URL format
        map_link = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}" 
        msg.html = f"""
        <p>A new injured animal has been reported.</p>
        <p><strong>Description:</strong> {description}</p>
        <p><strong>Location:</strong> <a href="{map_link}">View on Google Maps</a></p>
        <p><strong>Image:</strong> <a href="{image_url}">{image_url}</a></p>
        """
        mail.send(msg)
    except Exception as e:
        print(f"❌ Error in send_email: {e}")

# =======================================================================
# 🌐 ROUTES
# =======================================================================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        raw_password = request.form['password']
        role = request.form['role']
        
        hashed_password = generate_password_hash(raw_password, method='pbkdf2:sha256')

        cursor = mysql.connection.cursor()
        try:
            cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
            existing_user = cursor.fetchone()

            if existing_user:
                flash('That email address is already registered. Please use a different one or log in.', 'warning')
                return redirect(url_for('register'))

            cursor.execute("INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s)",
                           (name, email, hashed_password, role)) 
            mysql.connection.commit() 
            flash('✅ Registration successful. Please login.', 'success') 
            return redirect(url_for('login'))
        except MySQLdb.IntegrityError as e:
            
            if "Duplicate entry" in str(e) and "for key 'users.email'" in str(e):
                flash('That email address is already registered. Please use a different one or log in.', 'warning')
            else:
                flash(f'An unexpected database error occurred: {e}', 'danger')
                print(f"Database Integrity Error: {e}")
            mysql.connection.rollback() 
            return redirect(url_for('register'))
        except Exception as e:
            flash(f'An error occurred during registration: {e}', 'danger')
            print(f"General error during registration: {e}")
            mysql.connection.rollback() 
            return redirect(url_for('register'))
        finally:
            cursor.close() 

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        cursor = mysql.connection.cursor()
        try:
            cursor.execute("SELECT id, name, role, password FROM users WHERE email=%s", (email,))
            user_data = cursor.fetchone()

            if user_data:
                user_id, name, role, hashed_password = user_data
                
                if check_password_hash(hashed_password, password):
                    session['user_id'] = user_id
                    session['name'] = name
                    session['role'] = role
                    flash(f'Welcome, {session["name"]}!', 'success')
                    return redirect(url_for('dashboard'))
                else:
                    flash("❌ Invalid credentials. Try again.", 'danger')
                    return redirect(url_for('login'))
            else:
                flash("❌ Invalid credentials. Try again.", 'danger')
                return redirect(url_for('login'))
        except Exception as e:
            flash(f'An error occurred during login: {e}', 'danger')
            print(f"Login error: {e}")
            return redirect(url_for('login'))
        finally:
            cursor.close()

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor()
        # Indices:      0   1        2            3          4    5    6
    cursor.execute("SELECT id, user_id, description, image_url, lat, lon, status FROM reports")
    reports = cursor.fetchall()

        # Use .get() to prevent errors if role is missing from session
    return render_template('dashboard.html', reports=reports, role=session.get('role'))

    cursor = mysql.connection.cursor()
    try:
        cursor.execute("SELECT * FROM reports ORDER BY id DESC")
        reports = cursor.fetchall()
    except Exception as e:
        flash(f'Error fetching reports: {e}', 'danger')
        print(f"Dashboard fetch error: {e}")
        reports = []
    finally:
        cursor.close()

    return render_template('dashboard.html', reports=reports, role=session['role'])

@app.route('/report', methods=['GET', 'POST'])
def report():
    if 'user_id' not in session:
        flash('Please log in to submit a report.', 'info')
        return redirect(url_for('login'))

    if request.method == 'POST':
        description = request.form['description']
        lat = request.form['lat']
        lon = request.form['lon']
        image_file = request.files.get('image') 

        image_url = None
        if image_file and image_file.filename != '': 
            try:
                image_url, _ = upload_image(image_file)
            except Exception as e:
                flash(f"❌ Image upload failed: {e}", 'danger')
                print(f"Image upload error: {e}")
                return redirect(url_for('report'))
        else:
            flash("❌ No image file provided.", 'danger')
            return redirect(url_for('report'))

        cursor = mysql.connection.cursor()
        try:
            cursor.execute("INSERT INTO reports (user_id, description, image_url, lat, lon, status) VALUES (%s, %s, %s, %s, %s, %s)",
                           (session['user_id'], description, image_url, lat, lon, 'Pending'))
            mysql.connection.commit()

            cursor.execute("SELECT email FROM users WHERE role='Volunteer'")
            volunteers = cursor.fetchall()
            for v in volunteers:
                send_email(v[0], description, image_url, lat, lon)

            socketio.emit('new_report', {'description': description})

            flash('✅ Report submitted successfully.', 'success')
            return redirect(url_for('dashboard'))
        except Exception as e:
            flash(f'An error occurred while submitting the report: {e}', 'danger')
            print(f"Report submission error: {e}")
            mysql.connection.rollback()
            return redirect(url_for('report'))
        finally:
            cursor.close()

    return render_template('report_form.html')


@app.route('/mark_cared/<int:report_id>')
def mark_cared(report_id):
    if 'user_id' not in session or session['role'] != 'Volunteer':
        flash("❌ You're not authorized to mark reports as cared.", 'danger')
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor()
    try:
        cursor.execute("UPDATE reports SET status='Cared' WHERE id=%s", (report_id,))
        mysql.connection.commit()
        flash('✅ Marked as cared.', 'success')
    except Exception as e:
        flash(f'An error occurred while marking the report as cared: {e}', 'danger')
        print(f"Mark cared error: {e}")
        mysql.connection.rollback()
    finally:
        cursor.close()
    return redirect(url_for('dashboard'))

@app.route('/delete_report/<int:report_id>')
def delete_report(report_id):
    if 'user_id' not in session:
        flash('Please log in to delete reports.', 'info')
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor()
    try:
        cursor.execute("SELECT user_id FROM reports WHERE id=%s", (report_id,))
        result = cursor.fetchone()

        if result and result[0] == session['user_id']:
            cursor.execute("DELETE FROM reports WHERE id=%s", (report_id,))
            mysql.connection.commit()
            flash('✅ Report deleted successfully.', 'success')
        else:
            flash("❌ You're not authorized to delete this report.", 'danger')
    except Exception as e:
        flash(f'An error occurred while deleting the report: {e}', 'danger')
        print(f"Delete report error: {e}")
        mysql.connection.rollback()
    finally:
        cursor.close()

    return redirect(url_for('dashboard'))
        
if __name__ == '__main__':
    # host='0.0.0.0' is important for cloud deployment
    socketio.run(app, debug=True, host='0.0.0.0', port=8000)



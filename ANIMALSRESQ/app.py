from flask import Flask, render_template, request, redirect, session, flash, url_for
from flask_mysqldb import MySQL
from flask_mail import Mail, Message
from flask_socketio import SocketIO
from werkzeug.security import generate_password_hash, check_password_hash
from cloudinary_helper import upload_image
from config import Config



# Ensure compatibility on Windows


# ======================================================
# 🚀 APP INITIALIZATION
# ======================================================

app = Flask(__name__)
app.config.from_object(Config)

mysql = MySQL(app)
mail = Mail(app)
socketio = SocketIO(app, cors_allowed_origins="*")

print("✅ App & Extensions Initialized Successfully")

# ======================================================
# 📩 HELPER FUNCTION: SEND EMAIL
# ======================================================

def send_email(to, description, image_url, lat, lon):
    try:
        msg = Message(
            subject="🐾 New Animal Reported!",
            sender=app.config['MAIL_USERNAME'],
            recipients=[to]
        )

        map_link = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"

        msg.html = f"""
        <p><strong>A new injured animal has been reported.</strong></p>
        <p><b>Description:</b> {description}</p>
        <p><b>Location:</b> <a href="{map_link}">View on Google Maps</a></p>
        <p><b>Image:</b> <a href="{image_url}">{image_url}</a></p>
        """

        mail.send(msg)

    except Exception as e:
        print(f"❌ Email Error: {e}")

# ======================================================
# 🌐 ROUTES
# ======================================================

@app.route('/')
def index():
    return render_template('index.html')

# ---------------- REGISTER ----------------

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])
        role = request.form['role']

        cursor = mysql.connection.cursor()
        try:
            cursor.execute("SELECT id FROM users WHERE email=%s", (email,))
            if cursor.fetchone():
                flash("⚠️ Email already registered.", "warning")
                return redirect(url_for('register'))

            cursor.execute(
                "INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s)",
                (name, email, password, role)
            )
            mysql.connection.commit()
            flash("✅ Registration successful. Please login.", "success")
            return redirect(url_for('login'))

        except Exception as e:
            mysql.connection.rollback()
            flash(f"❌ Registration error: {e}", "danger")
            print(e)

        finally:
            cursor.close()

    return render_template('register.html')

# ---------------- LOGIN ----------------

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        cursor = mysql.connection.cursor()
        try:
            cursor.execute(
                "SELECT id, name, role, password FROM users WHERE email=%s", (email,)
            )
            user = cursor.fetchone()

            if user and check_password_hash(user[3], password):
                session['user_id'] = user[0]
                session['name'] = user[1]
                session['role'] = user[2]
                flash(f"👋 Welcome, {user[1]}!", "success")
                return redirect(url_for('dashboard'))

            flash("❌ Invalid credentials.", "danger")

        except Exception as e:
            flash(f"❌ Login error: {e}", "danger")
            print(e)

        finally:
            cursor.close()

    return render_template('login.html')

# ---------------- LOGOUT ----------------

@app.route('/logout')
def logout():
    session.clear()
    flash("ℹ️ Logged out successfully.", "info")
    return redirect(url_for('index'))

# ---------------- DASHBOARD ----------------

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor()
    try:
        cursor.execute(
            "SELECT id, user_id, description, image_url, lat, lon, status "
            "FROM reports ORDER BY id DESC"
        )
        reports = cursor.fetchall()

    except Exception as e:
        flash(f"❌ Dashboard error: {e}", "danger")
        print(e)
        reports = []

    finally:
        cursor.close()

    return render_template(
        'dashboard.html',
        reports=reports,
        role=session.get('role')
    )

# ---------------- REPORT ANIMAL ----------------

@app.route('/report', methods=['GET', 'POST'])
def report():
    if 'user_id' not in session:
        flash("Please login first.", "info")
        return redirect(url_for('login'))

    if request.method == 'POST':
        description = request.form['description']
        lat = request.form['lat']
        lon = request.form['lon']
        image_file = request.files.get('image')

        if not image_file or image_file.filename == "":
            flash("❌ Image required.", "danger")
            return redirect(url_for('report'))

        try:
            image_url, _ = upload_image(image_file)
        except Exception as e:
            flash(f"❌ Image upload failed: {e}", "danger")
            return redirect(url_for('report'))

        cursor = mysql.connection.cursor()
        try:
            cursor.execute(
                "INSERT INTO reports (user_id, description, image_url, lat, lon, status) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (session['user_id'], description, image_url, lat, lon, 'Pending')
            )
            mysql.connection.commit()

            cursor.execute("SELECT email FROM users WHERE role='Volunteer'")
            volunteers = cursor.fetchall()

            for v in volunteers:
                send_email(v[0], description, image_url, lat, lon)

            socketio.emit('new_report', {'description': description})

            flash("✅ Report submitted successfully.", "success")
            return redirect(url_for('dashboard'))

        except Exception as e:
            mysql.connection.rollback()
            flash(f"❌ Report error: {e}", "danger")
            print(e)

        finally:
            cursor.close()

    return render_template('report_form.html')

# ---------------- MARK AS CARED ----------------

@app.route('/mark_cared/<int:report_id>')
def mark_cared(report_id):
    if session.get('role') != 'Volunteer':
        flash("❌ Unauthorized.", "danger")
        return redirect(url_for('dashboard'))

    cursor = mysql.connection.cursor()
    try:
        cursor.execute(
            "UPDATE reports SET status='Cared' WHERE id=%s", (report_id,)
        )
        mysql.connection.commit()
        flash("✅ Marked as cared.", "success")

    except Exception as e:
        mysql.connection.rollback()
        flash(f"❌ Error: {e}", "danger")
        print(e)

    finally:
        cursor.close()

    return redirect(url_for('dashboard'))

# ---------------- DELETE REPORT ----------------

@app.route('/delete_report/<int:report_id>')
def delete_report(report_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor()
    try:
        cursor.execute(
            "SELECT user_id FROM reports WHERE id=%s", (report_id,)
        )
        owner = cursor.fetchone()

        if owner and owner[0] == session['user_id']:
            cursor.execute("DELETE FROM reports WHERE id=%s", (report_id,))
            mysql.connection.commit()
            flash("✅ Report deleted.", "success")
        else:
            flash("❌ Not authorized.", "danger")

    except Exception as e:
        mysql.connection.rollback()
        flash(f"❌ Delete error: {e}", "danger")
        print(e)

    finally:
        cursor.close()

    return redirect(url_for('dashboard'))

# ======================================================
# ▶️ RUN APP
# ======================================================

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=8000)







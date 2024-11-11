from flask import Flask, request, redirect, render_template, session, flash, send_file
from db import get_db_connection
from security import hash_password, check_password
from sqlite3 import IntegrityError
import pyotp
import qrcode
from io import BytesIO

app = Flask(__name__)
app.secret_key = 'supersecretkey'

# Register route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = hash_password(request.form['password'])
        email = request.form['email']

        conn = get_db_connection()
        try:
            conn.execute('INSERT INTO users (username, password, email) VALUES (?, ?, ?)',
                         (username, password, email))
            conn.commit()
            flash('Registration successful. Please log in.')
            return redirect('/login')
        except IntegrityError:
            flash('Username or email already exists.')
            return render_template('register.html')
        finally:
            conn.close()
    return render_template('register.html')

# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()

        if user and check_password(password, user['password']):
            session['user_id'] = user['id']
            return redirect('/2fa')
        else:
            flash('Invalid username or password.')
    return render_template('login.html')

# 2FA route with QR code generation
@app.route('/2fa', methods=['GET', 'POST'])
def two_factor_auth():
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    conn.close()

    if user['otp_secret'] is None:
        otp_secret = pyotp.random_base32()
        conn = get_db_connection()
        conn.execute('UPDATE users SET otp_secret = ? WHERE id = ?', (otp_secret, user['id']))
        conn.commit()
        conn.close()
    else:
        otp_secret = user['otp_secret']

    # Handle OTP verification on POST request
    if request.method == 'POST':
        otp = request.form['otp']
        if pyotp.TOTP(otp_secret).verify(otp):
            session['authenticated'] = True
            flash('Two-factor authentication successful.')
            return redirect('/protected_resource')
        else:
            flash('Invalid OTP. Please try again.')

    # Generate QR code for 2FA setup
    otp_uri = pyotp.TOTP(otp_secret).provisioning_uri(name=user['username'], issuer_name="MyApp")
    qr_img = qrcode.make(otp_uri)
    buffer = BytesIO()
    qr_img.save(buffer)
    buffer.seek(0)
    return send_file(buffer, mimetype="image/png")

# Protected resource route
@app.route('/protected_resource')
def protected_resource():
    if 'authenticated' not in session:
        flash('You need to complete two-factor authentication to access this resource.')
        return redirect('/login')
    return "This is a protected resource only accessible to authenticated users."

# Logout route
@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.')
    return redirect('/login')

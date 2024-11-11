from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
import sqlite3
import pyotp
import qrcode
from io import BytesIO

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Güvenlik için secret key


def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn


# Home page - Shows blog posts
@app.route('/')
def index():
    conn = get_db_connection()
    blogs = conn.execute('SELECT * FROM blogs').fetchall()
    conn.close()
    return render_template('index.html', blogs=blogs)


# Add new blog post page
@app.route('/add_blog', methods=['GET', 'POST'])
def add_blog():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']

        conn = get_db_connection()
        conn.execute('INSERT INTO blogs (title, content) VALUES (?, ?)', (title, content))
        conn.commit()
        conn.close()

        flash("Blog post added successfully!")
        return redirect(url_for('index'))
    return render_template('add_blog.html')


# View a specific blog post and its comments
@app.route('/blog/<int:blog_id>')
def blog_page(blog_id):
    conn = get_db_connection()
    blog = conn.execute('SELECT * FROM blogs WHERE id = ?', (blog_id,)).fetchone()
    comments = conn.execute('SELECT * FROM comments WHERE blog_id = ?', (blog_id,)).fetchall()
    conn.close()
    return render_template('blog.html', blog=blog, comments=comments)


# Add comment to a blog post
@app.route('/add_comment/<int:blog_id>', methods=['POST'])
def add_comment(blog_id):
    comment_text = request.form['comment']

    conn = get_db_connection()
    conn.execute('INSERT INTO comments (blog_id, comment_text) VALUES (?, ?)', (blog_id, comment_text))
    conn.commit()
    conn.close()

    flash("Comment added successfully!")
    return redirect(url_for('blog_page', blog_id=blog_id))


# Register page
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']

        conn = get_db_connection()
        existing_user = conn.execute('SELECT * FROM users WHERE username = ? OR email = ?', (username, email)).fetchone()
        if existing_user:
            flash("Username or email already exists. Please try a different one.")
            conn.close()
            return render_template('register.html')

        conn.execute('INSERT INTO users (username, password, email) VALUES (?, ?, ?)', (username, password, email))
        conn.commit()
        conn.close()

        flash("Registration successful! Please log in.")
        return redirect(url_for('login'))
    return render_template('register.html')


# Login page
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password)).fetchone()
        conn.close()

        if user:
            session['user_id'] = user['id']
            return redirect(url_for('two_factor_auth'))
        else:
            flash("Invalid username or password")
    return render_template('login.html')


# 2FA route
@app.route('/2fa', methods=['GET', 'POST'])
def two_factor_auth():
    if 'user_id' not in session:
        return redirect(url_for('login'))

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

    if request.method == 'POST':
        otp = request.form['otp']
        print("Entered OTP:", otp)  # Check the entered OTP
        print("Expected OTP:", pyotp.TOTP(otp_secret).now())  # OTP expected by the server
        if pyotp.TOTP(otp_secret).verify(otp):
            session['authenticated'] = True
            flash("Two-factor authentication successful!")
            return redirect(url_for('index'))
        else:
            flash("Invalid OTP. Please try again.")


    return render_template('2fa.html')


# QR Code Generation Endpoint for 2FA
@app.route('/2fa_qr')
def generate_qr():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    conn.close()

    otp_secret = user['otp_secret']
    otp_uri = pyotp.TOTP(otp_secret).provisioning_uri(name=user['username'], issuer_name="MyApp")
    qr_img = qrcode.make(otp_uri)
    buffer = BytesIO()
    qr_img.save(buffer)
    buffer.seek(0)
    return send_file(buffer, mimetype="image/png")


# Logout
@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.")
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(debug=True)

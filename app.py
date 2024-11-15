from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
import sqlite3
import pyotp
import qrcode
from io import BytesIO
import bcrypt

app = Flask(__name__)
app.secret_key = 'supersecretkey'


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

    if 'user_id' not in session:
        flash("You need to log in to view the blog posts.")
        return render_template('index.html', blogs=None)
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


# QR kod gösteren 2FA sayfası
@app.route('/2fa_qr', methods=['GET', 'POST'])
def two_factor_auth_qr():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    conn.close()

    # QR kod için OTP gizli anahtarını oluştur
    otp_secret = user['otp_secret']
    if otp_secret is None:
        otp_secret = pyotp.random_base32()
        conn = get_db_connection()
        conn.execute('UPDATE users SET otp_secret = ? WHERE id = ?', (otp_secret, user['id']))
        conn.commit()
        conn.close()

    # QR kod URI'sini oluştur
    otp_uri = pyotp.TOTP(otp_secret).provisioning_uri(name=user['username'], issuer_name="MyApp")
    qr_img = qrcode.make(otp_uri)
    buffer = BytesIO()
    qr_img.save(buffer)
    buffer.seek(0)

    # Kullanıcı 'Next' butonuna bastığında doğrulama kodu sayfasına yönlendirilir
    if request.method == 'POST':
        return redirect(url_for('two_factor_auth_code'))

    return render_template('2fa_qr.html', qr_code=buffer)


# Kayıt sayfasında QR kod sayfasına yönlendirme
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password'].encode('utf-8')
        email = request.form['email']

        # Şifreyi hashle
        hashed_pw = bcrypt.hashpw(password, bcrypt.gensalt())

        conn = get_db_connection()
        existing_user = conn.execute('SELECT * FROM users WHERE username = ? OR email = ?', (username, email)).fetchone()
        if existing_user:
            flash("Username or email already exists. Please try a different one.")
            conn.close()
            return render_template('register.html')

        try:
            # Kullanıcıyı veritabanına ekle
            conn.execute("INSERT INTO users (username, password, email) VALUES (?, ?, ?)",
                         (username, hashed_pw, email))
            conn.commit()

            # Kullanıcıyı session'a ekleyerek oturum başlatın
            user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
            session['user_id'] = user['id']  # Kullanıcı oturum açtı olarak ayarlanır

            flash("Registration successful! Please scan the QR code for two-factor authentication.")
            return redirect(url_for('two_factor_auth_qr'))  # Kayıttan sonra QR kodlu 2FA sayfasına yönlendirme

        except sqlite3.IntegrityError:
            flash("Username or email already exists.")
        finally:
            conn.close()

    return render_template('register.html')



# Kod girme işlemi için ikinci 2FA sayfası
@app.route('/2fa_code', methods=['GET', 'POST'])
def two_factor_auth_code():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    conn.close()

    otp_secret = user['otp_secret']

    if request.method == 'POST':
        otp = request.form['otp']
        if pyotp.TOTP(otp_secret).verify(otp, valid_window=1):
            session['authenticated'] = True
            flash("Two-factor authentication successful!")
            return redirect(url_for('index'))
        else:
            flash("Invalid OTP. Please try again.")

    return render_template('2fa_code.html')


# Login sonrası 2FA kod sayfasına yönlendirme
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password'].encode('utf-8')  # Plain password in bytes format

        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()

        if user and bcrypt.checkpw(password, user['password']):
            session['user_id'] = user['id']
            return redirect(url_for('two_factor_auth_code'))  # Giriş sonrası 2FA kod sayfasına yönlendirme
        else:
            flash("Invalid username or password")
    return render_template('login.html')


# QR Code Generation Endpoint for 2FA
# QR kod oluşturma için bir endpoint
@app.route('/generate_qr')
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
    qr_img.save(buffer, format="PNG")
    buffer.seek(0)
    return send_file(buffer, mimetype="image/png")




# Logout
@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.")
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True)

import os
import secrets
from datetime import datetime, timedelta
from urllib.parse import quote

from email_validator import validate_email, EmailNotValidError
from flask import render_template, request, redirect, url_for, flash, session, Blueprint
from werkzeug.security import generate_password_hash, check_password_hash

from auth_utils import generate_activation_token, send_activation_email
from db import get_db_connection
from email_utils import send_email

auth_bp = Blueprint('auth', __name__)

# Email activation + two-factor authentication need a working Gmail app password.
# Off by default so the app runs locally without email; set ENABLE_EMAIL_2FA=true in .env.
EMAIL_2FA = os.getenv('ENABLE_EMAIL_2FA', 'false').lower() == 'true'


def _new_2fa_code():
    return f"{secrets.randbelow(1_000_000):06d}"


@auth_bp.route('/')
def home():
    return render_template('login.html')


@auth_bp.route('/signup')
def signup():
    return render_template('signup.html', email_enabled=EMAIL_2FA)


@auth_bp.route('/activate/<token>')
def activate_account(token):
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE activation_token = ?', (token,)).fetchone()

    if not user:
        conn.close()
        flash("Invalid activation link", "error")
        return redirect(url_for('auth.login'))

    if datetime.now() > datetime.fromisoformat(user['token_expiry']):
        conn.close()
        flash("Activation link has expired", "error")
        return redirect(url_for('auth.login'))

    conn.execute('UPDATE users SET is_active = TRUE, activation_token = NULL WHERE id = ?', (user['id'],))
    conn.commit()
    conn.close()
    flash("Account activated successfully!", "success")
    return redirect(url_for('auth.login'))


@auth_bp.route('/register', methods=['POST', 'GET'])
def register():
    if request.method != 'POST':
        return render_template('signup.html', email_enabled=EMAIL_2FA)

    name = request.form['name']
    user_id = request.form['user_id']
    password = request.form['password']
    password2 = request.form['password2']
    profile = request.form['profile']
    email = None

    if EMAIL_2FA:
        try:
            email = validate_email(request.form.get('email', ''), check_deliverability=True).normalized
        except EmailNotValidError as e:
            flash(f"Invalid email address: {e}", "error")
            return redirect(url_for('auth.signup'))

    if password != password2:
        flash("Passwords do not match", "error")
        return redirect(url_for('auth.signup'))

    conn = get_db_connection()
    existing = conn.execute('SELECT user_id, email FROM users WHERE user_id = ? OR (email IS NOT NULL AND email = ?)',
                            (user_id, email)).fetchone()
    if existing:
        conn.close()
        flash("Email already registered" if email and existing['email'] == email else "User ID already taken", "error")
        return redirect(url_for('auth.signup'))

    hashed_pw = generate_password_hash(password)

    if EMAIL_2FA:
        token = generate_activation_token()
        conn.execute('''
            INSERT INTO users (name, email, user_id, profile, password, is_active, activation_token, token_expiry)
            VALUES (?, ?, ?, ?, ?, FALSE, ?, ?)
        ''', (name, email, user_id, profile, hashed_pw, token, datetime.now() + timedelta(minutes=30)))
        conn.commit()
        conn.close()
        send_activation_email(email, f"{request.host_url}activate/{quote(token)}")
        flash("Registration successful! Check your email to activate your account.", "success")
    else:
        conn.execute('INSERT INTO users (name, user_id, profile, password) VALUES (?, ?, ?, ?)',
                     (name, user_id, profile, hashed_pw))
        conn.commit()
        conn.close()
        flash("Registration successful!", "success")
    return redirect(url_for('auth.login'))


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')

    password = request.form['password']
    user_id = request.form['user_id']

    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE user_id = ?', (user_id,)).fetchone()

    if not user or not check_password_hash(user['password'], password):
        conn.close()
        flash("Invalid user ID or password", "error")
        return redirect(url_for('auth.home'))

    if not user['is_active']:
        conn.close()
        flash("Account not activated. Please check your email.", "error")
        return redirect(url_for('auth.home'))

    if EMAIL_2FA and user['email']:
        code = _new_2fa_code()
        now = datetime.now()
        conn.execute('UPDATE users SET twofa_code = ?, twofa_expiry = ?, last_2fa_sent = ? WHERE id = ?',
                     (code, now + timedelta(minutes=5), now, user['id']))
        conn.commit()
        conn.close()
        send_email(user['email'], "Your 2FA Code",
                   f"<p>Your verification code is: <strong>{code}</strong></p>")
        session['2fa_user_id'] = user['id']
        return redirect(url_for('auth.two_fa'))

    conn.close()
    session['user_id'] = user['id']
    session['profile'] = user['profile']
    return redirect(url_for('auth.main'))


@auth_bp.route('/2fa', methods=['GET', 'POST'])
def two_fa():
    if '2fa_user_id' not in session:
        return redirect(url_for('auth.home'))

    if request.method == 'POST':
        entered_code = request.form['code']
        user_id = session['2fa_user_id']

        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        valid = (user and user['twofa_code'] and secrets.compare_digest(user['twofa_code'], entered_code)
                 and datetime.now() < datetime.fromisoformat(user['twofa_expiry']))
        if valid:
            conn.execute('UPDATE users SET twofa_code = NULL, twofa_expiry = NULL WHERE id = ?', (user_id,))
            conn.commit()
            conn.close()
            session.pop('2fa_user_id')
            session['user_id'] = user_id
            session['profile'] = user['profile']
            return redirect(url_for('auth.main'))
        conn.close()
        flash("Invalid or expired code", "error")

    return render_template('2fa.html')


@auth_bp.route('/resend-2fa')
def resend_2fa():
    if '2fa_user_id' not in session:
        return redirect(url_for('auth.home'))

    user_id = session['2fa_user_id']
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    if not user:
        conn.close()
        flash("Session expired. Please log in again.", "error")
        return redirect(url_for('auth.home'))

    # Rate limit: one code every 30 seconds
    now = datetime.now()
    if user['last_2fa_sent'] and now < datetime.fromisoformat(user['last_2fa_sent']) + timedelta(seconds=30):
        conn.close()
        flash("Please wait before requesting a new code.", "warning")
        return redirect(url_for('auth.two_fa'))

    # Reuse the current code while it is still valid
    if user['twofa_expiry'] and now < datetime.fromisoformat(user['twofa_expiry']):
        code = user['twofa_code']
    else:
        code = _new_2fa_code()
        conn.execute('UPDATE users SET twofa_code = ?, twofa_expiry = ? WHERE id = ?',
                     (code, now + timedelta(minutes=5), user_id))

    send_email(user['email'], "Your 2FA Code", f"<p>Your verification code is: <strong>{code}</strong></p>")
    conn.execute('UPDATE users SET last_2fa_sent = ? WHERE id = ?', (now, user_id))
    conn.commit()
    conn.close()
    flash("A new verification code has been sent to your email.", "success")
    return redirect(url_for('auth.two_fa'))


@auth_bp.route('/main')
def main():
    if 'user_id' not in session:
        return redirect(url_for('auth.home'))
    return render_template('main.html')


@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.home'))

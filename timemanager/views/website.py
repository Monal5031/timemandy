from timemanager import app
from flask import render_template


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')


@app.route('/profile')
def profile():
    return render_template('profile.html')


@app.route('/users')
def users():
    return render_template('users.html')


@app.route('/users/change_password/<user_id>')
def change_password(user_id):
    return render_template('change_password.html')


@app.route('/logout')
def logout():
    return render_template('logout.html')

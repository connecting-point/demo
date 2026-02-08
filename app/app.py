
from flask import Flask, render_template, request, redirect, session, url_for, flash
from werkzeug.utils import secure_filename
import os
import mysql.connector
from datetime import datetime
import random
import string

app = Flask(__name__)
app.secret_key = 'your_secret_key'
UPLOAD_FOLDER = 'app/static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

db_config = {
    'host': 'db',
    'user': 'root',
    'password': 'password',
    'database': 'employee_db'
}

def get_db_connection():
    return mysql.connector.connect(**db_config)

def generate_random_credentials():
    username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    return username, password

@app.route('/')
def home():
    if 'admin' in session:
        return redirect('/admin')
    elif 'employee_id' in session:
        return redirect('/dashboard')
    return redirect('/login')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form['username']
        pw = request.form['password']
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM admin WHERE username=%s AND password=%s", (user, pw))
        result = cursor.fetchone()
        if result:
            session['admin'] = True
            return redirect('/admin')
        cursor.execute("SELECT * FROM employees WHERE username=%s AND password=%s", (user, pw))
        emp = cursor.fetchone()
        cursor.close()
        conn.close()
        if emp:
            session['employee_id'] = emp['id']
            return redirect('/dashboard')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/admin', methods=['GET', 'POST'])
def admin_dashboard():
    if 'admin' not in session:
        return redirect('/login')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    if request.method == 'POST':
        name = request.form['name']
        mobile = request.form['mobile']
        email = request.form['email']
        address = request.form['address']
        aadhaar = request.form['aadhaar']
        aadhaar_photo = request.files['aadhaar_photo']
        filename = secure_filename(aadhaar_photo.filename)
        path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        aadhaar_photo.save(path)
        username, password = generate_random_credentials()
        cursor.execute("""INSERT INTO employees (name, mobile, email, address, aadhaar, aadhaar_photo, username, password)
                         VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                       (name, mobile, email, address, aadhaar, filename, username, password))
        conn.commit()
        flash(f'Employee added. Username: {username}, Password: {password}', 'success')
    cursor.execute("SELECT * FROM employees")
    employees = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('admin.html', employees=employees)

@app.route('/dashboard')
def employee_dashboard():
    if 'employee_id' not in session:
        return redirect('/login')
    return render_template('dashboard.html')

@app.route('/punch', methods=['POST'])
def punch():
    if 'employee_id' not in session:
        return redirect('/login')
    emp_id = session['employee_id']
    photo = request.files['photo']
    filename = secure_filename(photo.filename)
    photo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    latitude = request.form.get('latitude')
    longitude = request.form.get('longitude')
    timestamp = datetime.now()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO attendance (employee_id, photo, latitude, longitude, timestamp) VALUES (%s, %s, %s, %s, %s)",
                   (emp_id, filename, latitude, longitude, timestamp))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect('/dashboard')

if __name__ == '__main__':
    print("✅ Flask server started...")
    app.run(host='0.0.0.0', port=5000)

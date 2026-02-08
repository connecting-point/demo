# -*- coding: utf-8 -*-
from flask import (
    Flask, request, jsonify, session, render_template,
    redirect, url_for, send_file, send_from_directory,
    flash, Response, make_response
)
from flask_session import Session
from werkzeug.utils import secure_filename
from functools import wraps
from markupsafe import escape
# -----------------------------
# Standard libraries
# -----------------------------
import uuid
import socket
try:
    import fcntl
except Exception:
    fcntl = None
import struct
import platform
import os
import csv
import base64
import random

import calendar
import threading
import sqlite3
import smtplib
from datetime import datetime, timedelta
from io import StringIO, BytesIO
from urllib.parse import quote


# -----------------------------
# Third-party libraries
# -----------------------------
import requests
import pandas as pd
from xhtml2pdf import pisa
from dotenv import load_dotenv

# -----------------------------
# Email Handling
# -----------------------------
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from email.mime.application import MIMEApplication  # ✅ Needed for attachments
from email.mime.base import MIMEBase
from email import encoders

# -----------------------------
# PDF Generation (ReportLab)
# -----------------------------
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.lib.units import inch


load_dotenv(dotenv_path="/media/data/vigneshwar/cc/demo/.env")

# =================================================
# Flask setup
# =================================================
app = Flask(__name__)
app.secret_key = 'Adithya@1999'

# Register url_encode filter for WhatsApp message encoding
from urllib.parse import quote_plus
app.jinja_env.filters['url_encode'] = lambda s: quote_plus(str(s)) if s is not None else ''

# Filesystem session
SESSION_FOLDER = os.path.expanduser("~/attendance_sessions")
os.makedirs(SESSION_FOLDER, exist_ok=True)
app.config.update(
    SESSION_TYPE='filesystem',
    SESSION_FILE_DIR=SESSION_FOLDER,
    SESSION_PERMANENT=False,
    SESSION_USE_SIGNER=True,
    SESSION_COOKIE_NAME='attendance_session',
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=False
)
Session(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "employees.db")
MASTER_DB_PATH = os.path.join(BASE_DIR, "master.db")
COMPANY_DB_DIR = os.path.join(BASE_DIR, "companies")
os.makedirs(COMPANY_DB_DIR, exist_ok=True)
ENSURED_EMP_SCHEMA = set()
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static/uploads")
ATTENDANCE_FOLDER = os.path.join(BASE_DIR, "static/attendance_photos")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(ATTENDANCE_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# =================================================
# Telegram + Email config
# =================================================
TELEGRAM_BOT_TOKEN = "8499798540:AAHB-tJLCEZIEuCUzwwxQ6aiDEfsKXZtnyM"
ADMIN_CHAT_IDS = ["1061601577", "1214837092"]

SMTP_HOST = 'smtp.hostinger.com'
SMTP_PORT = 587
SMTP_USER = 'sales@connectingpoint.in'
SMTP_PASSWORD = '4003@xUv'

OTP_COOLDOWN_SECONDS = 60
OTP_EXPIRY_MINUTES = 5

from dotenv import load_dotenv
import os

load_dotenv(dotenv_path="/media/data/vigneshwar/cc/demo/.env")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
MASTER_ADMIN_EMAIL = os.getenv("MASTER_ADMIN_EMAIL", "info@connectingpoint.in")
    
# =================================================
# Helpers
# =================================================
@app.before_request
def make_session_permanent():
    session.permanent = True

def get_db_connection(db_path=None):
    path = db_path or session.get('company_db_path') or DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    if path not in ENSURED_EMP_SCHEMA:
        ensure_employee_location_columns(conn)
        ensure_vehicle_logbook_table(conn)
        ensure_work_tables(conn)
        ENSURED_EMP_SCHEMA.add(path)
    return conn

def get_master_db_connection():
    conn = sqlite3.connect(MASTER_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def ensure_employee_location_columns(conn):
    try:
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(employees)").fetchall()]
        if "office_staff" not in cols:
            conn.execute("ALTER TABLE employees ADD COLUMN office_staff INTEGER DEFAULT 0")
        if "office_lat" not in cols:
            conn.execute("ALTER TABLE employees ADD COLUMN office_lat REAL")
        if "office_lon" not in cols:
            conn.execute("ALTER TABLE employees ADD COLUMN office_lon REAL")
        if "office_radius_m" not in cols:
            conn.execute("ALTER TABLE employees ADD COLUMN office_radius_m REAL DEFAULT 200")
        if "vehicle_log_enabled" not in cols:
            conn.execute("ALTER TABLE employees ADD COLUMN vehicle_log_enabled INTEGER DEFAULT 0")
        if "manager_role" not in cols:
            conn.execute("ALTER TABLE employees ADD COLUMN manager_role INTEGER DEFAULT 0")
        if "shop_manager_role" not in cols:
            conn.execute("ALTER TABLE employees ADD COLUMN shop_manager_role INTEGER DEFAULT 0")
        conn.commit()
    except Exception as e:
        print("⚠️ ensure_employee_location_columns failed:", e)

def ensure_vehicle_logbook_table(conn):
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS vehicle_logbook (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER,
                log_date TEXT,
                vehicle_no TEXT,
                start_km REAL,
                end_km REAL,
                purpose TEXT,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
    except Exception as e:
        print("⚠️ ensure_vehicle_logbook_table failed:", e)

def ensure_work_tables(conn):
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS work_assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                assigned_by INTEGER,
                assigned_to INTEGER,
                customer_name TEXT,
                customer_mobile TEXT,
                customer_address TEXT,
                customer_location TEXT,
                service_type TEXT,
                notes TEXT,
                assign_photo TEXT,
                status TEXT DEFAULT 'assigned',
                assigned_at TEXT DEFAULT CURRENT_TIMESTAMP,
                checkin_time TEXT,
                checkin_lat TEXT,
                checkin_lon TEXT,
                checkout_time TEXT,
                checkout_lat TEXT,
                checkout_lon TEXT,
                checkout_photo TEXT,
                amount REAL
            )
        """)
        conn.commit()
    except Exception as e:
        print("⚠️ ensure_work_tables failed:", e)

def haversine_meters(lat1, lon1, lat2, lon2):
    from math import radians, sin, cos, sqrt, atan2
    r = 6371000.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return r * c

def check_office_location(conn, employee_id, lat, lon):
    row = conn.execute(
        "SELECT office_staff, office_lat, office_lon, office_radius_m FROM employees WHERE id = ?",
        (employee_id,)
    ).fetchone()
    if not row:
        return True, None
    if not row["office_staff"]:
        return True, None
    if row["office_lat"] is None or row["office_lon"] is None:
        return False, "Office location not configured. Contact admin."
    if lat is None or lon is None:
        return False, "Location not captured."
    try:
        dist = haversine_meters(float(lat), float(lon), float(row["office_lat"]), float(row["office_lon"]))
        allowed = float(row["office_radius_m"] or 200)
    except Exception:
        return False, "Location check failed."
    if dist > allowed:
        return False, "You are out of location from office."
    return True, None

def compute_duration(start_ts, end_ts):
    if not start_ts or not end_ts:
        return None
    try:
        start = datetime.fromisoformat(start_ts)
        end = datetime.fromisoformat(end_ts)
        delta = end - start
        total_minutes = int(delta.total_seconds() // 60)
        hours = total_minutes // 60
        minutes = total_minutes % 60
        return f"{hours}h {minutes}m"
    except Exception:
        return None

def get_company_by_code(company_code):
    if not company_code:
        return None
    conn = get_master_db_connection()
    company = conn.execute(
        "SELECT * FROM companies WHERE company_code = ?",
        (company_code,)
    ).fetchone()
    conn.close()
    return company

def get_company_telegram_chat_ids():
    company_id = session.get('company_id')
    company_code = session.get('company_code')
    if not company_id and not company_code:
        return ADMIN_CHAT_IDS
    conn = get_master_db_connection()
    if company_id:
        row = conn.execute(
            "SELECT telegram_chat_ids FROM companies WHERE id = ?",
            (company_id,)
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT telegram_chat_ids FROM companies WHERE company_code = ?",
            (company_code,)
        ).fetchone()
    conn.close()
    if row and row["telegram_chat_ids"]:
        raw = row["telegram_chat_ids"].replace(";", ",")
        ids = [c.strip() for c in raw.split(",") if c.strip()]
        return ids or ADMIN_CHAT_IDS
    return ADMIN_CHAT_IDS

def init_master_db():
    conn = get_master_db_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT NOT NULL,
            company_email TEXT,
            company_phone TEXT,
            company_address TEXT,
            admin_name TEXT,
            admin_email TEXT NOT NULL,
            company_code TEXT NOT NULL UNIQUE,
            db_path TEXT NOT NULL,
            telegram_chat_ids TEXT,
            company_legal_name TEXT,
            gst_number TEXT,
            pan_number TEXT,
            cin_number TEXT,
            website TEXT,
            billing_address TEXT,
            billing_city TEXT,
            billing_state TEXT,
            billing_pincode TEXT,
            contact_person TEXT,
            contact_phone TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Add is_active column for older databases
    try:
        conn.execute("ALTER TABLE companies ADD COLUMN is_active INTEGER DEFAULT 1")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE companies ADD COLUMN telegram_chat_ids TEXT")
    except Exception:
        pass
    for col, ddl in [
        ("company_legal_name", "ALTER TABLE companies ADD COLUMN company_legal_name TEXT"),
        ("gst_number", "ALTER TABLE companies ADD COLUMN gst_number TEXT"),
        ("pan_number", "ALTER TABLE companies ADD COLUMN pan_number TEXT"),
        ("cin_number", "ALTER TABLE companies ADD COLUMN cin_number TEXT"),
        ("website", "ALTER TABLE companies ADD COLUMN website TEXT"),
        ("billing_address", "ALTER TABLE companies ADD COLUMN billing_address TEXT"),
        ("billing_city", "ALTER TABLE companies ADD COLUMN billing_city TEXT"),
        ("billing_state", "ALTER TABLE companies ADD COLUMN billing_state TEXT"),
        ("billing_pincode", "ALTER TABLE companies ADD COLUMN billing_pincode TEXT"),
        ("contact_person", "ALTER TABLE companies ADD COLUMN contact_person TEXT"),
        ("contact_phone", "ALTER TABLE companies ADD COLUMN contact_phone TEXT"),
    ]:
        try:
            conn.execute(ddl)
        except Exception:
            pass
    conn.commit()
    conn.close()

def clone_schema_to_new_db(target_path):
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError("Template DB not found to clone schema.")
    src = sqlite3.connect(DB_PATH)
    dst = sqlite3.connect(target_path)
    try:
        schema_sqls = src.execute(
            "SELECT sql FROM sqlite_master "
            "WHERE type IN ('table','index','trigger','view') AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        for (sql,) in schema_sqls:
            if sql:
                dst.execute(sql)
        dst.commit()
    finally:
        src.close()
        dst.close()

def generate_company_code(length=6):
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(random.choices(alphabet, k=length))

def send_welcome_email(to_email, company_name, company_code):
    subject = "Welcome to 360 Vision - Company Admin Access"
    body = f"""
Hello,

Your company "{company_name}" has been created successfully.

Company Code: {company_code}
Admin Login: Use your email and the company code to request an OTP.

If you did not request this, please contact support.

Regards,
360 Vision Team
"""
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = SMTP_USER
    msg['To'] = to_email
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
            s.starttls()
            s.login(SMTP_USER, SMTP_PASSWORD)
            s.sendmail(SMTP_USER, to_email, msg.as_string())
        return True
    except Exception as e:
        print("Failed to send welcome email:", e)
        return False

# Initialize master DB on startup
init_master_db()

def get_employee_id(username):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM employees WHERE mobile = ?", (username,))
    row = cur.fetchone()
    conn.close()
    return row['id'] if row else None

def get_employee_shift_hours(employee_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT shift_hours FROM employees WHERE id = ?", (employee_id,))
    row = cur.fetchone()
    conn.close()
    return row['shift_hours'] if row and row['shift_hours'] is not None else 8

def save_file(file):
    if file and file.filename:
        filename = datetime.now().strftime("%Y%m%d_%H%M%S_") + secure_filename(file.filename)
        path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(path)
        return filename
    return None

def send_otp_email(to_email, otp):
    subject = "Your Admin OTP Login Code"
    body = f"Your OTP for admin login is: {otp}\nIt will expire in {OTP_EXPIRY_MINUTES} minutes."
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = SMTP_USER
    msg['To'] = to_email
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
            s.starttls()
            s.login(SMTP_USER, SMTP_PASSWORD)
            s.sendmail(SMTP_USER, to_email, msg.as_string())
        return True
    except Exception as e:
        print("Failed to send OTP:", e)
        return False

def send_telegram_message(employee_name, action, timestamp, latitude, longitude):
    """Simple text alert (we also have photo alert in async_send_telegram)."""
    map_link = f"https://www.google.com/maps?q={latitude},{longitude}"
    message = (
        f"👤 *Employee:* {employee_name}\n"
        f"🔘 *Action:* {action.title()}\n"
        f"⏰ *Time:* {timestamp}\n"
        f"📍 [View Location]({map_link})"
    )
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    for chat_id in get_company_telegram_chat_ids():
        try:
            requests.post(url, json={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}, timeout=5)
        except Exception as e:
            print(f"⚠️ Telegram text send failed for {chat_id}: {e}")

def send_attendance_email(to_email, employee_name, action, timestamp, latitude, longitude, photo_path):
    """HTML email with optional photo attachment."""
    subject = f"Attendance {action.title()} Confirmation - {employee_name}"
    map_link = f"https://www.google.com/maps?q={latitude},{longitude}"
    html = f"""
    <html><body style="font-family:Arial,sans-serif;">
      <h2>✅ Attendance {action.title()} Recorded</h2>
      <p><b>Employee:</b> {employee_name}</p>
      <p><b>Time:</b> {timestamp}</p>
      <p><b>Location:</b> <a href="{map_link}">{latitude}, {longitude}</a></p>
      <p>This is your confirmation for today's attendance {action.lower()}.</p>
      <p style="margin-top:10px;">Regards,<br><b>360 Vision – Attendance System</b></p>
      <hr>
      <p style="font-size:12px;color:#888;">Automatic notification – please do not reply.</p>
    </body></html>
    """
    msg = MIMEMultipart("related")
    msg["From"] = f"360 Vision Attendance <{SMTP_USER}>"
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(html, "html"))

    if photo_path and os.path.exists(photo_path):
        with open(photo_path, "rb") as f:
            img = MIMEImage(f.read())
            img.add_header("Content-ID", "<photo>")
            msg.attach(img)

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
            s.starttls()
            s.login(SMTP_USER, SMTP_PASSWORD)
            s.send_message(msg)
        print(f"📧 Sent attendance email to {to_email}")
    except Exception as e:
        print(f"❌ Failed to send attendance email to {to_email}: {e}")
        
def render_pdf_template(template_src, context_dict):
    """Render HTML → PDF (in-memory) using xhtml2pdf."""
    html = render_template(template_src, **context_dict)
    result = BytesIO()
    pdf = pisa.pisaDocument(BytesIO(html.encode("UTF-8")), result)
    if pdf.err:
        raise Exception("PDF generation error")
    result.seek(0)
    return result

def get_mac_address():
    """Return local machine's MAC address (server-side)."""
    try:
        if fcntl is None:
            return 'Unknown'
        for interface in ['eth0', 'enp3s0', 'wlan0']:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                info = fcntl.ioctl(
                    s.fileno(), 0x8927, struct.pack('256s', bytes(interface[:15], 'utf-8'))
                )
                return ':'.join(['%02x' % b for b in info[18:24]])
            except OSError:
                continue
    except Exception:
        pass
    return 'Unknown'

def get_device_info(request):
    """Extract browser and OS info from request headers."""
    try:
        ua = request.headers.get('User-Agent', 'Unknown')
        return ua[:250]  # limit to 250 chars to prevent overflow
    except Exception:
        return 'Unknown'

def log_activity(user_id, mobile, action, request):
    """Insert log entry with IP, MAC, and Device info."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        mac = get_mac_address()
        device_info = get_device_info(request)

        cur.execute("""
            INSERT INTO logs (user_id, mobile, action, ip_address, mac_address, device_info)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, mobile, action, ip, mac, device_info))

        conn.commit()
        conn.close()

        print(f"🪵 Log saved: {mobile} -> {action} ({ip}/{mac}) [{device_info}]")
    except Exception as e:
        print("⚠️ Failed to log activity:", e)

# =================================================
# Payroll core – Intelligent IN/OUT handling & salary calc
# =================================================
def calculate_payroll_records(emp, start_date, end_date):
    conn = get_db_connection()
    employee_id = emp['id']
    per_hour_salary = float(emp.get('per_hour_salary') or 0)
    shift_hours = float(emp.get('shift_hours') or 8)
    week_offs = emp['week_off_days'].split(',') if emp.get('week_off_days') else []
    ot_multiplier = float(emp.get('ot_multiplier') or 1.5)
    ot_enabled = (emp.get('ot_enabled') or 'No').lower() == 'yes'
    emp_in_time = emp.get('in_time') or '09:00'

    date_cursor = datetime.strptime(start_date, "%Y-%m-%d")
    end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
    records = []

    while date_cursor <= end_date_obj:
        day_name = date_cursor.strftime("%A")
        date_str = date_cursor.strftime("%Y-%m-%d")

        # --- Fetch attendance for this day ---
        attendance_rows = conn.execute("""
            SELECT * FROM attendance
            WHERE employee_id = ? AND DATE(timestamp) = ?
            ORDER BY timestamp ASC
        """, (employee_id, date_str)).fetchall()

        # --- Initialize defaults ---
        status = "Absent"
        base_hours = 0
        ot_hours = 0
        salary = 0
        ot_pay = 0
        in_time_display = "-"
        out_time_display = "-"

        # --- Week off (auto pay) ---
        if day_name in week_offs:
            status = "Week Off"
            base_hours = shift_hours
            salary = per_hour_salary * shift_hours

        elif attendance_rows:
            first_in = next((r for r in attendance_rows if r['action'].lower() == 'in'), None)
            last_out = next((r for r in reversed(attendance_rows) if r['action'].lower() == 'out'), None)

            in_time_raw = first_in['timestamp'].split(' ')[1][:5] if first_in else None
            out_time_raw = last_out['timestamp'].split(' ')[1][:5] if last_out else None

            # --- Build display labels ---
            if first_in and last_out:
                in_time_display = in_time_raw
                out_time_display = out_time_raw
            elif first_in and not last_out:
                in_time_display = f"{in_time_raw} (In Only)"
                out_time_display = "No Out"
            elif last_out and not first_in:
                in_time_display = "No In"
                out_time_display = f"{out_time_raw} (Out Only)"
            else:
                in_time_display, out_time_display = "No In", "No Out"

            fmt = "%H:%M"
            worked_hours = 0

            # --- Calculate worked hours safely ---
            try:
                if first_in and last_out:
                    in_dt = datetime.strptime(in_time_raw, fmt)
                    out_dt = datetime.strptime(out_time_raw, fmt)
                    worked_hours = max(0, (out_dt - in_dt).total_seconds() / 3600)
                elif first_in and not last_out:
                    worked_hours = shift_hours / 2
                elif last_out and not first_in:
                    worked_hours = shift_hours / 2

                # --- Late punch logic ---
                emp_in_dt = datetime.strptime(emp_in_time, fmt)
                late_cutoff = emp_in_dt + timedelta(hours=1)
                actual_in = datetime.strptime(in_time_raw, fmt) if in_time_raw else emp_in_dt

                if worked_hours == 0:
                    status = "Absent"
                elif worked_hours >= shift_hours * 0.75:
                    status = "Present"
                elif actual_in > late_cutoff:
                    status = "Half-Day"
                    worked_hours = shift_hours / 2
                else:
                    status = "Half-Day"

                # --- OT calculation ---
                if ot_enabled and worked_hours > shift_hours:
                    ot_hours = round(worked_hours - shift_hours, 2)
                    ot_pay = ot_hours * per_hour_salary * ot_multiplier
                    base_hours = shift_hours
                else:
                    base_hours = min(worked_hours, shift_hours)

                salary = (base_hours * per_hour_salary) + ot_pay

            except Exception as e:
                print(f"[Payroll] Time parsing failed for {date_str}:", e)
                status = "Half-Day"
                base_hours = shift_hours / 2
                salary = base_hours * per_hour_salary

        # --- Append final record ---
        records.append({
            "date": date_str,
            "day": day_name,
            "in_time": in_time_display,
            "out_time": out_time_display,
            "status": status,
            "base_hours": round(base_hours, 2),
            "ot_hours": round(ot_hours, 2),
            "ot_pay": round(ot_pay, 2),
            "salary": round(salary, 2)
        })

        date_cursor += timedelta(days=1)

    conn.close()

    total_salary = round(sum(r['salary'] for r in records), 2)
    total_ot_pay = round(sum(r['ot_pay'] for r in records), 2)

    return records, total_salary, total_ot_pay


# =================================================
# Auth guards
# =================================================
ADMIN_SESSION_FILE = "/tmp/admin_session.lock"

def admin_login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_logged_in'):
            flash("⚠️ Please login as Company Admin", "danger")
            return redirect(url_for('admin_login'))
        if not session.get('company_db_path'):
            flash("⚠️ Company session missing. Please login again.", "danger")
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated

def master_login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('master_admin_logged_in'):
            flash("⚠️ Please login as Master Admin", "danger")
            return redirect(url_for('master_login'))
        return f(*args, **kwargs)
    return decorated

# =================================================
# Routes — Core
# =================================================
@app.route("/")
def index():
    host = request.headers.get('Host', '')
    if 'att.360vision.in' in host:
        return redirect(url_for('admin_login'))  # Admin Panel
    return redirect(url_for('login'))            # Employee Login
    
@app.route('/send-telegram/<int:emp_id>')
@admin_login_required
def send_telegram_message_route(emp_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT name, email, mobile FROM employees WHERE id=?", (emp_id,))
    emp = cur.fetchone()
    conn.close()

    if not emp:
        return jsonify({"status": "error", "message": "Employee not found"}), 404

    msg = f"📢 Reminder for {emp['name']} ({emp['mobile']}) — Please check your attendance or updates."
    try:
        for chat_id in get_company_telegram_chat_ids():
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            requests.post(url, json={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"}, timeout=5)
        flash(f"✅ Telegram message sent for {emp['name']}", "success")
    except Exception as e:
        flash(f"❌ Telegram send failed: {e}", "danger")

    return redirect(request.referrer or url_for('employee_attendance_dashboard'))

@app.route("/export_monthly_report")
@admin_login_required
def export_monthly_report():
    import calendar
    from io import BytesIO

    # --- Parameters ---
    month = int(request.args.get("month", datetime.now().month))
    year = int(request.args.get("year", datetime.now().year))

    SHIFT_START = datetime.strptime("09:00:00", "%H:%M:%S").time()
    SHIFT_END = datetime.strptime("18:00:00", "%H:%M:%S").time()
    HALFDAY_HRS = 4
    LATE_MINS = 30
    

    # --- Date range ---
    start_date = datetime(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    end_date = datetime(year, month, last_day)
    all_dates = [start_date + timedelta(days=i) for i in range(last_day)]

    # --- Database Query ---
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row  # ✅ fetch rows as dict-like
    cur = conn.cursor()
    cur.execute("""
        SELECT 
            e.name AS emp_name,
            a.timestamp AS timestamp,
            a.in_time AS in_time,
            a.out_time AS out_time
        FROM attendance a
        JOIN employees e ON a.employee_id = e.id
        WHERE date(a.timestamp) BETWEEN ? AND ?
        ORDER BY e.name, a.timestamp
    """, (start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")))
    rows = cur.fetchall()
    conn.close()

    if not rows:
        flash("No attendance data for this period.", "warning")
        return redirect(request.referrer or url_for('employee_attendance_dashboard'))

    # ✅ Convert rows → DataFrame
    df = pd.DataFrame([dict(r) for r in rows])

    if "timestamp" not in df.columns:
        return "❌ Missing 'timestamp' column in fetched data.", 500

    df["date"] = pd.to_datetime(df["timestamp"], errors='coerce').dt.date
    df = df.dropna(subset=["date"])

    # --- Process attendance ---
    summary = {}
    for _, r in df.iterrows():
        emp = r["emp_name"]
        if emp not in summary:
            summary[emp] = {d.strftime("%d"): "" for d in all_dates}
        d_str = r["date"].strftime("%d")
        in_t, out_t = r["in_time"], r["out_time"]
        work_h = 0
        if in_t and out_t:
            try:
                t1_str = in_t.split(" ")[1] if " " in in_t else in_t
                t2_str = out_t.split(" ")[1] if " " in out_t else out_t
                t1 = datetime.strptime(t1_str, "%H:%M:%S")
                t2 = datetime.strptime(t2_str, "%H:%M:%S")
                work_h = (t2 - t1).total_seconds() / 3600
            except:
                pass

        status = "A"
        remark = ""

        # Determine status even for partial punches
        if in_t or out_t:
            if work_h >= HALFDAY_HRS:
                status = "P"
            elif 0 < work_h < HALFDAY_HRS:
                status = "H"
            else:
                status = "P"

        # Late check
        if in_t:
            try:
                t_in_str = in_t.split(" ")[1] if " " in in_t else in_t
                t_in = datetime.strptime(t_in_str, "%H:%M:%S").time()
                diff = (datetime.combine(datetime.today(), t_in) -
                        datetime.combine(datetime.today(), SHIFT_START)).total_seconds() / 60
                if LATE_MINS <= diff <= 60:
                    remark += " Late"
            except:
                pass

        # Early check
        if out_t:
            try:
                t_out_str = out_t.split(" ")[1] if " " in out_t else out_t
                t_out = datetime.strptime(t_out_str, "%H:%M:%S").time()
                diff = (datetime.combine(datetime.today(), SHIFT_END) -
                        datetime.combine(datetime.today(), t_out)).total_seconds() / 60
                if EARLY_MINS <= diff <= 60:
                    remark += " Early"
            except:
                pass

        # --- Format times cleanly ---
        def fmt_time(val):
            if not val:
                return ""
            if " " in val:
                val = val.split(" ")[1]
            try:
                return datetime.strptime(val.strip(), "%H:%M:%S").strftime("%H:%M")
            except:
                return val[:5]

        # --- Status with times ---
        if in_t and out_t:
            status += f"\n{fmt_time(in_t)}–{fmt_time(out_t)}{remark}"
        elif in_t:
            status += f"\n{fmt_time(in_t)} In Only{remark}"
        elif out_t:
            status += f"\n{fmt_time(out_t)} Out Only{remark}"
        elif remark:
            status += remark

        summary[emp][d_str] = status.strip()

    # --- Sundays as WO ---
    for emp, days in summary.items():
        for d in all_dates:
            if d.weekday() == 6:
                days[d.strftime("%d")] = "WO"

    # --- Summary Table ---
    report_rows = []
    for idx, (emp, days) in enumerate(sorted(summary.items()), start=1):
        row = {"Emp Code": idx, "Emp Name": emp}
        row.update(days)
        vals = list(days.values())
        row["Total P"] = sum(1 for v in vals if v.startswith("P"))
        row["Total H"] = sum(1 for v in vals if v.startswith("H"))
        row["Total A"] = sum(1 for v in vals if v.startswith("A"))
        row["Total WO"] = sum(1 for v in vals if "WO" in v)
        row["Late"] = sum(1 for v in vals if "Late" in v)
        row["Early"] = sum(1 for v in vals if "Early" in v)
        report_rows.append(row)

    report_df = pd.DataFrame(report_rows)

    # --- Excel Export ---
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        report_df.to_excel(writer, index=False, sheet_name="Monthly Report", startrow=1)
        wb = writer.book
        ws = writer.sheets["Monthly Report"]

        header = f"Monthly Attendance Report - {calendar.month_name[month]} {year}"
        ws.write(0, 0, header)
        ws.set_row(0, 25)
        ws.set_row(1, 25, wb.add_format({"bold": True, "align": "center"}))
        ws.set_column(0, 1, 22)
        ws.set_column(2, len(all_dates) + 8, 15)

        fmt_center = wb.add_format({"align": "center", "valign": "vcenter"})
        fmt_present = wb.add_format({"bg_color": "#C6EFCE", "align": "center"})
        fmt_half = wb.add_format({"bg_color": "#BDD7EE", "align": "center"})
        fmt_absent = wb.add_format({"bg_color": "#FFC7CE", "font_color": "#9C0006", "bold": True, "align": "center"})
        fmt_wo = wb.add_format({"bg_color": "#E7E6E6", "align": "center"})
        fmt_late = wb.add_format({"bg_color": "#FFEB9C", "align": "center"})
        fmt_early = wb.add_format({"bg_color": "#F4B084", "align": "center"})

        # Apply conditional formatting
        for r_idx in range(2, len(report_df) + 2):
            for c_idx in range(2, len(all_dates) + 2):
                val = report_df.iloc[r_idx - 2, c_idx]
                if not isinstance(val, str):
                    continue
                fmt = fmt_wo if "WO" in val else \
                      fmt_absent if val.startswith("A") else \
                      fmt_half if val.startswith("H") else \
                      fmt_early if "Late" in val and "Early" in val else \
                      fmt_late if "Late" in val else \
                      fmt_early if "Early" in val else \
                      fmt_present
                ws.write(r_idx, c_idx, val, fmt)

        footer = f"Generated by 360 Vision Attendance System on {datetime.now():%Y-%m-%d %H:%M:%S}"
        ws.write(len(report_df) + 3, 0, footer)

    output.seek(0)
    return send_file(
        output,
        as_attachment=True,
        download_name=f"Monthly_Report_{year}_{month:02d}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@app.route("/email_monthly_report")
@admin_login_required
def email_monthly_report():
    import calendar
    from io import BytesIO

    month = int(request.args.get("month", datetime.now().month))
    year = int(request.args.get("year", datetime.now().year))
    to_email = request.args.get("to", "").strip()
    cc_param = request.args.get("cc", "").strip()
    cc_list = [email.strip() for email in cc_param.split(",") if email.strip()]

    if not to_email:
        return jsonify({"message": "Missing 'to' email address."}), 400

    # --- Helper: clean time format ---
    def extract_time_str(value):
        if not value:
            return ""
        try:
            if " " in value:  # full timestamp
                return value.split(" ")[1][:5]
            return value[:5]
        except:
            return str(value)

    try:
        SHIFT_START = datetime.strptime("09:00:00", "%H:%M:%S").time()
        SHIFT_END = datetime.strptime("18:00:00", "%H:%M:%S").time()
        HALFDAY_HRS = 4
        LATE_MINS = 30
        

        start_date = datetime(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        end_date = datetime(year, month, last_day)
        all_dates = [start_date + timedelta(days=i) for i in range(last_day)]

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT e.name AS emp_name,
                   a.timestamp,
                   a.in_time,
                   a.out_time
            FROM attendance a
            JOIN employees e ON a.employee_id = e.id
            WHERE date(a.timestamp) BETWEEN ? AND ?
            ORDER BY e.name, a.timestamp
        """, (start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")))

        rows = cur.fetchall()
        columns = [desc[0] for desc in cur.description]
        conn.close()

        if not rows:
            return jsonify({"message": "No data to send."}), 400

        # Convert tuples → dicts
        row_dicts = [dict(zip(columns, r)) for r in rows]
        df = pd.DataFrame(row_dicts)

        if "timestamp" not in df.columns:
            return jsonify({"message": "Excel generation failed: missing 'timestamp' column."}), 400

        df["date"] = pd.to_datetime(df["timestamp"]).dt.date

        summary = {}
        for _, r in df.iterrows():
            emp = r["emp_name"]
            if emp not in summary:
                summary[emp] = {d.strftime("%d"): "" for d in all_dates}
            d_str = r["date"].strftime("%d")
            in_t, out_t = r["in_time"], r["out_time"]
            work_h = 0
            if in_t and out_t:
                try:
                    t1 = datetime.strptime(extract_time_str(in_t), "%H:%M")
                    t2 = datetime.strptime(extract_time_str(out_t), "%H:%M")
                    work_h = (t2 - t1).total_seconds() / 3600
                except:
                    pass

            status = "A" if work_h == 0 else ("H" if work_h < HALFDAY_HRS else "P")
            remark = ""

            # Late check
            if in_t:
                try:
                    t_in = datetime.strptime(extract_time_str(in_t), "%H:%M").time()
                    diff = (datetime.combine(datetime.today(), t_in) - datetime.combine(datetime.today(), SHIFT_START)).total_seconds() / 60
                    if LATE_MINS <= diff <= 60:
                        remark += " Late"
                except:
                    pass

            # Early check
            if out_t:
                try:
                    t_out = datetime.strptime(extract_time_str(out_t), "%H:%M").time()
                    diff = (datetime.combine(datetime.today(), SHIFT_END) - datetime.combine(datetime.today(), t_out)).total_seconds() / 60
                    if EARLY_MINS <= diff <= 60:
                        remark += " Early"
                except:
                    pass

            # Show time in/out or Pending
            if in_t and out_t:
                status += f"\n{extract_time_str(in_t)}–{extract_time_str(out_t)}{remark}"
            elif in_t and not out_t:
                status += f"\n{extract_time_str(in_t)}–(Pending){remark}"
            elif remark:
                status += remark

            summary[emp][d_str] = status.strip()

        # Mark Sundays as WO
        for emp, days in summary.items():
            for d in all_dates:
                if d.weekday() == 6:
                    days[d.strftime("%d")] = "WO"

        # Build final report
        report_rows = []
        for idx, (emp, days) in enumerate(sorted(summary.items()), start=1):
            row = {"Emp Code": idx, "Emp Name": emp}
            row.update(days)
            vals = list(days.values())
            row["Total P"] = sum(1 for v in vals if v.startswith("P"))
            row["Total H"] = sum(1 for v in vals if v.startswith("H"))
            row["Total A"] = sum(1 for v in vals if v.startswith("A"))
            row["Total WO"] = sum(1 for v in vals if "WO" in v)
            row["Late"] = sum(1 for v in vals if "Late" in v)
            row["Early"] = sum(1 for v in vals if "Early" in v)
            report_rows.append(row)

        report_df = pd.DataFrame(report_rows)

        output = BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            report_df.to_excel(writer, index=False, sheet_name="Monthly Report", startrow=1)
            ws = writer.sheets["Monthly Report"]
            ws.write(0, 0, f"Monthly Attendance Report - {calendar.month_name[month]} {year}")
        output.seek(0)

    except Exception as e:
        return jsonify({"message": f"Excel generation failed: {e}"}), 500

    # --- Send Email ---
    sender = SMTP_USER
    subject = f"Monthly Attendance Report – {calendar.month_name[month]} {year}"
    body = f"""Hi Team,

Please find attached the Monthly Attendance Summary for {calendar.month_name[month]} {year}.

Regards,
360 Vision Attendance System
"""

    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = to_email
    if cc_list:
        msg["Cc"] = ", ".join(cc_list)
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    attachment = MIMEApplication(output.read(), _subtype="xlsx")
    attachment.add_header(
        "Content-Disposition",
        "attachment",
        filename=f"Monthly_Report_{year}_{month:02d}.xlsx"
    )
    msg.attach(attachment)

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
            s.starttls()
            s.login(SMTP_USER, SMTP_PASSWORD)
            s.sendmail(sender, [to_email] + cc_list, msg.as_string())
        return jsonify({"message": f"✅ Report emailed successfully to {to_email}"}), 200
    except Exception as e:
        return jsonify({"message": f"❌ Email failed: {str(e)}"}), 500

@app.route('/logs', methods=['GET'])
@admin_login_required
def logs_report():
    search = request.args.get('search', '').strip()
    from_date = request.args.get('from_date', '')
    to_date = request.args.get('to_date', '')
    query = "SELECT * FROM logs WHERE 1=1"
    params = []

    if search:
        query += " AND (mobile LIKE ? OR action LIKE ? OR device_info LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
    if from_date:
        query += " AND date(timestamp) >= ?"
        params.append(from_date)
    if to_date:
        query += " AND date(timestamp) <= ?"
        params.append(to_date)

    query += " ORDER BY timestamp DESC LIMIT 300"

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(query, params)
    logs = cur.fetchall()
    conn.close()

    return render_template("logs_report.html", logs=logs, from_date=from_date, to_date=to_date, search=search)


@app.template_filter('escapejs')
def escapejs_filter(s):
    """Escape string for use in JavaScript"""
    if s is None:
        return ""
    # Escape quotes, backslashes, and newlines
    s = str(s)
    s = s.replace('\\', '\\\\').replace('"', '\\"').replace("'", "\\'")
    s = s.replace('\n', '\\n').replace('\r', '\\r')
    return s
 
@app.route('/email_report_pdf/<int:emp_id>')
@admin_login_required
def email_report_pdf(emp_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM employees WHERE id = ?", (emp_id,))
    emp = cur.fetchone()
    if not emp:
        conn.close()
        flash("Employee not found", "danger")
        return redirect(url_for('employee_attendance_dashboard'))

    emp_dict = dict(emp)
    employee_email = emp_dict.get('email')
    if not employee_email:
        flash("Employee has no email address", "danger")
        return redirect(url_for('employee_attendance_dashboard'))

    # Reuse same data logic as download
    cur.execute("""
        SELECT timestamp, action, in_time, out_time,
               latitude, longitude, photo_path
        FROM attendance WHERE employee_id = ? ORDER BY timestamp DESC
    """, (emp_id,))
    rows = cur.fetchall()
    conn.close()

    records = []
    for r in rows:
        rec = dict(r)
        rec['date'] = r['timestamp'].split(' ')[0]
        rec['time'] = r['timestamp'].split(' ')[1]
        rec['photo_urls'] = []
        if r['photo_path']:
            for p in r['photo_path'].split(','):
                p = p.strip()
                if p.startswith('static/'):
                    p = p.replace('static/', '', 1)
                rec['photo_urls'].append(url_for('static', filename=p))
        records.append(rec)

    pdf_file = render_pdf_template(
        'report_pdf_template.html',
        employee=emp_dict,
        records=records,
        now=datetime.now()
    )

    # ---------- Email ----------
    subject = f"Complete Attendance Report – {emp_dict['name']}"
    body = f"""Hi {emp_dict['name']},

Please find your complete attendance report attached as a PDF.

Regards,
360 Vision Attendance System
"""

    msg = MIMEMultipart()
    msg['From'] = SMTP_USER
    msg['To'] = employee_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    pdf_file.seek(0)
    attachment = MIMEApplication(pdf_file.read(), _subtype='pdf')
    attachment.add_header(
        'Content-Disposition',
        'attachment',
        filename=f"Attendance_Report_{emp_dict['name'].replace(' ', '_')}_{datetime.now():%Y%m%d_%H%M%S}.pdf"
    )
    msg.attach(attachment)

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
            s.starttls()
            s.login(SMTP_USER, SMTP_PASSWORD)
            s.send_message(msg)
        flash(f"Report emailed to {employee_email}", "success")
    except Exception as e:
        flash(f"Email failed: {e}", "danger")

    return redirect(url_for('employee_attendance_dashboard'))
    
@app.route("/export_records")
@admin_login_required
def export_records():
    start = request.args.get("start")
    end = request.args.get("end")
    export_type = request.args.get("type", "excel")

    if not start or not end:
        return "Missing date range", 400

    db_path = os.path.join(os.getcwd(), "employees.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        SELECT 
            e.name AS employee_name,
            e.employee_photo,
            a.in_time, a.out_time, a.timestamp,
            a.latitude, a.longitude,
            a.photo_path, a.subject
        FROM attendance a
        JOIN employees e ON a.employee_id = e.id
        WHERE date(a.timestamp) BETWEEN ? AND ?
        ORDER BY a.timestamp ASC
    """, (start, end))
    rows = cur.fetchall()
    conn.close()

    if not rows:
        return "No attendance data found for this range.", 404

    df = pd.DataFrame(rows)

    # ---------- EXCEL EXPORT ----------
    if export_type == "excel":
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name="Attendance", startrow=1)

            workbook = writer.book
            worksheet = writer.sheets["Attendance"]

            worksheet.write(0, 0, f"Attendance Records ({start} to {end})")
            worksheet.set_row(0, 25)
            worksheet.set_column("A:H", 20)

            # Insert images in Excel
            for idx, r in enumerate(rows):
                row_num = idx + 2  # because of header + title row
                photo_list = []
                if r["photo_path"]:
                    photo_list = [p.strip() for p in r["photo_path"].split(",") if p.strip()]
                if not photo_list:
                    continue

                first_photo = photo_list[0].replace("static/", "static/")
                full_path = os.path.join(os.getcwd(), first_photo)
                if os.path.exists(full_path):
                    try:
                        worksheet.set_row(row_num, 60)
                        worksheet.insert_image(row_num, 8, full_path, {"x_scale": 0.3, "y_scale": 0.3})
                    except Exception as e:
                        print("Image insert failed:", e)

        output.seek(0)
        return send_file(
            output,
            as_attachment=True,
            download_name=f"attendance_{start}_to_{end}.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    # ---------- PDF EXPORT ----------
    elif export_type == "pdf":
        output = BytesIO()
        pdf = canvas.Canvas(output, pagesize=letter)
        width, height = letter

        pdf.setTitle(f"Attendance Report {start} to {end}")
        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawString(50, height - 50, f"Attendance Report: {start} to {end}")

        y = height - 80
        for r in rows:
            pdf.setFont("Helvetica-Bold", 10)
            pdf.drawString(50, y, f"Name: {r['employee_name']}")
            pdf.setFont("Helvetica", 9)
            pdf.drawString(200, y, f"Subject: {r['subject'] or 'N/A'}")
            y -= 15
            pdf.drawString(50, y, f"In: {r['in_time'] or '-'} | Out: {r['out_time'] or '-'} | Date: {r['timestamp'][:10]}")
            y -= 15

            # Add photo
            if r["photo_path"]:
                photos = [p.strip() for p in r["photo_path"].split(",") if p.strip()]
                if photos:
                    photo_path = os.path.join(os.getcwd(), photos[0])
                    if os.path.exists(photo_path):
                        try:
                            pdf.drawImage(ImageReader(photo_path), 400, y - 10, width=1*inch, height=1*inch)
                        except Exception as e:
                            print("PDF image error:", e)
            y -= 70
            if y < 100:
                pdf.showPage()
                y = height - 80
        pdf.save()
        output.seek(0)

        return send_file(
            output,
            as_attachment=True,
            download_name=f"attendance_{start}_to_{end}.pdf",
            mimetype="application/pdf"
        )

    else:
        return "Invalid export type", 400    
    
@app.route('/admin/employee_announcement', methods=['GET', 'POST'])
@admin_login_required
def employee_announcement():
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # --- Fetch employees & teams ---
    cur.execute("SELECT id, name, email, mobile, COALESCE(team, 'General') AS team FROM employees")
    employees = cur.fetchall()
    teams = sorted(set([e['team'] for e in employees if e['team']]))

    # --- Fetch last 10 announcements ---
    cur.execute("""
        SELECT id, subject,
               DATE(sent_at) as sent_date,
               TIME(sent_at) as sent_time
        FROM announcements
        ORDER BY id DESC LIMIT 10
    """)
    recent = cur.fetchall()
    recent_announcements = [
        {
            'id': r['id'],
            'subject': r['subject'],
            'sent_at': f"{r['sent_date']} {r['sent_time']}"
        }
        for r in recent
    ]

    if request.method == 'POST':
        ann_type = request.form.get('announcement_type')
        subject = request.form.get('subject', '').strip()
        message = request.form.get('message', '').strip()
        emp_id = request.form.get('employee_id')
        team_name = request.form.get('team_name')

        # --- Channel flags ---
        send_email = 'send_email' in request.form
        send_whatsapp = 'send_whatsapp' in request.form
        send_facebook = 'send_facebook' in request.form

        if not subject or not message:
            flash("Subject and message are required.", "danger")
            return redirect(url_for('employee_announcement'))

        # --- Save attachment ---
        attachment_path = None
        has_attachment = False
        if 'attachment' in request.files:
            file = request.files['attachment']
            if file and file.filename:
                upload_folder = os.path.join(app.root_path, 'static', 'announcements')
                os.makedirs(upload_folder, exist_ok=True)
                filename = datetime.now().strftime("%Y%m%d_%H%M%S_") + secure_filename(file.filename)
                attachment_path = os.path.join(upload_folder, filename)
                file.save(attachment_path)
                has_attachment = True

        # --- Save announcement to DB ---
        cur.execute("INSERT INTO announcements (subject, message) VALUES (?, ?)", (subject, message))
        ann_id = cur.lastrowid
        conn.commit()

        # --- Determine recipients ---
        recipients = []
        if ann_type == "All Employees":
            recipients = employees
        elif ann_type == "Individual" and emp_id:
            recipients = [e for e in employees if str(e['id']) == emp_id]
        elif ann_type == "Team" and team_name:
            recipients = [e for e in employees if e['team'] == team_name]

        success_email = success_wa = success_fb = 0

        # --- Send via selected channels ---
        for emp in recipients:
            name, email, mobile = emp['name'], emp['email'], emp['mobile']
            clean_mobile = ''.join(filter(str.isdigit, str(mobile or '')))

            # EMAIL
            if send_email and email:
                try:
                    msg = MIMEMultipart()
                    msg['From'] = SMTP_USER
                    msg['To'] = email
                    msg['Subject'] = f"{subject}"
                    body = f"Hi {name},\n\n{message}\n\nBest regards,\n360 Vision HR Team"
                    msg.attach(MIMEText(body, 'plain'))
                    if attachment_path:
                        with open(attachment_path, 'rb') as f:
                            part = MIMEBase('application', 'octet-stream')
                            part.set_payload(f.read())
                        encoders.encode_base64(part)
                        part.add_header('Content-Disposition', f'attachment; filename="{os.path.basename(attachment_path)}"')
                        msg.attach(part)
                    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
                        s.starttls()
                        s.login(SMTP_USER, SMTP_PASSWORD)
                        s.send_message(msg)
                    success_email += 1
                except Exception as e:
                    print(f"Email failed for {email}: {e}")

            # WHATSAPP
            if send_whatsapp and clean_mobile:
                try:
                    text = f"Hi {name}!\n\n*{subject}*\n\n{message}\n\n– 360 Vision HR"
                    encoded = requests.utils.quote(text)
                    wa_url = f"https://wa.me/91{clean_mobile}?text={encoded}"
                    print(f"WhatsApp: {wa_url}")
                    success_wa += 1
                except Exception as e:
                    print(f"WhatsApp failed: {e}")

            # FACEBOOK
            if send_facebook:
                try:
                    fb_text = f"{subject}\n\n{message}\n\n– 360 Vision HR"
                    fb_url = f"https://www.facebook.com/sharer/sharer.php?quote={requests.utils.quote(fb_text)}"
                    print(f"Facebook: {fb_url}")
                    success_fb += 1
                except Exception as e:
                    print(f"Facebook failed: {e}")

        # --- LOG THE ANNOUNCEMENT ---
        log_action(
            session['username'],
            'Send Announcement',
            {
                'announcement_id': ann_id,
                'type': ann_type,
                'subject': subject,
                'recipients_count': len(recipients),
                'channels': {
                    'email': send_email,
                    'whatsapp': send_whatsapp,
                    'facebook': send_facebook
                },
                'successful': {
                    'email': success_email,
                    'whatsapp': success_wa,
                    'facebook': success_fb
                },
                'has_attachment': has_attachment
            }
        )

        # --- Flash success ---
        channels = []
        if send_email: channels.append(f"Email ({success_email})")
        if send_whatsapp: channels.append(f"WhatsApp ({success_wa})")
        if send_facebook: channels.append(f"Facebook ({success_fb})")
        flash(f"Announcement sent via: {', '.join(channels)}", "success")

        conn.close()
        return redirect(url_for('employee_announcement'))

    conn.close()
    return render_template(
        'employee_announcement.html',
        employees=employees,
        teams=teams,
        recent_announcements=recent_announcements
    )

@app.route("/under_development")
@admin_login_required
def under_development():
    feature = request.args.get("feature", "Feature")
    return render_template("under_development.html", feature=feature)



@app.route('/send-email/<int:emp_id>')
@admin_login_required
def send_email_message_route(emp_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT name, email FROM employees WHERE id=?", (emp_id,))
    emp = cur.fetchone()
    conn.close()

    if not emp or not emp["email"]:
        flash("⚠️ Employee email not found", "danger")
        return redirect(request.referrer or url_for('employee_attendance_dashboard'))

    subject = "Attendance Reminder"
    body = f"""
    Hello {emp['name']},

    Please check your attendance summary or confirm your latest punch.

    Regards,
    360 Vision Attendance Team
    """
    msg = MIMEText(body)
    msg["From"] = SMTP_USER
    msg["To"] = emp["email"]
    msg["Subject"] = subject

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
            s.starttls()
            s.login(SMTP_USER, SMTP_PASSWORD)
            s.send_message(msg)
        flash(f"✅ Email sent to {emp['email']}", "success")
    except Exception as e:
        flash(f"❌ Failed to send email: {e}", "danger")

    return redirect(request.referrer or url_for('employee_attendance_dashboard'))
    

@app.route('/master-login', methods=['GET', 'POST'])
def master_login():
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        if not email or email != MASTER_ADMIN_EMAIL.lower():
            flash("❌ Invalid master admin email", "danger")
            return render_template("master_admin_login.html", master_email=MASTER_ADMIN_EMAIL)

        otp = str(random.randint(100000, 999999))
        session['admin_email'] = email
        session['pending_admin_type'] = 'master'
        session['admin_otp'] = otp
        session['otp_expiry'] = (datetime.now() + timedelta(minutes=OTP_EXPIRY_MINUTES)).timestamp()
        session['otp_last_sent'] = datetime.now().timestamp()

        if send_otp_email(email, otp):
            flash("✅ OTP sent to master admin email", "success")
            return redirect(url_for('verify_otp'))
        flash("❌ Failed to send OTP", "danger")
        return render_template("master_admin_login.html", master_email=MASTER_ADMIN_EMAIL)

    return render_template("master_admin_login.html", master_email=MASTER_ADMIN_EMAIL)


@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()

        if not email:
            flash("❌ Admin email is required", "danger")
            return render_template("admin_email_login.html")

        conn = get_master_db_connection()
        company = conn.execute(
            "SELECT * FROM companies WHERE lower(admin_email) = ? AND is_active = 1",
            (email,)
        ).fetchone()
        conn.close()

        if not company:
            flash("❌ Admin email not found or inactive", "danger")
            return render_template("admin_email_login.html")

        otp = str(random.randint(100000, 999999))
        session['admin_email'] = email
        session['pending_admin_type'] = 'company_email'
        session['admin_otp'] = otp
        session['otp_expiry'] = (datetime.now() + timedelta(minutes=OTP_EXPIRY_MINUTES)).timestamp()
        session['otp_last_sent'] = datetime.now().timestamp()

        if send_otp_email(email, otp):
            flash("✅ OTP sent to admin email", "success")
            return redirect(url_for('verify_otp'))
        flash("❌ Failed to send OTP", "danger")
        return render_template("admin_email_login.html")

    return render_template("admin_email_login.html")

@app.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    # ----- GET: simply show the OTP page -----
    if request.method == 'GET':
        return render_template('otp_verify.html')

    # ----- POST: called via AJAX from otp_verify.html -----
    user_otp = (request.form.get('otp') or '').strip()
    expected_otp = session.get('admin_otp')
    expiry_ts = session.get('otp_expiry', 0)
    now_ts = datetime.now().timestamp()

    # No email / session -> ask to restart flow
    if not session.get('admin_email'):
        return jsonify({
            "status": "no_session",
            "message": "Session expired. Please request a new OTP."
        }), 400

    # OTP expired / missing
    if not expected_otp or now_ts > expiry_ts:
        return jsonify({
            "status": "expired",
            "message": "OTP expired. Please click Resend OTP."
        }), 400

    # Wrong OTP
    if user_otp != expected_otp:
        return jsonify({
            "status": "invalid",
            "message": "Invalid OTP. Please try again."
        }), 400

    # ✅ Correct OTP
    pending_type = session.get('pending_admin_type')
    session.pop('admin_otp', None)

    if pending_type == 'master':
        session['master_admin_logged_in'] = True
        session.pop('pending_admin_type', None)
        session.pop('pending_company_id', None)
        session.pop('pending_company_code', None)
        session.pop('pending_company_db_path', None)
        return jsonify({
            "status": "ok",
            "redirect_url": url_for('master_dashboard')
        }), 200

    if pending_type == 'company_email':
        session.pop('pending_admin_type', None)
        return jsonify({
            "status": "ok",
            "redirect_url": url_for('admin_company_code')
        }), 200

    return jsonify({
        "status": "no_session",
        "message": "Session expired. Please request a new OTP."
    }), 400


@app.route('/resend-otp', methods=['POST'])
def resend_otp():
    email = session.get('admin_email')
    if not email:
        return jsonify({"status": "error", "message": "No email found in session"}), 400

    otp = str(random.randint(100000, 999999))
    session['admin_otp'] = otp
    session['otp_expiry'] = (datetime.now() + timedelta(minutes=OTP_EXPIRY_MINUTES)).timestamp()
    session['otp_last_sent'] = datetime.now().timestamp()

    success = send_otp_email(email, otp)
    if success:
        return jsonify({"status": "ok"})
    else:
        return jsonify({"status": "error", "message": "Failed to send OTP"}), 500


@app.route('/admin-logout')
def admin_logout():
    session.clear()
    try:
        if os.path.exists(ADMIN_SESSION_FILE):
            os.remove(ADMIN_SESSION_FILE)
    except:
        pass
    return redirect(url_for('admin_login'))

@app.route('/master-logout')
def master_logout():
    session.clear()
    return redirect(url_for('master_login'))

# =================================================
# Company Admin - Company Code Step
# =================================================
@app.route('/admin-company-code', methods=['GET', 'POST'])
def admin_company_code():
    if not session.get('admin_email'):
        flash("⚠️ Please login again", "danger")
        return redirect(url_for('admin_login'))

    if request.method == 'POST':
        company_code = (request.form.get('company_code') or '').strip().upper()
        if not company_code:
            flash("❌ Company code is required", "danger")
            return render_template("admin_company_code.html")

        email = session.get('admin_email', '').lower()
        conn = get_master_db_connection()
        company = conn.execute(
            "SELECT * FROM companies WHERE company_code = ? AND lower(admin_email) = ? AND is_active = 1",
            (company_code, email)
        ).fetchone()
        conn.close()

        if not company:
            flash("❌ Invalid company code or inactive company", "danger")
            return render_template("admin_company_code.html")

        session['admin_logged_in'] = True
        session['company_db_path'] = company['db_path']
        session['company_code'] = company['company_code']
        session['company_id'] = company['id']
        flash("✅ Company verified", "success")
        return redirect(url_for('admin_dashboard'))

    return render_template("admin_company_code.html")

# =================================================
# Master Admin - Company Management
# =================================================
@app.route('/master-dashboard', methods=['GET'])
@master_login_required
def master_dashboard():
    conn = get_master_db_connection()
    companies = conn.execute(
        "SELECT * FROM companies ORDER BY created_at DESC"
    ).fetchall()
    company_count = conn.execute("SELECT COUNT(*) AS cnt FROM companies").fetchone()["cnt"]
    conn.close()
    return render_template("master_dashboard.html", companies=companies, company_count=company_count, master_email=MASTER_ADMIN_EMAIL)

@app.route('/master/companies', methods=['POST'])
@master_login_required
def create_company():
    company_name = (request.form.get('company_name') or '').strip()
    company_email = (request.form.get('company_email') or '').strip()
    company_phone = (request.form.get('company_phone') or '').strip()
    company_address = (request.form.get('company_address') or '').strip()
    admin_name = (request.form.get('admin_name') or '').strip()
    admin_email = (request.form.get('admin_email') or '').strip().lower()
    telegram_chat_ids = (request.form.get('telegram_chat_ids') or '').strip()

    if not admin_email:
        flash("❌ Admin email is required", "danger")
        return redirect(url_for('master_dashboard'))
    if not company_name:
        company_name = "Company"

    conn = get_master_db_connection()
    try:
        # Ensure unique company code
        company_code = generate_company_code()
        while conn.execute(
            "SELECT 1 FROM companies WHERE company_code = ?",
            (company_code,)
        ).fetchone():
            company_code = generate_company_code()

        db_filename = f"company_{company_code}.db"
        db_path = os.path.join(COMPANY_DB_DIR, db_filename)

        if not os.path.exists(db_path):
            clone_schema_to_new_db(db_path)

        conn.execute("""
            INSERT INTO companies (
                company_name, company_email, company_phone, company_address,
                admin_name, admin_email, company_code, db_path, telegram_chat_ids
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            company_name, company_email, company_phone, company_address,
            admin_name, admin_email, company_code, db_path, telegram_chat_ids
        ))
        conn.commit()
    except Exception as e:
        conn.rollback()
        flash(f"❌ Failed to create company: {e}", "danger")
        return redirect(url_for('master_dashboard'))
    finally:
        conn.close()

    send_welcome_email(admin_email, company_name, company_code)
    flash(f"✅ Company created. Code: {company_code}", "success")
    return redirect(url_for('master_dashboard'))

@app.route('/master/company/<int:company_id>/toggle', methods=['POST'])
@master_login_required
def toggle_company_status(company_id):
    conn = get_master_db_connection()
    row = conn.execute("SELECT is_active FROM companies WHERE id = ?", (company_id,)).fetchone()
    if not row:
        conn.close()
        flash("❌ Company not found", "danger")
        return redirect(url_for('master_dashboard'))
    new_status = 0 if row["is_active"] else 1
    conn.execute("UPDATE companies SET is_active = ? WHERE id = ?", (new_status, company_id))
    conn.commit()
    conn.close()
    flash("✅ Company status updated", "success")
    return redirect(url_for('master_dashboard'))

@app.route('/master/company/<int:company_id>/telegram', methods=['POST'])
@master_login_required
def update_company_telegram(company_id):
    telegram_chat_ids = (request.form.get('telegram_chat_ids') or '').strip()
    conn = get_master_db_connection()
    conn.execute(
        "UPDATE companies SET telegram_chat_ids = ? WHERE id = ?",
        (telegram_chat_ids, company_id)
    )
    conn.commit()
    conn.close()
    flash("✅ Telegram chat IDs updated", "success")
    return redirect(url_for('master_dashboard'))

# =================================================
# Admin dashboards / listings
# =================================================
@app.route("/admin", methods=["GET", "POST"])
@admin_login_required
def admin():
    conn = get_db_connection()
    cur = conn.cursor()
    if request.method == "POST":
        data = request.form
        files = request.files
        cur.execute("""
            INSERT INTO employees (
                name, email, mobile, aadhaar, address, username, password,
                father_mobile, wife_or_mother_mobile, facebook_profile,
                aadhaar_photo, employee_photo, pan_card, bank_passbook,
                tenth_certificate, other_certificate,
                joining_date, designation, status,
                in_time, out_time, per_hour_salary, week_off_days
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data['name'], data['email'], data['mobile'], data['aadhaar'], data['address'],
            data['mobile'], data['password'],
            data['father_mobile'], data['wife_or_mother_mobile'], data['facebook_profile'],
            save_file(files.get('aadhaar_photo')),
            save_file(files.get('employee_photo')),
            save_file(files.get('pan_card')),
            save_file(files.get('bank_passbook')),
            save_file(files.get('tenth_certificate')),
            save_file(files.get('other_certificate')),
            data['joining_date'], data['designation'], data['status'],
            data.get('in_time'), data.get('out_time'), data.get('per_hour_salary'),
            ','.join(data.getlist('week_off_days'))
        ))
        conn.commit()
        return redirect(url_for('admin'))

    employees = cur.execute("SELECT * FROM employees ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("admin.html", employees=employees)

@app.route('/admin-dashboard')
@admin_login_required
def admin_dashboard():
    company_name = None
    company_id = session.get('company_id')
    if company_id:
        conn = get_master_db_connection()
        row = conn.execute("SELECT company_name FROM companies WHERE id = ?", (company_id,)).fetchone()
        conn.close()
        company_name = row["company_name"] if row else None
    year = datetime.now().year
    return render_template("dashboard.html", company_name=company_name, year=year)

@app.route('/admin/vehicle-logbook')
@admin_login_required
def admin_vehicle_logbook():
    conn = get_db_connection()
    rows = conn.execute("""
        SELECT v.*, e.name AS employee_name, e.mobile AS employee_mobile
        FROM vehicle_logbook v
        JOIN employees e ON v.employee_id = e.id
        ORDER BY v.log_date DESC, v.id DESC
    """).fetchall()
    conn.close()
    return render_template("vehicle_logbook_admin.html", rows=rows)

@app.route('/vehicle-logbook', methods=['GET', 'POST'])
def vehicle_logbook():
    if 'username' not in session:
        return redirect(url_for('login'))
    employee_id = get_employee_id(session['username'])
    if not employee_id:
        return redirect(url_for('login'))

    conn = get_db_connection()
    emp = conn.execute("SELECT name, vehicle_log_enabled FROM employees WHERE id = ?", (employee_id,)).fetchone()
    if not emp or not emp["vehicle_log_enabled"]:
        conn.close()
        flash("⚠️ Vehicle logbook is not enabled for you.", "danger")
        return redirect(url_for('view_attendance'))

    if request.method == 'POST':
        log_date = (request.form.get('log_date') or '').strip()
        vehicle_no = (request.form.get('vehicle_no') or '').strip()
        start_km = (request.form.get('start_km') or '').strip()
        end_km = (request.form.get('end_km') or '').strip()
        purpose = (request.form.get('purpose') or '').strip()
        notes = (request.form.get('notes') or '').strip()

        if not log_date or not vehicle_no:
            flash("❌ Date and Vehicle No are required.", "danger")
        else:
            conn.execute("""
                INSERT INTO vehicle_logbook (
                    employee_id, log_date, vehicle_no, start_km, end_km, purpose, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (employee_id, log_date, vehicle_no, start_km, end_km, purpose, notes))
            conn.commit()
            flash("✅ Vehicle log entry saved.", "success")

    entries = conn.execute("""
        SELECT * FROM vehicle_logbook
        WHERE employee_id = ?
        ORDER BY log_date DESC, id DESC
    """, (employee_id,)).fetchall()
    conn.close()
    return render_template("vehicle_logbook_employee.html", entries=entries, employee_name=emp["name"])

# =================================================
# Work Assignment (Manager / Shop Manager)
# =================================================
def require_employee_login():
    if 'username' not in session:
        return False
    return True

def get_employee_by_mobile(mobile, db_path=None):
    conn = get_db_connection(db_path=db_path)
    row = conn.execute("SELECT * FROM employees WHERE mobile = ?", (mobile,)).fetchone()
    conn.close()
    return row

def get_employee_by_mobile_password(mobile, password, db_path=None):
    conn = get_db_connection(db_path=db_path)
    row = conn.execute("SELECT * FROM employees WHERE mobile = ? AND password = ?", (mobile, password)).fetchone()
    conn.close()
    return row

@app.route('/work-assign', methods=['GET', 'POST'])
def work_assign():
    if not require_employee_login():
        return redirect(url_for('login'))
    employee_id = get_employee_id(session['username'])
    conn = get_db_connection()
    me = conn.execute("SELECT id, name, manager_role, shop_manager_role FROM employees WHERE id = ?", (employee_id,)).fetchone()
    if not me or (not me["manager_role"] and not me["shop_manager_role"]):
        conn.close()
        flash("⚠️ You are not allowed to assign work.", "danger")
        return redirect(url_for('view_attendance'))

    if request.method == 'POST':
        assigned_to = request.form.get('assigned_to')
        customer_name = (request.form.get('customer_name') or '').strip()
        customer_mobile = (request.form.get('customer_mobile') or '').strip()
        customer_address = (request.form.get('customer_address') or '').strip()
        customer_location = (request.form.get('customer_location') or '').strip()
        service_type = (request.form.get('service_type') or '').strip()
        notes = (request.form.get('notes') or '').strip()
        assign_photo = None
        file = request.files.get('assign_photo')
        if file and file.filename:
            assign_photo = save_file(file)

        if not assigned_to or not customer_name or not service_type:
            flash("❌ Assigned employee, customer name, and service type are required.", "danger")
        else:
            conn.execute("""
                INSERT INTO work_assignments (
                    assigned_by, assigned_to, customer_name, customer_mobile,
                    customer_address, customer_location, service_type, notes, assign_photo
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                me["id"], assigned_to, customer_name, customer_mobile,
                customer_address, customer_location, service_type, notes, assign_photo
            ))
            conn.commit()
            flash("✅ Work assigned.", "success")

    employees = conn.execute("SELECT id, name, mobile FROM employees ORDER BY name").fetchall()
    my_assigned = conn.execute("""
        SELECT w.*, e.name AS emp_name
        FROM work_assignments w
        JOIN employees e ON w.assigned_to = e.id
        WHERE w.assigned_by = ?
        ORDER BY w.assigned_at DESC
    """, (me["id"],)).fetchall()
    conn.close()
    return render_template("work_assign.html", employees=employees, my_assigned=my_assigned)

@app.route('/my-work')
def my_work():
    if not require_employee_login():
        return redirect(url_for('login'))
    employee_id = get_employee_id(session['username'])
    conn = get_db_connection()
    works = conn.execute("""
        SELECT * FROM work_assignments
        WHERE assigned_to = ?
        ORDER BY assigned_at DESC
    """, (employee_id,)).fetchall()
    conn.close()
    return render_template("work_list.html", works=works)

@app.route('/my-work/<int:work_id>', methods=['GET', 'POST'])
def my_work_detail(work_id):
    if not require_employee_login():
        return redirect(url_for('login'))
    employee_id = get_employee_id(session['username'])
    conn = get_db_connection()
    work = conn.execute("SELECT * FROM work_assignments WHERE id = ? AND assigned_to = ?", (work_id, employee_id)).fetchone()
    if not work:
        conn.close()
        flash("❌ Work not found.", "danger")
        return redirect(url_for('my_work'))

    if request.method == 'POST':
        action = request.form.get('action')
        lat = request.form.get('lat')
        lon = request.form.get('lon')
        if action == 'checkin':
            if not lat or not lon:
                flash("❌ GPS required for check-in.", "danger")
            else:
                conn.execute("""
                    UPDATE work_assignments
                    SET status='in_progress', checkin_time=datetime('now', 'localtime'),
                        checkin_lat=?, checkin_lon=?
                    WHERE id = ?
                """, (lat, lon, work_id))
                conn.commit()
                flash("✅ Work checked in.", "success")
        elif action == 'checkout':
            if not lat or not lon:
                flash("❌ GPS required for check-out.", "danger")
            else:
                photo = request.files.get('checkout_photo')
                if not photo or not photo.filename:
                    flash("❌ Photo required for check-out.", "danger")
                else:
                    checkout_photo = save_file(photo)
                    amount = request.form.get('amount') or None
                    conn.execute("""
                        UPDATE work_assignments
                        SET status='completed', checkout_time=datetime('now', 'localtime'),
                            checkout_lat=?, checkout_lon=?, checkout_photo=?, amount=?
                        WHERE id = ?
                    """, (lat, lon, checkout_photo, amount, work_id))
                    conn.commit()
                    flash("✅ Work completed.", "success")

    work = conn.execute("SELECT * FROM work_assignments WHERE id = ? AND assigned_to = ?", (work_id, employee_id)).fetchone()
    duration = compute_duration(work["checkin_time"], work["checkout_time"]) if work else None
    conn.close()
    return render_template("work_detail.html", work=work, upi_id="connectingpoint@icici", duration=duration)

@app.route('/work-records')
def work_records():
    if not require_employee_login():
        return redirect(url_for('login'))
    employee_id = get_employee_id(session['username'])
    conn = get_db_connection()
    me = conn.execute("SELECT manager_role FROM employees WHERE id = ?", (employee_id,)).fetchone()
    if not me or not me["manager_role"]:
        conn.close()
        flash("⚠️ Only manager can view all records.", "danger")
        return redirect(url_for('view_attendance'))
    rows = conn.execute("""
        SELECT w.*, e.name AS emp_name
        FROM work_assignments w
        JOIN employees e ON w.assigned_to = e.id
        ORDER BY w.assigned_at DESC
    """).fetchall()
    # add duration
    rows_out = []
    for r in rows:
        d = compute_duration(r["checkin_time"], r["checkout_time"])
        rows_out.append(dict(r) | {"duration": d})
    conn.close()
    return render_template("work_records.html", rows=rows_out)

# =================================================
# Mobile JSON APIs
# =================================================
@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json(force=True, silent=True) or {}
    mobile = (data.get('mobile') or '').strip()
    password = data.get('password') or ''
    company_code = (data.get('company_code') or '').strip().upper()

    if not mobile or not password:
        return jsonify({"status": "error", "message": "Mobile and password required"}), 400

    db_path = None
    if company_code:
        company = get_company_by_code(company_code)
    if not company or not company["db_path"]:
        return jsonify({"status": "error", "message": "Invalid company code"}), 400
    db_path = company["db_path"]
    session['company_code'] = company_code
    session['company_db_path'] = db_path
    session['company_id'] = company['id']

    user = get_employee_by_mobile_password(mobile, password, db_path=db_path)
    if user:
        user = dict(user)
    if not user:
        return jsonify({"status": "error", "message": "Invalid mobile or password"}), 401

    session['username'] = mobile
    return jsonify({
        "status": "ok",
        "employee": {
            "id": user["id"],
            "name": user["name"],
            "mobile": user["mobile"],
            "vehicle_log_enabled": bool(user["vehicle_log_enabled"]),
            "manager_role": bool(user["manager_role"]),
            "shop_manager_role": bool(user["shop_manager_role"])
        }
    })

@app.route('/api/me', methods=['GET'])
def api_me():
    if 'username' not in session:
        return jsonify({"status": "error", "message": "Not logged in"}), 401
    user = get_employee_by_mobile(session['username'])
    if not user:
        return jsonify({"status": "error", "message": "Invalid session"}), 401
    return jsonify({
        "status": "ok",
        "employee": {
            "id": user["id"],
            "name": user["name"],
            "mobile": user["mobile"],
            "vehicle_log_enabled": bool(user["vehicle_log_enabled"]),
            "manager_role": bool(user.get("manager_role")),
            "shop_manager_role": bool(user.get("shop_manager_role"))
        }
    })

@app.route('/api/my-work', methods=['GET'])
def api_my_work():
    if 'username' not in session:
        return jsonify({"status": "error", "message": "Not logged in"}), 401
    employee_id = get_employee_id(session['username'])
    conn = get_db_connection()
    works = conn.execute("""
        SELECT * FROM work_assignments
        WHERE assigned_to = ?
        ORDER BY assigned_at DESC
    """, (employee_id,)).fetchall()
    conn.close()
    return jsonify({
        "status": "ok",
        "works": [dict(w) for w in works]
    })

@app.route('/api/work/<int:work_id>', methods=['GET'])
def api_work_detail(work_id):
    if 'username' not in session:
        return jsonify({"status": "error", "message": "Not logged in"}), 401
    employee_id = get_employee_id(session['username'])
    conn = get_db_connection()
    work = conn.execute(
        "SELECT * FROM work_assignments WHERE id = ? AND assigned_to = ?",
        (work_id, employee_id)
    ).fetchone()
    conn.close()
    if not work:
        return jsonify({"status": "error", "message": "Work not found"}), 404
    d = dict(work)
    d["duration"] = compute_duration(d.get("checkin_time"), d.get("checkout_time"))
    return jsonify({"status": "ok", "work": d})

@app.route('/api/work/checkin', methods=['POST'])
def api_work_checkin():
    if 'username' not in session:
        return jsonify({"status": "error", "message": "Not logged in"}), 401
    data = request.get_json(force=True, silent=True) or {}
    work_id = data.get("work_id")
    lat = data.get("lat")
    lon = data.get("lon")
    if not work_id or not lat or not lon:
        return jsonify({"status": "error", "message": "work_id, lat, lon required"}), 400
    employee_id = get_employee_id(session['username'])
    conn = get_db_connection()
    work = conn.execute(
        "SELECT id, status FROM work_assignments WHERE id = ? AND assigned_to = ?",
        (work_id, employee_id)
    ).fetchone()
    if not work:
        conn.close()
        return jsonify({"status": "error", "message": "Work not found"}), 404
    if work["status"] != "assigned":
        conn.close()
        return jsonify({"status": "error", "message": "Work already started"}), 400
    conn.execute("""
        UPDATE work_assignments
        SET status='in_progress', checkin_time=datetime('now', 'localtime'),
            checkin_lat=?, checkin_lon=?
        WHERE id = ?
    """, (lat, lon, work_id))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})

@app.route('/api/work/checkout', methods=['POST'])
def api_work_checkout():
    if 'username' not in session:
        return jsonify({"status": "error", "message": "Not logged in"}), 401
    work_id = request.form.get('work_id')
    lat = request.form.get('lat')
    lon = request.form.get('lon')
    amount = request.form.get('amount')
    photo = request.files.get('photo')
    if not work_id or not lat or not lon:
        return jsonify({"status": "error", "message": "work_id, lat, lon required"}), 400
    if not photo or not photo.filename:
        return jsonify({"status": "error", "message": "Photo required"}), 400

    employee_id = get_employee_id(session['username'])
    conn = get_db_connection()
    work = conn.execute(
        "SELECT id, status FROM work_assignments WHERE id = ? AND assigned_to = ?",
        (work_id, employee_id)
    ).fetchone()
    if not work:
        conn.close()
        return jsonify({"status": "error", "message": "Work not found"}), 404
    if work["status"] != "in_progress":
        conn.close()
        return jsonify({"status": "error", "message": "Work not in progress"}), 400

    checkout_photo = save_file(photo)
    conn.execute("""
        UPDATE work_assignments
        SET status='completed', checkout_time=datetime('now', 'localtime'),
            checkout_lat=?, checkout_lon=?, checkout_photo=?, amount=?
        WHERE id = ?
    """, (lat, lon, checkout_photo, amount, work_id))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})

@app.route('/api/employees', methods=['GET'])
def api_employees():
    if 'username' not in session:
        return jsonify({"status": "error", "message": "Not logged in"}), 401
    employee_id = get_employee_id(session['username'])
    conn = get_db_connection()
    me = conn.execute("SELECT manager_role, shop_manager_role FROM employees WHERE id = ?", (employee_id,)).fetchone()
    if not me or (not me["manager_role"] and not me["shop_manager_role"]):
        conn.close()
        return jsonify({"status": "error", "message": "Not allowed"}), 403
    rows = conn.execute("SELECT id, name, mobile FROM employees ORDER BY name").fetchall()
    conn.close()
    return jsonify({"status": "ok", "employees": [dict(r) for r in rows]})

@app.route('/api/work-assign', methods=['POST'])
def api_work_assign():
    if 'username' not in session:
        return jsonify({"status": "error", "message": "Not logged in"}), 401
    data = request.get_json(force=True, silent=True) or {}
    assigned_to = data.get("assigned_to")
    customer_name = (data.get("customer_name") or "").strip()
    customer_mobile = (data.get("customer_mobile") or "").strip()
    customer_address = (data.get("customer_address") or "").strip()
    customer_location = (data.get("customer_location") or "").strip()
    service_type = (data.get("service_type") or "").strip()
    notes = (data.get("notes") or "").strip()

    if not assigned_to or not customer_name or not service_type:
        return jsonify({"status": "error", "message": "assigned_to, customer_name, service_type required"}), 400

    employee_id = get_employee_id(session['username'])
    conn = get_db_connection()
    me = conn.execute("SELECT manager_role, shop_manager_role FROM employees WHERE id = ?", (employee_id,)).fetchone()
    if not me or (not me["manager_role"] and not me["shop_manager_role"]):
        conn.close()
        return jsonify({"status": "error", "message": "Not allowed"}), 403

    conn.execute("""
        INSERT INTO work_assignments (
            assigned_by, assigned_to, customer_name, customer_mobile,
            customer_address, customer_location, service_type, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        employee_id, assigned_to, customer_name, customer_mobile,
        customer_address, customer_location, service_type, notes
    ))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})

@app.route('/api/work-records', methods=['GET'])
def api_work_records():
    if 'username' not in session:
        return jsonify({"status": "error", "message": "Not logged in"}), 401
    employee_id = get_employee_id(session['username'])
    conn = get_db_connection()
    me = conn.execute("SELECT manager_role FROM employees WHERE id = ?", (employee_id,)).fetchone()
    if not me or not me["manager_role"]:
        conn.close()
        return jsonify({"status": "error", "message": "Not allowed"}), 403
    rows = conn.execute("""
        SELECT w.*, e.name AS emp_name
        FROM work_assignments w
        JOIN employees e ON w.assigned_to = e.id
        ORDER BY w.assigned_at DESC
    """).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["duration"] = compute_duration(d.get("checkin_time"), d.get("checkout_time"))
        out.append(d)
    conn.close()
    return jsonify({"status": "ok", "records": out})

@app.route('/company-registration', methods=['GET', 'POST'])
@admin_login_required
def company_registration():
    company_id = session.get('company_id')
    if not company_id:
        flash("⚠️ Company session missing. Please login again.", "danger")
        return redirect(url_for('admin_login'))

    conn = get_master_db_connection()
    if request.method == 'POST':
        fields = {
            "company_legal_name": (request.form.get('company_legal_name') or '').strip(),
            "gst_number": (request.form.get('gst_number') or '').strip(),
            "pan_number": (request.form.get('pan_number') or '').strip(),
            "cin_number": (request.form.get('cin_number') or '').strip(),
            "website": (request.form.get('website') or '').strip(),
            "billing_address": (request.form.get('billing_address') or '').strip(),
            "billing_city": (request.form.get('billing_city') or '').strip(),
            "billing_state": (request.form.get('billing_state') or '').strip(),
            "billing_pincode": (request.form.get('billing_pincode') or '').strip(),
            "contact_person": (request.form.get('contact_person') or '').strip(),
            "contact_phone": (request.form.get('contact_phone') or '').strip(),
        }
        conn.execute("""
            UPDATE companies SET
                company_legal_name = ?,
                gst_number = ?,
                pan_number = ?,
                cin_number = ?,
                website = ?,
                billing_address = ?,
                billing_city = ?,
                billing_state = ?,
                billing_pincode = ?,
                contact_person = ?,
                contact_phone = ?
            WHERE id = ?
        """, (
            fields["company_legal_name"],
            fields["gst_number"],
            fields["pan_number"],
            fields["cin_number"],
            fields["website"],
            fields["billing_address"],
            fields["billing_city"],
            fields["billing_state"],
            fields["billing_pincode"],
            fields["contact_person"],
            fields["contact_phone"],
            company_id
        ))
        conn.commit()
        flash("✅ Company details updated", "success")

    company = conn.execute("SELECT * FROM companies WHERE id = ?", (company_id,)).fetchone()
    conn.close()
    if not company:
        flash("❌ Company not found", "danger")
        return redirect(url_for('admin_dashboard'))

    return render_template("company_registration.html", company=company)

@app.route('/admin_records', methods=['GET'])
@admin_login_required
def admin_records():
    conn = get_db_connection()
    cur = conn.cursor()
    search = request.args.get('search', '').strip()

    query = """
        SELECT e.*, a.photo_path
        FROM employees e
        LEFT JOIN (
            SELECT employee_id, MAX(id) AS max_att_id
            FROM attendance
            GROUP BY employee_id
        ) AS latest ON e.id = latest.employee_id
        LEFT JOIN attendance a ON a.id = latest.max_att_id
        WHERE 1=1
    """
    params = []
    if search:
        like = f"%{search}%"
        query += " AND (e.name LIKE ? OR e.mobile LIKE ? OR e.status LIKE ?)"
        params += [like, like, like]
    query += " ORDER BY e.id DESC"
    rows = cur.execute(query, params).fetchall()
    conn.close()
    return render_template("admin_records.html", employees=[dict(r) for r in rows], now=datetime.now)

@app.route('/employee_list')
@admin_login_required
def employee_list():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM employees ORDER BY id DESC")
    employees = cur.fetchall()
    conn.close()
    return render_template("employee_list.html", employees=employees)

@app.route('/employee/<int:id>')
@admin_login_required
def employee_view(id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM employees WHERE id = ?", (id,))
    employee = cur.fetchone()
    conn.close()
    if not employee:
        return "Employee not found", 404
    return render_template("employee.html", employee=employee)
    
@app.route("/add_employee", methods=["GET", "POST"])
@admin_login_required
def add_employee():
    if request.method == "POST":
        conn = get_db_connection()
        cur = conn.cursor()
        data = request.form
        files = request.files

        name = (data.get('name') or '').strip()
        mobile = (data.get('mobile') or '').strip()
        email = (data.get('email') or '').strip()

        # Prevent duplicate employees by name + mobile
        cur.execute("SELECT * FROM employees WHERE LOWER(TRIM(name)) = ? AND TRIM(mobile) = ?", 
                    (name.lower(), mobile))
        existing = cur.fetchone()
        if existing:
            flash('Employee already exists.', 'danger')
            conn.close()
            return redirect(url_for('add_employee'))

        # Handle No-Out-Punch checkbox
        no_out_punch = 1 if 'no_out_punch' in data else 0
        office_staff = 1 if 'office_staff' in data else 0
        office_lat = data.get('office_lat') or None
        office_lon = data.get('office_lon') or None
        office_radius_m = data.get('office_radius_m') or 200
        vehicle_log_enabled = 1 if 'vehicle_log_enabled' in data else 0
        manager_role = 1 if 'manager_role' in data else 0
        shop_manager_role = 1 if 'shop_manager_role' in data else 0

        if office_staff and (not office_lat or not office_lon):
            flash('Office location is required for office staff.', 'danger')
            conn.close()
            return redirect(url_for('add_employee'))

        # Save files and get paths
        uploaded_files = {}
        upload_fields = [
            'aadhaar_photo', 'employee_photo', 'pan_card',
            'bank_passbook', 'tenth_certificate', 'other_certificate'
        ]
        for field in upload_fields:
            file = files.get(field)
            if file and file.filename:
                uploaded_files[field] = save_file(file)

        # Insert employee record
        cur.execute("""
            INSERT INTO employees (
                name, email, mobile, aadhaar, address, username, password,
                father_mobile, wife_or_mother_mobile, facebook_profile,
                aadhaar_photo, employee_photo, pan_card, bank_passbook,
                tenth_certificate, other_certificate,
                joining_date, designation, status,
                in_time, out_time, per_hour_salary, week_off_days, shift_hours,
                no_out_punch, office_staff, office_lat, office_lon, office_radius_m,
                vehicle_log_enabled, manager_role, shop_manager_role
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get('name'), data.get('email'), data.get('mobile'), data.get('aadhaar'), data.get('address'),
            data.get('username'), data.get('password'),
            data.get('father_mobile'), data.get('wife_or_mother_mobile'), data.get('facebook_profile'),
            uploaded_files.get('aadhaar_photo'),
            uploaded_files.get('employee_photo'),
            uploaded_files.get('pan_card'),
            uploaded_files.get('bank_passbook'),
            uploaded_files.get('tenth_certificate'),
            uploaded_files.get('other_certificate'),
            data.get('joining_date'), data.get('designation'), data.get('status'),
            data.get('in_time'), data.get('out_time'), data.get('per_hour_salary'),
            ','.join(data.getlist('week_off_days')),
            data.get('shift_hours') or 8,
            no_out_punch, office_staff, office_lat, office_lon, office_radius_m,
            vehicle_log_enabled, manager_role, shop_manager_role
        ))

        employee_id = cur.lastrowid
        conn.commit()
        conn.close()

        # LOG THE ADD ACTION
        log_action(
            session.get('admin_email') or session.get('username') or 'admin',
            'Add Employee',
            {
                'employee_id': employee_id,
                'name': name,
                'mobile': mobile,
                'email': email,
                'team': data.get('team'),
                'designation': data.get('designation'),
                'status': data.get('status'),
                'no_out_punch': bool(no_out_punch),
                'files_uploaded': list(uploaded_files.keys()),
                'week_off_days': data.getlist('week_off_days')
            }
        )

        flash('Employee added successfully!', 'success')
        return redirect(url_for('admin_dashboard'))

    return render_template("add_employee.html")

@app.route('/edit_employee/<int:id>', methods=['GET', 'POST'])
@admin_login_required
def edit_employee(id):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    if request.method == 'POST':
        # --- Fetch old data ---
        old_emp = cur.execute('SELECT * FROM employees WHERE id=?', (id,)).fetchone()
        old_dict = dict(old_emp) if old_emp else {}

        # --- Get form data ---
        name = request.form.get('name', '')
        email = request.form.get('email', '')
        mobile = request.form.get('mobile', '')
        password = request.form.get('password', '')
        aadhaar = request.form.get('aadhaar', '')
        address = request.form.get('address', '')
        father_mobile = request.form.get('father_mobile', '')
        wife_or_mother_mobile = request.form.get('wife_or_mother_mobile', '')
        facebook_profile = request.form.get('facebook_profile', '')
        joining_date = request.form.get('joining_date', '')
        designation = request.form.get('designation', '')
        status = request.form.get('status', '')
        team = request.form.get('team', '')
        employee_category = request.form.get('employee_category', '')
        no_out_punch = 1 if 'no_out_punch' in request.form else 0
        office_staff = 1 if 'office_staff' in request.form else 0
        office_lat = request.form.get('office_lat') or None
        office_lon = request.form.get('office_lon') or None
        office_radius_m = request.form.get('office_radius_m') or 200
        vehicle_log_enabled = 1 if 'vehicle_log_enabled' in request.form else 0
        manager_role = 1 if 'manager_role' in request.form else 0
        shop_manager_role = 1 if 'shop_manager_role' in request.form else 0
        in_time = request.form.get('in_time', '')
        out_time = request.form.get('out_time', '')
        per_hour_salary = request.form.get('per_hour_salary', 0)
        shift_hours = request.form.get('shift_hours', 8)
        week_off_days = ','.join(request.form.getlist('week_off_days'))
        if office_staff and (not office_lat or not office_lon):
            flash('Office location is required for office staff.', 'danger')
            conn.close()
            return redirect(url_for('edit_employee', id=id))

        # --- File uploads ---
        upload_fields = [
            'employee_photo', 'aadhaar_photo', 'pan_card',
            'bank_passbook', 'tenth_certificate', 'other_certificate'
        ]
        upload_updates = {}
        upload_dir = os.path.join('static', 'uploads')
        os.makedirs(upload_dir, exist_ok=True)

        for field in upload_fields:
            file = request.files.get(field)
            if file and file.filename:
                filename = f"{int(datetime.now().timestamp())}_{secure_filename(file.filename)}"
                save_path = os.path.join(upload_dir, filename)
                file.save(save_path)
                upload_updates[field] = filename

        # --- Build query (NO username) ---
        update_query = '''
            UPDATE employees SET
                name=?, email=?, mobile=?, password=?, aadhaar=?, address=?,
                father_mobile=?, wife_or_mother_mobile=?, facebook_profile=?,
                joining_date=?, designation=?, status=?, team=?, employee_category=?,
                no_out_punch=?, office_staff=?, office_lat=?, office_lon=?, office_radius_m=?,
                vehicle_log_enabled=?, manager_role=?, shop_manager_role=?,
                in_time=?, out_time=?, per_hour_salary=?, shift_hours=?, week_off_days=?
        '''
        params = [
            name, email, mobile, password, aadhaar, address,
            father_mobile, wife_or_mother_mobile, facebook_profile,
            joining_date, designation, status, team, employee_category,
            no_out_punch, office_staff, office_lat, office_lon, office_radius_m,
            vehicle_log_enabled, manager_role, shop_manager_role,
            in_time, out_time, per_hour_salary, shift_hours, week_off_days
        ]

        for field, filename in upload_updates.items():
            update_query += f", {field}=?"
            params.append(filename)

        update_query += " WHERE id=?"
        params.append(id)

        # --- Execute ---
        try:
            cur.execute(update_query, params)
            conn.commit()

            # --- Detect changes ---
            changes = []
            field_map = {
                'name': 'Name', 'email': 'Email', 'mobile': 'Mobile',
                'password': 'Password', 'aadhaar': 'Aadhaar', 'address': 'Address',
                'father_mobile': "Father's Mobile", 'wife_or_mother_mobile': "Wife/Mother Mobile",
                'facebook_profile': 'Facebook', 'joining_date': 'Joining Date',
                'designation': 'Designation', 'status': 'Status', 'team': 'Team',
                'employee_category': 'Category', 'in_time': 'In Time', 'out_time': 'Out Time',
                'per_hour_salary': '₹/Hour', 'shift_hours': 'Shift Hours',
                'week_off_days': 'Week Off Days', 'no_out_punch': 'No Out-Punch',
                'office_staff': 'Office Staff', 'office_lat': 'Office Latitude',
                'office_lon': 'Office Longitude', 'office_radius_m': 'Office Radius',
                'vehicle_log_enabled': 'Vehicle Logbook',
                'manager_role': 'Manager', 'shop_manager_role': 'Shop Manager'
            }

            for field in field_map:
                old_val = old_dict.get(field)
                new_val = locals().get(field, old_val)
                if str(old_val) != str(new_val):
                    changes.append((field_map[field], old_val or '—', new_val or '—'))

            for field, filename in upload_updates.items():
                old_file = old_dict.get(field)
                changes.append((field_map.get(field, field.replace('_', ' ').title()), old_file or '—', filename))

            # --- Log the edit ---
            admin_user = session.get('admin_email') or session.get('username') or 'admin'
            log_action(
                admin_user,
                'Edit Employee',
                {
                    'employee_id': id,
                    'employee_name': name,
                    'changes_count': len(changes),
                    'changes': changes,
                    'files_updated': list(upload_updates.keys())
                }
            )

            if changes or upload_updates:
                session['changes'] = changes
                flash('Employee updated successfully!', 'success')
            else:
                flash('No changes detected.', 'info')

        except Exception as e:
            conn.rollback()
            flash(f'Error: {str(e)}', 'danger')
        finally:
            conn.close()

        return redirect(url_for('edit_employee', id=id))

    # --- GET ---
    emp = cur.execute('SELECT * FROM employees WHERE id=?', (id,)).fetchone()
    conn.close()
    return render_template('edit_employee.html', emp=emp)
    
    
@app.route('/admin/no_out_punch', methods=['GET', 'POST'])
@admin_login_required
def no_out_punch():
    # ── Filters ─────────────────────────────────────
    start_date = request.form.get('start_date') or request.args.get('start_date')
    end_date   = request.form.get('end_date')   or request.args.get('end_date')
    search     = (request.form.get('search') or request.args.get('search') or '').lower()
    page       = int(request.args.get('page', 1))
    per_page   = 20

    # ── Export Excel (POST) ────────────────────────
    if request.method == 'POST' and 'export_excel' in request.form:
        return no_out_punch_export()

    # ── Build query ─────────────────────────────────
    conn = get_db_connection()
    query = """
        SELECT 
            e.name, e.mobile, e.employee_photo,
            a.in_time, a.latitude, a.longitude, a.photo_path,
            a.timestamp
        FROM attendance a
        JOIN employees e ON a.employee_id = e.id
        WHERE (a.out_time IS NULL OR a.out_time = '')
          AND e.no_out_punch = 1
          AND DATE(a.timestamp) BETWEEN ? AND ?
    """
    params = [start_date or '1900-01-01', end_date or '2100-01-01']

    if search:
        query += " AND (LOWER(e.name) LIKE ? OR e.mobile LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])

    query += " ORDER BY a.timestamp DESC"

    # ── Pagination count ───────────────────────────
    count_query = f"SELECT COUNT(*) FROM ({query})"
    total = conn.execute(count_query, params).fetchone()[0]
    total_pages = (total + per_page - 1) // per_page
    offset = (page - 1) * per_page

    # ── Final query with LIMIT/OFFSET ──────────────
    final_query = query + " LIMIT ? OFFSET ?"
    params.extend([per_page, offset])
    logs = conn.execute(final_query, params).fetchall()

    # ── Clean photo paths in Python ────────────────
    cleaned_logs = []
    for row in logs:
        r = dict(row)
        if r['photo_path']:
            p = r['photo_path'].split(',')[0].strip().replace('\\', '/')
            if p.startswith('static/'):
                p = p[7:]
            r['photo_clean'] = p
        else:
            r['photo_clean'] = None
        cleaned_logs.append(r)

    conn.close()

    return render_template(
        'no_out_punch.html',
        logs=cleaned_logs,
        start_date=start_date,
        end_date=end_date,
        search=search,
        page=page,
        total_pages=total_pages
    )
    
@app.route('/admin/no_out_punch_export', methods=['POST'])
@admin_login_required
def no_out_punch_export():
    start_date = request.form.get('start_date')
    end_date   = request.form.get('end_date')
    search     = request.form.get('search', '').lower()

    conn = get_db_connection()
    query = """
        SELECT e.name, e.mobile, a.in_time, a.latitude, a.longitude, a.photo_path
        FROM attendance a
        JOIN employees e ON a.employee_id = e.id
        WHERE (a.out_time IS NULL OR a.out_time = '')
          AND e.no_out_punch = 1
          AND DATE(a.timestamp) BETWEEN ? AND ?
    """
    params = [start_date or '1900-01-01', end_date or '2100-01-01']
    if search:
        query += " AND (LOWER(e.name) LIKE ? OR e.mobile LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])

    rows = conn.execute(query, params).fetchall()
    conn.close()

    df = pd.DataFrame([dict(r) for r in rows])
    if df.empty:
        df = pd.DataFrame(columns=['Name','Mobile','In Time','Latitude','Longitude','Photo'])

    out = BytesIO()
    with pd.ExcelWriter(out, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='No Out Punch')
    out.seek(0)

    return send_file(
        out,
        as_attachment=True,
        download_name=f"no_out_punch_{start_date or 'all'}_to_{end_date or 'all'}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    
@app.route("/employee/<int:id>/delete")
@admin_login_required
def delete_employee(id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM employees WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    flash("🗑️ Employee deleted successfully!", "success")
    return redirect(url_for("admin"))

# =================================================
# Auth (employee)
# =================================================

# --- Helper: simple login logger ---
from datetime import datetime
import json

def log_action(user, action, details=None):
    """Logs login attempts to console and file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = {
        "user": user,
        "action": action,
        "timestamp": timestamp,
        "details": details or {}
    }
    try:
        print(f"[LOGIN LOG] {json.dumps(entry, ensure_ascii=False)}")
        with open("/media/data/employee_db/login_audit.log", "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        print(f"[LOG_ERROR] {e}")


@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        mobile = request.form['mobile'].strip()
        password = request.form['password']
        company_code = (request.form.get('company_code') or '').strip().upper()
        db_path = None
        if company_code:
            company = get_company_by_code(company_code)
            if not company:
                error = "Invalid company code"
                return render_template('login.html', error=error)
            db_path = company['db_path']
            session['company_code'] = company_code
            session['company_db_path'] = db_path
            session['company_id'] = company['id']

        conn = get_db_connection(db_path=db_path)
        cur = conn.cursor()
        cur.execute("SELECT * FROM employees WHERE mobile = ? AND password = ?", (mobile, password))
        user = cur.fetchone()
        conn.close()

        # --- LOG THE LOGIN ATTEMPT ---
        log_action(
            mobile,  # Even if failed, log the mobile used
            'Login Attempt',
            {
                'success': bool(user),
                'ip': request.remote_addr,
                'user_agent': request.headers.get('User-Agent', '')[:200],
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        )

        if user:
            session['username'] = mobile
            # --- LOG SUCCESSFUL LOGIN ---
            log_action(
                mobile,
                'Login Success',
                {
                    'ip': request.remote_addr,
                    'user_agent': request.headers.get('User-Agent', '')[:200],
                    'name': user['name'] if 'name' in user else None
                }
            )
            return redirect(url_for('view_attendance'))
        else:
            error = "Invalid mobile number or password"

    return render_template('login.html', error=error)
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# =======================================================
# Save Attendance - Auto toggle IN / OUT per employee/day
# =======================================================

# ✅ GET route — show attendance page
@app.route('/attendance', methods=['GET'])
def view_attendance():
    print("➡️ Accessing /attendance")
    print("🔍 session contents:", dict(session))

    if 'username' not in session:
        print("❌ session['username'] missing! Redirecting to /login")
        return redirect(url_for('login'))

    print("✅ Access granted to:", session['username'])
    username = session['username']  # mobile is used as username

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT * FROM employees WHERE mobile = ?", (username,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return "Employee not found", 404

    employee = dict(row)
    employee_id = employee['id']
    assigned_count = conn.execute(
        "SELECT COUNT(*) FROM work_assignments WHERE assigned_to = ? AND status = 'assigned'",
        (employee_id,)
    ).fetchone()[0]

    # -------------------------------
    # 📅 Attendance Records & Summary
    # -------------------------------
    page = int(request.args.get('page', 1))
    per_page = 10
    offset = (page - 1) * per_page

    cur.execute("SELECT COUNT(*) FROM attendance WHERE employee_id = ?", (employee_id,))
    total_records = cur.fetchone()[0]
    total_pages = (total_records + per_page - 1) // per_page

    cur.execute("""
        SELECT * FROM attendance
        WHERE employee_id = ?
        ORDER BY timestamp DESC
        LIMIT ? OFFSET ?
    """, (employee_id, per_page, offset))
    records = [dict(r) for r in cur.fetchall()]

    cur.execute("""
        SELECT
            SUM(CASE WHEN action = 'in' THEN 1 ELSE 0 END) as total_in,
            SUM(CASE WHEN action = 'out' THEN 1 ELSE 0 END) as total_out
        FROM attendance
        WHERE employee_id = ?
    """, (employee_id,))
    summary = dict(cur.fetchone())

    # ✅ Pending expenses
    cur.execute("SELECT COUNT(*) FROM expenses WHERE employee_id = ? AND status = 'Pending'", (employee_id,))
    pending_count = cur.fetchone()[0]

    # ------------------------------------
    # 🕒 Determine today's punch direction
    # ------------------------------------
    today = datetime.now().date()
    cur.execute("""
        SELECT action, timestamp FROM attendance
        WHERE employee_id = ? AND date(timestamp) = ?
        ORDER BY timestamp DESC LIMIT 1
    """, (employee_id, today))
    last_record = cur.fetchone()

    if not last_record:
        next_action = "in"
        status_message = "No punches yet today. Ready to Punch In!"
        color = "#00ff88"
    else:
        last_action = last_record["action"].lower()
        if last_action == "in":
            next_action = "out"
            status_message = f"Last punched IN at {last_record['timestamp']}."
            color = "#ff3366"
        else:
            next_action = "in"
            status_message = f"Last punched OUT at {last_record['timestamp']}."
            color = "#00ff88"

    conn.close()

    return render_template(
        "attendance.html",
        employee=employee,
        summary=summary,
        records=records,
        page=page,
        total_pages=total_pages,
        user_photo=employee.get("employee_photo", "default_user.png"),
        username=employee['name'],
        pending_count=pending_count,
        vehicle_log_enabled=bool(employee.get("vehicle_log_enabled")),
        is_manager=bool(employee.get("manager_role")),
        is_shop_manager=bool(employee.get("shop_manager_role")),
        assigned_count=assigned_count,
        next_action=next_action,
        status_message=status_message,
        status_color=color
    )


# =======================================================
# ✅ POST route — handle submission with log + proper logic
# =======================================================
@app.route('/attendance', methods=['POST'])
def submit_attendance():
    if 'username' not in session:
        return jsonify({'status': 'error', 'message': 'Session expired'})

    username = session['username']
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # get employee id
    cur.execute("SELECT id FROM employees WHERE mobile = ?", (username,))
    emp = cur.fetchone()
    if not emp:
        conn.close()
        return jsonify({'status': 'error', 'message': 'Employee not found'})

    employee_id = emp['id']
    lat = request.form.get('latitude')
    lon = request.form.get('longitude')
    photo_path = request.form.get('photo_path', '')

    # ✅ Check today's punches
    cur.execute("""
        SELECT action FROM attendance
        WHERE employee_id = ? AND DATE(timestamp) = DATE('now', 'localtime')
        ORDER BY id DESC LIMIT 1
    """, (employee_id,))
    last = cur.fetchone()

    cur.execute("""
        SELECT COUNT(*) FROM attendance
        WHERE employee_id = ? AND DATE(timestamp) = DATE('now', 'localtime') AND action = 'in'
    """, (employee_id,))
    in_count = cur.fetchone()[0]

    # ✅ Determine next action properly
    if in_count == 0:
        action = 'in'   # first punch of the day must be IN
    elif last and last['action'] == 'in':
        action = 'out'
    else:
        action = 'in'

    # ✅ Office location check (if enabled)
    ok, msg = check_office_location(conn, employee_id, lat, lon)
    if not ok:
        conn.close()
        return jsonify({'status': 'error', 'message': msg})

    # ✅ Insert attendance record
    cur.execute("""
        INSERT INTO attendance (employee_id, action, timestamp, latitude, longitude, photo_path)
        VALUES (?, ?, datetime('now', 'localtime'), ?, ?, ?)
    """, (employee_id, action, lat, lon, photo_path))
    conn.commit()

    # ✅ Log the punch with full device details
    try:
        log_activity(employee_id, username, f"Punch {action.upper()}", request)
    except Exception as e:
        print("⚠️ Logging failed:", e)

    conn.close()
    return jsonify({'status': 'success', 'action': action})



# Async helper
def async_task(func):
    def wrapper(*args, **kwargs):
        t = threading.Thread(target=func, args=args, kwargs=kwargs, daemon=True)
        t.start()
    return wrapper

@async_task
def async_send_email(emp, action, timestamp, lat, lon, saved_filenames):
    try:
        if emp and emp["email"]:
            photo_path = None
            if saved_filenames:
                last_rel = saved_filenames[-1]
                last_abs = os.path.join(BASE_DIR, last_rel) if last_rel.startswith("static/") else os.path.join(ATTENDANCE_FOLDER, os.path.basename(last_rel))
                photo_path = last_abs if os.path.exists(last_abs) else None
            send_attendance_email(emp["email"], emp["name"], action, timestamp, lat, lon, photo_path)
        else:
            print(f"⚠️ No email for employee {emp['name'] if emp else 'N/A'}")
    except Exception as e:
        print("❌ Async email error:", e)

@async_task
def async_send_telegram(emp, action, timestamp, lat, lon, saved_filenames):
    try:
        map_link = f"https://www.google.com/maps?q={lat},{lon}"
        caption = (
            f"👤 *Employee:* {emp['name']}\n"
            f"🔘 *Action:* {action.title()}\n"
            f"⏰ *Time:* {timestamp}\n"
            f"📍 [View Location]({map_link})"
        )
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
        photo_path = None
        if saved_filenames:
            last_rel = saved_filenames[-1]
            photo_path = os.path.join(BASE_DIR, last_rel) if last_rel.startswith("static/") else os.path.join(ATTENDANCE_FOLDER, os.path.basename(last_rel))

        for chat_id in get_company_telegram_chat_ids():
            if photo_path and os.path.exists(photo_path):
                with open(photo_path, "rb") as photo:
                    requests.post(url, data={"chat_id": chat_id, "caption": caption, "parse_mode": "Markdown"},
                                  files={"photo": photo}, timeout=5)
            else:
                send_telegram_message(emp['name'], action, timestamp, lat, lon)
    except Exception as e:
        print("⚠️ Telegram send failed:", e)

@app.route('/api/attendance', methods=['POST'])
def api_attendance():
    if 'username' not in session:
        return jsonify({"status": "error", "message": "Not logged in"}), 401
    if not request.is_json:
        return jsonify({"status": "error", "message": "Invalid content type"}), 400

    data = request.get_json()
    action = (data.get('action') or '').lower().strip()
    photos = data.get('photos', [])
    location = data.get('location', {}) or {}
    subject = data.get('subject', '') or ''

    username = session['username']
    employee_id = get_employee_id(username)
    if not employee_id:
        return jsonify({"status": "error", "message": "Invalid employee"}), 400
    if not photos:
        return jsonify({"status": "error", "message": "No photo captured"}), 400

    lat = str(location.get('latitude') or '').strip()
    lon = str(location.get('longitude') or '').strip()
    if not lat or not lon:
        return jsonify({"status": "error", "message": "Location not captured"}), 400

    # ✅ Office location check (if enabled)
    conn = get_db_connection()
    ok, msg = check_office_location(conn, employee_id, lat, lon)
    if not ok:
        conn.close()
        return jsonify({"status": "error", "message": msg}), 400

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    saved_filenames = []

    # Save captured photos to ATTENDANCE_FOLDER
    for idx, photo_data in enumerate(photos):
        if ',' in photo_data:
            photo_data = photo_data.split(',', 1)[1]
        try:
            photo_binary = base64.b64decode(photo_data)
        except Exception:
            return jsonify({"status": "error", "message": "Invalid photo data"}), 400
        filename = f"{username}_{action}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{idx}.jpg"
        filepath = os.path.join(ATTENDANCE_FOLDER, filename)
        with open(filepath, 'wb') as f:
            f.write(photo_binary)
        saved_filenames.append(f"static/attendance_photos/{filename}")

    photo_paths_str = ",".join(saved_filenames)
    full_location = f"{lat},{lon}"
    emp_shift_hours = get_employee_shift_hours(employee_id)

    cur = conn.cursor()

    if action == 'in':
        cur.execute("""
            INSERT INTO attendance (
                employee_id, timestamp, action, location, subject,
                photo_path, latitude, longitude, in_time, shift_hours
            ) VALUES (?, ?, 'in', ?, ?, ?, ?, ?, ?, ?)
        """, (employee_id, timestamp, full_location, subject,
              photo_paths_str, lat, lon, timestamp, emp_shift_hours))
        conn.commit()
        cur.execute("SELECT id, name, email FROM employees WHERE id=?", (employee_id,))
        emp = cur.fetchone()
        async_send_email(emp, action, timestamp, lat, lon, saved_filenames)
        async_send_telegram(emp, action, timestamp, lat, lon, saved_filenames)
        conn.close()
        return jsonify({"status": "success", "message": f"Punched IN at {timestamp}"})

    elif action == 'out':
        # Try to pair with today's IN
        cur.execute("""
            SELECT id FROM attendance
            WHERE employee_id=? AND date(timestamp) = date('now', 'localtime')
              AND action='in' AND out_time IS NULL
            ORDER BY timestamp DESC LIMIT 1
        """, (employee_id,))
        in_row = cur.fetchone()
        if in_row:
            cur.execute("""
                UPDATE attendance
                SET out_time = ?, photo_path = CASE
                        WHEN photo_path IS NULL OR photo_path = '' THEN ?
                        ELSE photo_path || ',' || ?
                    END,
                    latitude = ?, longitude = ?, action='out'
                WHERE id = ?
            """, (timestamp, photo_paths_str, photo_paths_str, lat, lon, in_row['id']))
            conn.commit()
            message = f"Punched OUT at {timestamp}"
        else:
            cur.execute("""
                INSERT INTO attendance (
                    employee_id, timestamp, action, location, subject,
                    photo_path, latitude, longitude, out_time, shift_hours
                ) VALUES (?, ?, 'out', ?, ?, ?, ?, ?, ?, ?)
            """, (employee_id, timestamp, full_location, subject,
                  photo_paths_str, lat, lon, timestamp, emp_shift_hours))
            conn.commit()
            message = f"Punched OUT (no matching IN) at {timestamp}"

        cur.execute("SELECT id, name, email FROM employees WHERE id=?", (employee_id,))
        emp = cur.fetchone()
        async_send_email(emp, action, timestamp, lat, lon, saved_filenames)
        async_send_telegram(emp, action, timestamp, lat, lon, saved_filenames)
        conn.close()
        return jsonify({"status": "success", "message": message})

    else:
        conn.close()
        return jsonify({"status": "error", "message": "Invalid action"})

# ============================
# API: Attendance Records
# ============================
@app.route('/api/attendance-records', methods=['GET'])
def api_attendance_records():
    if 'username' not in session:
        return jsonify({"status": "error", "message": "Not logged in"}), 401

    employee_id = get_employee_id(session['username'])
    if not employee_id:
        return jsonify({"status": "error", "message": "Invalid employee"}), 400

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT action, timestamp, latitude, longitude, location
        FROM attendance
        WHERE employee_id = ?
        ORDER BY timestamp DESC
        LIMIT 200
    """, (employee_id,))
    rows = cur.fetchall()
    conn.close()

    records = []
    for r in rows:
        location = r['location'] or ''
        if not location and r['latitude'] and r['longitude']:
            location = f"{r['latitude']},{r['longitude']}"
        records.append({
            "action": r["action"],
            "timestamp": r["timestamp"],
            "location": location
        })
    return jsonify({"status": "ok", "records": records})


def ensure_expenses_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER,
            title TEXT,
            amount REAL,
            expense_date TEXT,
            description TEXT,
            bill_photo TEXT,
            status TEXT DEFAULT 'Pending',
            rejection_comment TEXT,
            submitted_on TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

def ensure_advance_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS advance_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER,
            request_date TEXT,
            amount REAL,
            reason TEXT,
            status TEXT DEFAULT 'Pending',
            admin_comment TEXT
        )
    """)

# ============================
# API: Expenses
# ============================
@app.route('/api/expenses', methods=['GET', 'POST'])
def api_expenses():
    if 'username' not in session:
        return jsonify({"status": "error", "message": "Not logged in"}), 401

    employee_id = get_employee_id(session['username'])
    if not employee_id:
        return jsonify({"status": "error", "message": "Invalid employee"}), 400

    conn = get_db_connection()
    ensure_expenses_table(conn)
    cur = conn.cursor()

    if request.method == 'POST':
        if request.is_json:
            data = request.get_json() or {}
            title = (data.get('title') or '').strip()
            amount = (data.get('amount') or '').strip()
            expense_date = (data.get('expense_date') or '').strip()
            description = (data.get('description') or '').strip()
            photo_b64 = data.get('photo')
            file = None
        else:
            title = (request.form.get('title') or '').strip()
            amount = (request.form.get('amount') or '').strip()
            expense_date = (request.form.get('expense_date') or '').strip()
            description = (request.form.get('description') or '').strip()
            photo_b64 = None
            file = request.files.get('photo')

        if not title or not amount or not expense_date:
            conn.close()
            return jsonify({"status": "error", "message": "Title, amount, and date required"}), 400

        try:
            amount_val = float(amount)
        except Exception:
            conn.close()
            return jsonify({"status": "error", "message": "Invalid amount"}), 400

        bill_photo = None
        bill_folder = os.path.join('static', 'expense_bills')
        os.makedirs(bill_folder, exist_ok=True)

        if file and file.filename:
            filename = datetime.now().strftime("%Y%m%d_%H%M%S_") + secure_filename(file.filename)
            path = os.path.join(bill_folder, filename)
            file.save(path)
            bill_photo = path
        elif photo_b64:
            try:
                if ',' in photo_b64:
                    photo_b64 = photo_b64.split(',', 1)[1]
                photo_binary = base64.b64decode(photo_b64)
                filename = datetime.now().strftime("%Y%m%d_%H%M%S_") + "bill.jpg"
                path = os.path.join(bill_folder, filename)
                with open(path, 'wb') as f:
                    f.write(photo_binary)
                bill_photo = path
            except Exception:
                conn.close()
                return jsonify({"status": "error", "message": "Invalid photo data"}), 400

        cur.execute("""
            INSERT INTO expenses (employee_id, title, amount, expense_date, description, bill_photo)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (employee_id, title, amount_val, expense_date, description, bill_photo))
        conn.commit()
        conn.close()
        return jsonify({"status": "ok", "message": "Expense submitted"})

    cur.execute("""
        SELECT id, title, amount, expense_date, description, status, rejection_comment, submitted_on, bill_photo
        FROM expenses
        WHERE employee_id = ?
        ORDER BY submitted_on DESC
    """, (employee_id,))
    rows = cur.fetchall()
    conn.close()

    expenses = []
    for r in rows:
        expenses.append({
            "id": r["id"],
            "title": r["title"],
            "amount": r["amount"],
            "expense_date": r["expense_date"],
            "description": r["description"],
            "status": r["status"],
            "rejection_comment": r["rejection_comment"],
            "submitted_on": r["submitted_on"],
            "bill_photo": r["bill_photo"]
        })
    return jsonify({"status": "ok", "expenses": expenses})

# ============================
# API: Advance Requests
# ============================
@app.route('/api/advance', methods=['GET', 'POST'])
def api_advance():
    if 'username' not in session:
        return jsonify({"status": "error", "message": "Not logged in"}), 401

    employee_id = get_employee_id(session['username'])
    if not employee_id:
        return jsonify({"status": "error", "message": "Invalid employee"}), 400

    conn = get_db_connection()
    ensure_advance_table(conn)
    cur = conn.cursor()

    cur.execute("SELECT name, per_hour_salary, shift_hours FROM employees WHERE id = ?", (employee_id,))
    employee = cur.fetchone()
    per_hour_salary = float(employee['per_hour_salary'] or 0) if employee else 0
    shift_hours = float(employee['shift_hours'] or 0) if employee else 0
    monthly_salary = round(per_hour_salary * shift_hours * 30, 2)
    max_request = int(monthly_salary * 0.40)

    if request.method == 'POST':
        data = request.get_json() or {}
        amount_raw = (data.get('amount') or '').strip()
        reason = (data.get('reason') or '').strip()
        request_date = datetime.now().strftime('%Y-%m-%d')

        if not amount_raw or not reason:
            conn.close()
            return jsonify({"status": "error", "message": "Amount and reason required"}), 400

        try:
            amount = int(float(amount_raw))
        except Exception:
            conn.close()
            return jsonify({"status": "error", "message": "Invalid amount"}), 400

        if amount < 1 or amount > max_request:
            conn.close()
            return jsonify({"status": "error", "message": f"Max allowed is ₹{max_request}"}), 400

        cur.execute("""
            SELECT id FROM advance_requests
            WHERE employee_id = ? AND request_date = ?
        """, (employee_id, request_date))
        if cur.fetchone():
            conn.close()
            return jsonify({"status": "error", "message": "Already requested today"}), 400

        cur.execute("""
            INSERT INTO advance_requests (employee_id, request_date, amount, reason)
            VALUES (?, ?, ?, ?)
        """, (employee_id, request_date, amount, reason))
        conn.commit()
        conn.close()
        return jsonify({"status": "ok", "message": "Advance request submitted"})

    cur.execute("""
        SELECT request_date, amount, status, admin_comment
        FROM advance_requests
        WHERE employee_id = ?
        ORDER BY request_date DESC
    """, (employee_id,))
    rows = cur.fetchall()
    conn.close()

    requests_out = []
    for r in rows:
        requests_out.append({
            "request_date": r["request_date"],
            "amount": r["amount"],
            "status": r["status"],
            "admin_comment": r["admin_comment"]
        })
    return jsonify({"status": "ok", "requests": requests_out, "max_request": max_request})

@app.route('/admin/view_attendance/<int:id>')
@admin_login_required
def view_employee_attendance(id):
    from datetime import datetime as dt
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT * FROM employees WHERE id = ?", (id,))
    employee = cur.fetchone()
    if not employee:
        conn.close()
        return "Employee not found", 404

    month = int(request.args.get("month", datetime.now().month))
    year = int(request.args.get("year", datetime.now().year))
    start_date = f"{year}-{month:02d}-01"
    last_day = calendar.monthrange(year, month)[1]
    end_date = f"{year}-{month:02d}-{last_day:02d}"

    cur.execute("""
        SELECT * FROM attendance
        WHERE employee_id = ?
          AND date(timestamp) BETWEEN ? AND ?
        ORDER BY timestamp DESC
    """, (id, start_date, end_date))
    all_records = cur.fetchall()

    total_in = sum(1 for r in all_records if r['action'] == 'in')
    total_out = sum(1 for r in all_records if r['action'] == 'out')
    summary = {'total_in': total_in, 'total_out': total_out}

    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 10))
    total_pages = max((len(all_records) + per_page - 1) // per_page, 1)
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    records = all_records[start_idx:end_idx]

    # Enhance each record for template (date strings, map URLs, photo list)
    MAP_API_KEY = "AIzaSyATEg1ZhzpOctVA0swTsSoPc8ce5c1NG7U"
    out = []
    for rec in records:
        d = dict(rec)
        d['display_date'] = '—'
        d['in_time_only'] = None
        d['out_time_only'] = None
        d['work_hours'] = '—'
        try:
            ts = dt.strptime(d['timestamp'], '%Y-%m-%d %H:%M:%S')
            d['display_date'] = ts.strftime('%a, %d %b %Y')
        except:
            pass
        if d.get('in_time'):
            d['in_time_only'] = d['in_time'].split(' ')[1] if ' ' in d['in_time'] else d['in_time']
        if d.get('out_time'):
            d['out_time_only'] = d['out_time'].split(' ')[1] if ' ' in d['out_time'] else d['out_time']
        if d.get('in_time') and d.get('out_time'):
            try:
                in_dt = dt.strptime(d['in_time'], '%Y-%m-%d %H:%M:%S')
                out_dt = dt.strptime(d['out_time'], '%Y-%m-%d %H:%M:%S')
                diff = out_dt - in_dt
                hours = diff.seconds // 3600
                minutes = (diff.seconds % 3600) // 60
                d['work_hours'] = f"{hours}h {minutes}m"
            except:
                pass
        if d.get('latitude') and d.get('longitude'):
            d['map_url'] = (
                f"https://maps.googleapis.com/maps/api/staticmap?"
                f"center={d['latitude']},{d['longitude']}&zoom=16&size=120x90"
                f"&markers=color:red%7C{d['latitude']},{d['longitude']}&key={MAP_API_KEY}"
            )
            d['full_map_url'] = f"https://www.google.com/maps?q={d['latitude']},{d['longitude']}"
        else:
            d['map_url'] = None
            d['full_map_url'] = None

        if d.get('photo_path') and d['photo_path'].strip():
            photos = [p.strip() for p in d['photo_path'].split(',') if p.strip()]
            d['photo_list'] = [p if p.startswith('uploads/') or p.startswith('static/') else f"uploads/{p.lstrip('/')}" for p in photos]
        else:
            d['photo_list'] = []
        out.append(d)

    conn.close()
    return render_template(
        "employee_attendance.html",
        employee=employee,
        records=out,
        summary=summary,
        page=page,
        total_pages=total_pages,
        per_page=per_page,
        selected_month=month,
        selected_year=year,
        now=datetime.now()
    )

# List + export records (employee view)


@app.route('/records')
def records():
    from datetime import datetime
    import os

    # Session check
    if 'username' not in session:
        return redirect(url_for('login'))

    employee_id = get_employee_id(session['username'])
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    # --- Database query ---
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    q = "SELECT * FROM attendance WHERE employee_id = ?"
    params = [employee_id]

    if start_date:
        q += " AND date(timestamp) >= ?"
        params.append(start_date)
    if end_date:
        q += " AND date(timestamp) <= ?"
        params.append(end_date)

    q += " ORDER BY timestamp DESC"
    rows = cur.execute(q, params).fetchall()

    # --- Counts ---
    qi = "SELECT COUNT(*) FROM attendance WHERE employee_id = ? AND action='in'"
    qo = "SELECT COUNT(*) FROM attendance WHERE employee_id = ? AND action='out'"
    ip, op = [employee_id], [employee_id]

    if start_date:
        qi += " AND date(timestamp) >= ?"; ip.append(start_date)
        qo += " AND date(timestamp) >= ?"; op.append(start_date)
    if end_date:
        qi += " AND date(timestamp) <= ?"; ip.append(end_date)
        qo += " AND date(timestamp) <= ?"; op.append(end_date)

    total_in = cur.execute(qi, ip).fetchone()[0]
    total_out = cur.execute(qo, op).fetchone()[0]
    conn.close()

    # --- Format records ---
    recs = []
    for r in rows:
        d = dict(r)
        try:
            d['dt_obj'] = datetime.strptime(d['timestamp'], '%Y-%m-%d %H:%M:%S')
        except Exception:
            d['dt_obj'] = datetime.now()
        recs.append(d)

    # --- Render Template ---
    return render_template(
        'records.html',
        records=recs,
        start_date=start_date or '',
        end_date=end_date or '',
        total_in=total_in,
        total_out=total_out,
        now=datetime.now(),
        current_month=datetime.now().month,      # ✅ Needed for month dropdown
        current_year=datetime.now().year,        # ✅ Needed for year dropdown
        google_maps_key=os.getenv("GOOGLE_MAPS_API_KEY", "")
    )


@app.route("/export_monthly_status_excel")
def export_monthly_status_excel():
    from io import BytesIO
    import pandas as pd, calendar
    from datetime import datetime, timedelta
    from collections import defaultdict

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # ----- 1. Get request parameters (default = current month) -----
    now   = datetime.now()
    month = int(request.args.get("month", now.month))
    year  = int(request.args.get("year",  now.year))
    days_in_month = calendar.monthrange(year, month)[1]

    # ----- 2. Load employees (working only) -----
    cur.execute("""
        SELECT mobile   AS emp_code,
               name     AS emp_name,
               COALESCE(in_time,  '09:00:00') AS shift_in,
               COALESCE(out_time, '18:00:00') AS shift_out,
               COALESCE(shift_hours, 9.0)    AS shift_hours
        FROM employees
        WHERE LOWER(status) = 'working'
        ORDER BY name
    """)
    employees = cur.fetchall()

    # ----- 3. Load **ALL** punches for the selected month (single query) -----
    cur.execute("""
        SELECT e.mobile      AS emp_code,
               a.timestamp,
               a.in_time,
               a.out_time
        FROM attendance a
        JOIN employees e ON a.employee_id = e.id
        WHERE strftime('%Y-%m', a.timestamp) = ?
        ORDER BY e.mobile, a.timestamp
    """, (f"{year}-{month:02d}",))
    punches = cur.fetchall()
    conn.close()

    # ----- 4. Group punches by employee → date → {in, out} -----
    grouped = defaultdict(lambda: defaultdict(dict))
    for p in punches:
        # timestamp format: "YYYY-MM-DD HH:MM:SS"
        date_part = p["timestamp"].split(" ")[0]
        emp = p["emp_code"]
        grouped[emp][date_part]["in"]  = grouped[emp][date_part].get("in")  or p["in_time"]
        grouped[emp][date_part]["out"] = grouped[emp][date_part].get("out") or p["out_time"]

    # ----- 5. Build Excel workbook -----
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine="xlsxwriter")
    workbook = writer.book

    header_fmt = workbook.add_format({
        "bold": True, "bg_color": "#E8EAF6", "border": 1, "align": "center"
    })
    cell_fmt   = workbook.add_format({"border": 1, "align": "center"})
    bold_fmt   = workbook.add_format({"bold": True, "border": 1})

    for emp in employees:
        emp_code = emp["emp_code"]
        emp_name = emp["emp_name"]
        try:
            shift_start = datetime.strptime(emp["shift_in"], "%H:%M:%S").time()
        except:
            shift_start = datetime.strptime("09:00:00", "%H:%M:%S").time()
        try:
            shift_end = datetime.strptime(emp["shift_out"], "%H:%M:%S").time()
        except:
            shift_end = datetime.strptime("18:00:00", "%H:%M:%S").time()

        # ----- Build per-day dict -----
        day_data = {}
        total_work   = timedelta()
        present_cnt  = 0

        for day in range(1, days_in_month + 1):
            date_key = f"{year}-{month:02d}-{day:02d}"
            rec = grouped[emp_code].get(date_key, {})

            in_str  = rec.get("in")  or ""
            out_str = rec.get("out") or ""

            # clean possible leading date part
            if in_str and " " in in_str:
                in_str = in_str.split(" ")[-1]
            if out_str and " " in out_str:
                out_str = out_str.split(" ")[-1]

            # ---- late / early notes ----
            in_note  = ""
            out_note = ""
            if in_str:
                try:
                    t_in = datetime.strptime(in_str, "%H:%M:%S").time()
                    if t_in > shift_start:
                        in_note = " (Late)"
                    elif t_in < shift_start:
                        in_note = " (Early)"
                except:
                    pass
            if out_str:
                try:
                    t_out = datetime.strptime(out_str, "%H:%M:%S").time()
                    if t_out < shift_end:
                        out_note = " (Early)"
                    elif t_out > shift_end:
                        out_note = " (Late)"
                except:
                    pass

            status = "P" if in_str else "A"
            hrs    = ""
            if in_str and out_str:
                try:
                    t1 = datetime.strptime(in_str, "%H:%M:%S")
                    t2 = datetime.strptime(out_str, "%H:%M:%S")
                    diff = t2 - t1
                    if diff.total_seconds() > 0:
                        hrs = str(diff).split('.')[0]          # HH:MM:SS
                        total_work += diff
                except:
                    pass

            if in_str:
                present_cnt += 1

            day_data[day] = {
                "in":   in_str  + in_note  if in_str else "",
                "out":  out_str + out_note if out_str else "",
                "status": status,
                "hrs":  hrs
            }

        # ----- DataFrame (5 rows) -----
        cols = ["Type"] + [f"{d:02d}" for d in range(1, days_in_month + 1)]
        df = pd.DataFrame(columns=cols)

        df.loc[len(df)] = ["In"]      + [day_data.get(d, {}).get("in", "")      for d in range(1, days_in_month + 1)]
        df.loc[len(df)] = ["Out"]     + [day_data.get(d, {}).get("out", "")     for d in range(1, days_in_month + 1)]
        df.loc[len(df)] = ["Status"]  + [day_data.get(d, {}).get("status", "A") for d in range(1, days_in_month + 1)]
        df.loc[len(df)] = ["Total Hrs"] + [day_data.get(d, {}).get("hrs", "")   for d in range(1, days_in_month + 1)]

        # ----- Summary rows -----
        summary = ["Summary"] + [""] * days_in_month
        summary[1] = f"Present: {present_cnt}"
        df.loc[len(df)] = summary

        total_h = ["Total Working Hours"] + [""] * days_in_month
        total_h[1] = str(total_work).split('.')[0]
        df.loc[len(df)] = total_h

        # ----- Write sheet -----
        sheet_name = (emp_name[:25]).replace("/", "_")
        df.to_excel(writer, sheet_name=sheet_name, index=False)
        ws = writer.sheets[sheet_name]

        # header info
        ws.write("A1", f"Emp. Code: {emp_code} Emp. Name: {emp_name}", bold_fmt)
        ws.write("A2", f"Month: {calendar.month_name[month]} {year}", bold_fmt)

        # column headers (row 3)
        for col, val in enumerate(df.columns):
            ws.write(3, col, val, header_fmt)

        # formatting
        ws.set_column(0, days_in_month, 13, cell_fmt)
        ws.write(f"A{len(df)+6}", "Generated by 360 Vision", bold_fmt)

    writer.close()
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name=f"Monthly_Status_{month:02d}_{year}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
@app.route("/export_monthly_status_pdf")
def export_monthly_status_pdf():
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
    )
    from reportlab.lib.pagesizes import landscape, A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from io import BytesIO
    from datetime import datetime, timedelta
    import calendar
    from collections import defaultdict

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    now = datetime.now()
    month = int(request.args.get("month", now.month))
    year = int(request.args.get("year", now.year))
    days_in_month = calendar.monthrange(year, month)[1]

    # ✅ Fetch only active employees
    cur.execute("""
        SELECT 
            mobile AS emp_code,
            name AS emp_name,
            COALESCE(in_time, '09:00:00') AS shift_in,
            COALESCE(out_time, '18:00:00') AS shift_out,
            COALESCE(shift_hours, 9.0) AS shift_hours
        FROM employees
        WHERE LOWER(status) = 'working'
        ORDER BY name
    """)
    employees = cur.fetchall()

    # ✅ Fetch attendance records
    cur.execute("""
        SELECT 
            e.mobile AS emp_code,
            e.name AS emp_name,
            a.timestamp,
            a.in_time,
            a.out_time
        FROM attendance a
        JOIN employees e ON a.employee_id = e.id
        ORDER BY e.name, a.timestamp
    """)
    rows = cur.fetchall()
    conn.close()

    # ✅ Group by employee/date
    grouped = defaultdict(lambda: defaultdict(list))
    for r in rows:
        ts = r["timestamp"]
        if not ts:
            continue
        ts = ts.replace("/", "-")
        date_part = ts.split(" ")[0]
        try:
            dt = datetime.strptime(date_part, "%Y-%m-%d")
        except:
            continue
        if dt.year == year and dt.month == month:
            grouped[r["emp_code"]][date_part].append({
                "in": r["in_time"],
                "out": r["out_time"]
            })

    # ✅ Prepare PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4))
    story = []
    styles = getSampleStyleSheet()

    for idx, emp in enumerate(employees):
        emp_code = emp["emp_code"]
        emp_name = emp["emp_name"]

        # Shift start and end
        try:
            shift_start = datetime.strptime(emp["shift_in"], "%H:%M")
        except:
            shift_start = datetime.strptime("09:00", "%H:%M")
        try:
            shift_end = shift_start + timedelta(hours=float(emp["shift_hours"]))
        except:
            shift_end = datetime.strptime("18:00", "%H:%M")

        emp_days = {}
        total_work = timedelta()
        total_present = 0

        for day in range(1, days_in_month + 1):
            date_key = f"{year}-{month:02d}-{day:02d}"
            punches = grouped.get(emp_code, {}).get(date_key, [])
            if not punches:
                emp_days[day] = {"in": "", "out": "", "status": "A", "total": ""}
                continue

            ins = [p["in"] for p in punches if p["in"]]
            outs = [p["out"] for p in punches if p["out"]]
            first_in = min(ins) if ins else ""
            last_out = max(outs) if outs else ""

            note_in = note_out = ""
            if first_in:
                try:
                    t_in = datetime.strptime(first_in, "%H:%M:%S")
                    if t_in > shift_start:
                        note_in = " (Late)"
                    elif t_in < shift_start:
                        note_in = " (Early)"
                except:
                    pass

            if last_out:
                try:
                    t_out = datetime.strptime(last_out, "%H:%M:%S")
                    if t_out < shift_end:
                        note_out = " (Early)"
                    elif t_out > shift_end:
                        note_out = " (Late)"
                except:
                    pass

            status = "P" if first_in else "A"
            total_hrs = ""
            if first_in and last_out:
                try:
                    t1 = datetime.strptime(first_in, "%H:%M:%S")
                    t2 = datetime.strptime(last_out, "%H:%M:%S")
                    diff = t2 - t1
                    if diff.total_seconds() > 0:
                        total_hrs = str(diff)
                        total_work += diff
                except:
                    pass
            if first_in:
                total_present += 1

            emp_days[day] = {
                "in": first_in + note_in if first_in else "",
                "out": last_out + note_out if last_out else "",
                "status": status,
                "total": total_hrs
            }

        # ✅ Create table data
        header = ["Type"] + [f"{d:02d}" for d in range(1, days_in_month + 1)]
        table_data = [header]
        table_data.append(["In"] + [emp_days[d]["in"] for d in range(1, days_in_month + 1)])
        table_data.append(["Out"] + [emp_days[d]["out"] for d in range(1, days_in_month + 1)])
        table_data.append(["Status"] + [emp_days[d]["status"] for d in range(1, days_in_month + 1)])
        table_data.append(["Total Hrs"] + [emp_days[d]["total"] for d in range(1, days_in_month + 1)])

        summary_row = ["Summary"] + ["" for _ in range(days_in_month)]
        summary_row[1] = f"Present: {total_present}"
        total_row = ["Total Working Hours"] + ["" for _ in range(days_in_month)]
        total_row[1] = str(total_work)
        table_data.append(summary_row)
        table_data.append(total_row)

        # ✅ Add content
        story.append(Paragraph(f"<b>Emp. Code:</b> {emp_code} &nbsp;&nbsp;&nbsp; <b>Emp. Name:</b> {emp_name}", styles["Normal"]))
        story.append(Paragraph(f"<b>Month:</b> {calendar.month_name[month]} {year}", styles["Normal"]))
        story.append(Spacer(1, 6))

        t = Table(table_data, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(t)
        story.append(Spacer(1, 10))
        story.append(Paragraph("<i>Generated by 360 Vision</i>", styles["Italic"]))

        if idx < len(employees) - 1:
            story.append(PageBreak())

    doc.build(story)
    buffer.seek(0)
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"Monthly_Status_{month:02d}_{year}.pdf",
        mimetype="application/pdf"
    )


# ------------------ Employee Attendance Records ------------------
@app.route('/employee_attendance_records')
@admin_login_required
def employee_attendance_records():
    import re
    from datetime import datetime, date
    from collections import defaultdict

    def to_static_rel(path: str, default_rel: str = "") -> str:
        if not path:
            return default_rel
        p = str(path).replace("\\", "/").strip().lstrip("/")
        if p.lower().startswith("static/"):
            p = p[7:]
        return p or default_rel

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # --- Get selected date (or today) ---
    selected_date_str = request.args.get("date")
    if selected_date_str:
        try:
            selected_date = datetime.strptime(selected_date_str, "%Y-%m-%d").date()
        except:
            selected_date = date.today()
    else:
        selected_date = date.today()
    selected_date_str = selected_date.strftime("%Y-%m-%d")

    # --- Search ---
    search = request.args.get("search", "").strip()
    where = "WHERE DATE(a.timestamp) = ?"
    params = [selected_date_str]
    if search:
        where += " AND (e.name LIKE ? OR e.mobile LIKE ?)"
        params += [f"%{search}%", f"%{search}%"]

    # --- Fetch punches ---
    cur.execute(f"""
        SELECT
            a.id,
            e.name AS employee_name,
            e.mobile,
            e.employee_photo,
            a.in_time,
            a.out_time,
            a.latitude,
            a.longitude,
            a.photo_path
        FROM attendance a
        JOIN employees e ON a.employee_id = e.id
        {where}
        ORDER BY a.timestamp DESC
    """, params)
    rows = [dict(r) for r in cur.fetchall()]

    # --- Group by employee ---
    grouped = defaultdict(lambda: {"in": None, "out": None, "row": None})
    for r in rows:
        emp_id = r["id"]
        if r["in_time"] and not grouped[emp_id]["in"]:
            grouped[emp_id]["in"] = r["in_time"]
            grouped[emp_id]["row"] = r
        if r["out_time"]:
            grouped[emp_id]["out"] = r["out_time"]
            grouped[emp_id]["row"] = r

    # --- Build output ---
    out = []
    seen = set()

    for emp_id, data in grouped.items():
        seen.add(emp_id)
        row = data["row"]
        in_str = (data["in"] or "").split(" ")[-1] if data["in"] else ""
        out_str = (data["out"] or "").split(" ")[-1] if data["out"] else ""

        work_hours = "—"
        if in_str and out_str:
            try:
                t1 = datetime.strptime(in_str, "%H:%M:%S")
                t2 = datetime.strptime(out_str, "%H:%M:%S")
                diff = t2 - t1
                if diff.total_seconds() >= 0:
                    work_hours = str(diff).split('.')[0]
            except:
                pass

        att_rel = "default_attendance.png"
        if row.get("photo_path"):
            photos = [p.strip() for p in row["photo_path"].split(",") if p.strip()]
            if photos:
                att_rel = to_static_rel(photos[0], "default_attendance.png")

        full_map_url = f"https://www.google.com/maps?q={row.get('latitude')},{row.get('longitude')}" \
                       if row.get('latitude') and row.get('longitude') else ""

        mobile_clean = re.sub(r"\D", "", row["mobile"])[-10:]

        out.append({
            "id": row["id"],
            "employee_name": row["employee_name"],
            "mobile": row["mobile"],
            "mobile_clean": mobile_clean,
            "emp_photo_clean": to_static_rel(row["employee_photo"], "default_employee.png"),
            "att_photo_clean": att_rel,
            "in_time_only": in_str or "—",
            "out_time_only": out_str or "—",
            "work_hours": work_hours,
            "latitude": row.get("latitude"),
            "longitude": row.get("longitude"),
            "date_only": selected_date_str,
            "full_map_url": full_map_url,
        })

    # --- Add absent employees ---
    cur.execute("SELECT id, name, mobile, employee_photo FROM employees WHERE LOWER(status) = 'working'")
    all_emps = cur.fetchall()
    for emp in all_emps:
        emp_id = emp["id"]
        if emp_id in seen:
            continue
        out.append({
            "id": "",
            "employee_name": emp["name"],
            "mobile": emp["mobile"],
            "mobile_clean": re.sub(r"\D", "", emp["mobile"])[-10:],
            "emp_photo_clean": to_static_rel(emp["employee_photo"], "default_employee.png"),
            "att_photo_clean": "default_attendance.png",
            "in_time_only": "—",
            "out_time_only": "—",
            "work_hours": "—",
            "latitude": None,
            "longitude": None,
            "date_only": selected_date_str,
            "full_map_url": "",
        })

    conn.close()

    is_live = (selected_date == date.today())

    return render_template(
        "employee_attendance_records.html",
        records=out,
        selected_date=selected_date_str,
        is_live=is_live
    )
    
@app.route('/api/search_employees')
def api_search_employees():
    query = request.args.get('q', '').strip()
    month = request.args.get('month')
    year = request.args.get('year')
    
    if not query:
        return jsonify([])

    conn = get_db_connection()
    cur = conn.cursor()
    
    # Search in employees (name or mobile)
    sql = """
        SELECT id, name, mobile 
        FROM employees 
        WHERE name LIKE ? OR mobile LIKE ?
        ORDER BY name
        LIMIT 10
    """
    like_query = f"%{query}%"
    cur.execute(sql, (like_query, like_query))
    rows = cur.fetchall()
    conn.close()

    results = []
    for r in rows:
        results.append({
            'id': r['id'],
            'name': r['name'],
            'mobile': r['mobile']
        })
    
    return jsonify(results)
    
@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    
@app.route('/employee_attendance_dashboard')
@admin_login_required
def employee_attendance_dashboard():
    import calendar
    from datetime import datetime
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 🔹 Filters
    month = int(request.args.get('month', datetime.now().month))
    year = int(request.args.get('year', datetime.now().year))
    search = request.args.get('search', '').strip()

    # 🔹 Date range
    start_date = f"{year}-{month:02d}-01"
    last_day = calendar.monthrange(year, month)[1]
    end_date = f"{year}-{month:02d}-{last_day:02d}"

    # 🔹 Fetch all attendance records (no pagination)
    if search:
        cur.execute("""
            SELECT e.name AS employee_name, e.employee_photo,
                   a.timestamp, a.in_time, a.out_time,
                   a.latitude, a.longitude, a.photo_path
            FROM attendance a
            JOIN employees e ON a.employee_id = e.id
            WHERE date(a.timestamp) BETWEEN ? AND ?
              AND e.name LIKE ?
            ORDER BY e.name, a.timestamp DESC
        """, (start_date, end_date, f"%{search}%"))
    else:
        cur.execute("""
            SELECT e.name AS employee_name, e.employee_photo,
                   a.timestamp, a.in_time, a.out_time,
                   a.latitude, a.longitude, a.photo_path
            FROM attendance a
            JOIN employees e ON a.employee_id = e.id
            WHERE date(a.timestamp) BETWEEN ? AND ?
            ORDER BY e.name, a.timestamp DESC
        """, (start_date, end_date))

    records = cur.fetchall()

    # 🔹 Totals for header
    cur.execute("SELECT COUNT(DISTINCT e.mobile) FROM employees e")
    total_employees = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*) FROM attendance a
       JOIN employees e ON a.employee_id = e.id
        WHERE date(a.timestamp) BETWEEN ? AND ?
    """, (start_date, end_date))
    total_records = cur.fetchone()[0]

    conn.close()

    # 🔹 Group data by employee → date → punches
    grouped = {}
    for r in records:
        emp = r['employee_name']
        date_str = r['timestamp'][:10]
        if emp not in grouped:
            grouped[emp] = {}
        if date_str not in grouped[emp]:
            grouped[emp][date_str] = []
        grouped[emp][date_str].append(r)

    # 🔹 Render final template
    return render_template(
        'employee_attendance_dashboard.html',
        grouped_records=grouped,
        month=month,
        year=year,
        month_name=calendar.month_name[month],
        current_year=datetime.now().year,
        total_employees=total_employees,
        total_records=total_records,
        search=search,
        calendar=calendar  # ✅ Pass calendar to fix template error
    )

# =================================================
# Admin — Attendance Records table & export
# =================================================


@app.route('/admin_records/export')
@admin_login_required
def export_admin_records():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    search_name = request.args.get('search_name')

    conn = get_db_connection()
    cur = conn.cursor()
    q = """
        SELECT e.name, e.mobile, a.in_time, a.out_time, a.timestamp
        FROM attendance a
        JOIN employees e ON a.employee_id = e.id
        WHERE 1=1
    """
    params = []
    if start_date:
        q += " AND DATE(a.timestamp) >= ?"; params.append(start_date)
    if end_date:
        q += " AND DATE(a.timestamp) <= ?"; params.append(end_date)
    if search_name:
        q += " AND e.name LIKE ?"; params.append(f"%{search_name}%")
    q += " ORDER BY a.timestamp DESC"
    data = cur.execute(q, params).fetchall()
    conn.close()

    df = pd.DataFrame(data)
    out_path = os.path.join(BASE_DIR, "static/attendance_export.xlsx")
    df.to_excel(out_path, index=False)
    return send_file(out_path, as_attachment=True)

# =================================================
# Expenses
# =================================================
@app.route('/expenses', methods=['GET', 'POST'])
def submit_expense():
    if 'username' not in session:
        return redirect(url_for('login'))
    employee_id = get_employee_id(session['username'])

    if request.method == 'POST':
        try:
            titles = request.form.getlist('title[]')
            custom_titles = request.form.getlist('custom_title[]')
            amounts = request.form.getlist('amount[]')
            dates = request.form.getlist('expense_date[]')
            descriptions = request.form.getlist('description[]')
            bills = request.files.getlist('bill_photo[]')

            bill_folder = os.path.join('static', 'expense_bills')
            os.makedirs(bill_folder, exist_ok=True)

            conn = get_db_connection()
            for i in range(len(titles)):
                title = titles[i]
                if title == 'Miscellaneous':
                    title = custom_titles[i] or 'Miscellaneous'
                filename = secure_filename(bills[i].filename) if bills and bills[i] else ''
                bill_path = os.path.join(bill_folder, filename) if filename else ''
                if filename:
                    bills[i].save(bill_path)

                conn.execute("""
                    INSERT INTO expenses (employee_id, title, amount, expense_date, description, bill_photo)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (employee_id, title, amounts[i], dates[i], descriptions[i], bill_path))
            conn.commit()
            conn.close()
            return render_template('expenses.html', success="Expenses submitted successfully!")
        except Exception as e:
            return render_template('expenses.html', error=str(e))

    return render_template('expenses.html')

@app.route('/my_expenses', methods=['GET', 'POST'])
def my_expenses():
    if 'username' not in session:
        return redirect(url_for('login'))
    employee_id = get_employee_id(session['username'])

    q = "SELECT * FROM expenses WHERE employee_id = ?"
    params = [employee_id]
    if request.method == 'POST':
        month = (request.form.get('month') or '').zfill(2)
        year = request.form.get('year')
        date_from = request.form.get('date_from')
        date_to = request.form.get('date_to')
        if month and year:
            q += " AND strftime('%m', expense_date) = ? AND strftime('%Y', expense_date) = ?"
            params += [month, year]
        elif date_from and date_to:
            q += " AND expense_date BETWEEN ? AND ?"
            params += [date_from, date_to]
    q += " ORDER BY submitted_on DESC"

    conn = get_db_connection()
    expenses = conn.execute(q, params).fetchall()
    conn.close()
    return render_template('my_expenses.html', expenses=expenses)

@app.route('/export_expenses')
def export_expenses():
    if 'username' not in session:
        return redirect(url_for('login'))
    employee_id = get_employee_id(session['username'])
    conn = get_db_connection()
    df = pd.read_sql_query("""
        SELECT title, amount, expense_date, description, status
        FROM expenses WHERE employee_id = ? ORDER BY submitted_on DESC
    """, conn, params=(employee_id,))
    conn.close()
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    df.to_excel(writer, sheet_name='Expenses', index=False)
    writer.close()
    output.seek(0)
    return send_file(output, download_name="my_expenses.xlsx", as_attachment=True)

@app.route('/admin/expenses')
@admin_login_required
def admin_expenses():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT e.*, emp.name FROM expenses e
        JOIN employees emp ON e.employee_id = emp.id
        ORDER BY e.submitted_on DESC
    """)
    expenses = cur.fetchall()
    conn.close()
    return render_template('admin_expenses.html', expenses=expenses)

@app.route('/admin/expense_action', methods=['POST'])
@admin_login_required
def expense_action():
    expense_id = request.form['expense_id']
    action = request.form['action']
    comment = request.form.get('rejection_comment', '')
    conn = get_db_connection()
    if action == 'Rejected':
        conn.execute("UPDATE expenses SET status=?, rejection_comment=? WHERE id=?", (action, comment, expense_id))
    else:
        conn.execute("UPDATE expenses SET status=?, rejection_comment='' WHERE id=?", (action, expense_id))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_expenses'))

@app.route('/create_expenses_table')
def create_expenses_table():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER,
            title TEXT,
            amount REAL,
            expense_date TEXT,
            description TEXT,
            bill_photo TEXT,
            status TEXT DEFAULT 'Pending',
            rejection_comment TEXT,
            submitted_on TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()
    return "✅ Expenses table created!"

# =================================================
# Advance Salary
# =================================================
@app.route('/request_advance', methods=['GET', 'POST'])
def request_advance():
    if 'username' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()

    employee_id = get_employee_id(session['username'])

    # ─── Fetch employee details ───────────────────────────────────────────────
    cur.execute("""
        SELECT name, per_hour_salary, shift_hours
        FROM employees
        WHERE id = ?
    """, (employee_id,))
    employee = cur.fetchone()

    if not employee:
        conn.close()
        flash("Employee not found.", "danger")
        return redirect(url_for('attendance'))

    name = employee['name']

    try:
        per_hour_salary = float(employee['per_hour_salary'] or 0)
        shift_hours = float(employee['shift_hours'] or 0)
    except:
        per_hour_salary = 0
        shift_hours = 0

    # ─── Salary & limits ──────────────────────────────────────────────────────
    monthly_salary = round(per_hour_salary * shift_hours * 30, 2)
    max_request = int(monthly_salary * 0.40)   # 40% advance
    can_request = max_request >= 1

    # ─── POST: Submit advance request ─────────────────────────────────────────
    if request.method == 'POST':

        if not can_request:
            flash("Advance request not allowed. Salary not configured. Contact admin.", "danger")
            conn.close()
            return redirect(url_for('request_advance'))

        amount_raw = request.form.get('amount', '').strip()
        reason = request.form.get('reason', '').strip()
        request_date = datetime.now().strftime('%Y-%m-%d')

        if not amount_raw or not reason:
            flash("Please fill all fields.", "danger")
            conn.close()
            return redirect(url_for('request_advance'))

        try:
            amount = int(float(amount_raw))
        except:
            flash("Amount must be a valid number.", "danger")
            conn.close()
            return redirect(url_for('request_advance'))

        if amount < 1 or amount > max_request:
            flash(f"You can request between ₹1 and ₹{max_request} only.", "danger")
            conn.close()
            return redirect(url_for('request_advance'))

        # ─── Prevent duplicate same-day request ────────────────────────────────
        cur.execute("""
            SELECT id FROM advance_requests
            WHERE employee_id = ? AND request_date = ?
        """, (employee_id, request_date))

        if cur.fetchone():
            flash("You have already submitted an advance request today.", "warning")
            conn.close()
            return redirect(url_for('request_advance'))

        # ─── Insert request ────────────────────────────────────────────────────
        cur.execute("""
            INSERT INTO advance_requests (employee_id, request_date, amount, reason)
            VALUES (?, ?, ?, ?)
        """, (employee_id, request_date, amount, reason))

        conn.commit()

        # ─── Email admin ───────────────────────────────────────────────────────
        try:
            sender = SMTP_USER
            receiver = "info@connectingpoint.in"

            subject = "New Advance Salary Request"
            body = f"""
New advance salary request received.

Employee ID   : {employee_id}
Employee Name : {name}
Monthly Salary: ₹{monthly_salary}
Max Allowed   : ₹{max_request}
Requested     : ₹{amount}

Reason:
{reason}

Date: {request_date}
"""

            msg = MIMEText(body)
            msg["Subject"] = subject
            msg["From"] = sender
            msg["To"] = receiver

            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
            server.starttls()
            server.login(sender, SMTP_PASSWORD)
            server.send_message(msg)
            server.quit()
        except Exception as e:
            print("Admin email failed:", e)

        flash("Advance request submitted successfully.", "success")
        conn.close()
        return redirect(url_for('request_advance'))

    # ─── Fetch past requests ──────────────────────────────────────────────────
    cur.execute("""
        SELECT request_date, amount, status, admin_comment
        FROM advance_requests
        WHERE employee_id = ?
        ORDER BY request_date DESC
    """, (employee_id,))
    rows = cur.fetchall()

    past_requests = []
    for r in rows:
        try:
            fdate = datetime.strptime(r['request_date'], "%Y-%m-%d").strftime("%d %b %Y")
        except:
            fdate = r['request_date']

        past_requests.append({
            "request_date": fdate,
            "amount": r["amount"],
            "status": r["status"],
            "admin_comment": r["admin_comment"]
        })

    conn.close()

    return render_template(
        "request_advance.html",
        employee_id=employee_id,
        monthly_salary=monthly_salary,
        max_request=max_request,
        can_request=can_request,
        past_requests=past_requests
    )


@app.route('/admin/advance_requests')
@admin_login_required
def admin_advance_requests():
    employee_id = request.args.get('employee_id')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    status_filter = request.args.get('status')

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM employees")
    employees = cur.fetchall()

    q = """
        SELECT ar.*, e.name FROM advance_requests ar
        JOIN employees e ON ar.employee_id = e.id
        WHERE 1=1
    """
    params = []
    if employee_id:
        q += " AND ar.employee_id = ?"; params.append(employee_id)
    if start_date:
        q += " AND ar.request_date >= ?"; params.append(start_date)
    if end_date:
        q += " AND ar.request_date <= ?"; params.append(end_date)
    if status_filter:
        q += " AND ar.status = ?"; params.append(status_filter)
    q += " ORDER BY ar.request_date DESC"
    reqs = cur.execute(q, params).fetchall()
    conn.close()

    return render_template('admin_advance_requests.html',
                           requests=reqs, employees=employees,
                           selected_employee_id=employee_id,
                           start_date=start_date, end_date=end_date,
                           selected_status=status_filter)

@app.route('/admin/advance_requests/<int:id>', methods=['POST'])
@admin_login_required
def update_advance_request(id):
    status = request.form.get('status')
    comment = (request.form.get('admin_comment') or '').strip()
    if status not in ['Approved', 'Rejected']:
        flash("Invalid status selected.", "danger")
        return redirect(url_for('admin_advance_requests'))

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE advance_requests SET status=?, admin_comment=? WHERE id=?", (status, comment, id))
    conn.commit()
    conn.close()
    flash(f"Request updated as {status}.", "success")
    return redirect(url_for('admin_advance_requests'))

@app.route('/advance_history')
def advance_history():
    if 'username' not in session:
        return redirect(url_for('login'))
    emp_id = get_employee_id(session['username'])
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM advance_requests WHERE employee_id=? ORDER BY request_date DESC", (emp_id,))
    records = cur.fetchall()
    conn.close()
    return render_template('advance_history.html', records=records)

# =================================================
# Payroll
# =================================================
@app.route('/payroll')
@admin_login_required
def payroll_index():
    conn = get_db_connection()
    show_all = request.args.get('show') == 'all'
    if show_all:
        employees = conn.execute("SELECT * FROM employees").fetchall()
    else:
        employees = conn.execute("""
            SELECT * FROM employees
            WHERE status='Working' OR status IS NULL OR TRIM(status) = ''
        """).fetchall()
    conn.close()

    page = int(request.args.get('page', 1))
    per_page = 20
    total_pages = (len(employees) + per_page - 1) // per_page
    start = (page - 1) * per_page
    end = start + per_page
    employees_to_display = employees[start:end]

    return render_template('payroll_index.html',
                           employees_to_display=employees_to_display,
                           employees=employees,
                           page=page,
                           total_pages=total_pages,
                           show_all=show_all)

@app.route('/payroll/<int:employee_id>', methods=['GET', 'POST'])
@admin_login_required
def view_payroll(employee_id):
    today = datetime.today()
    default_start = today.replace(day=1).strftime('%Y-%m-%d')
    default_end = today.strftime('%Y-%m-%d')

    # --- Handle POST (Export Excel) ---
    if request.method == 'POST' and 'export_excel' in request.form:
        start_date = request.form.get('start_date', default_start)
        end_date = request.form.get('end_date', default_end)
        return export_payroll_excel(employee_id, start_date, end_date)

    # --- Filters (GET or POST) ---
    start_date = request.form.get('start_date') or request.args.get('start_date', default_start)
    end_date = request.form.get('end_date') or request.args.get('end_date', default_end)

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM employees WHERE id=? AND status='Working'", (employee_id,))
    emp_data = cur.fetchone()
    conn.close()

    if not emp_data:
        flash("This employee is not marked as 'Working'.", "danger")
        return redirect(url_for('payroll_index'))

    emp = dict(emp_data)

    # --- Totals for Expenses & Advances ---
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE employee_id=? AND expense_date BETWEEN ? AND ?", 
                (employee_id, start_date, end_date))
    total_expense = cur.fetchone()[0]

    cur.execute("SELECT COALESCE(SUM(amount), 0) FROM advance_requests WHERE employee_id=? AND request_date BETWEEN ? AND ?", 
                (employee_id, start_date, end_date))
    total_advance = cur.fetchone()[0]
    conn.close()

    # --- Calculate Payroll ---
    records, total_salary, total_ot_pay = calculate_payroll_records(emp, start_date, end_date)

    # --- Summary Counts ---
    total_present = sum(1 for r in records if r['status'] == 'Present')
    total_absent = sum(1 for r in records if r['status'] == 'Absent')
    total_half_day = sum(1 for r in records if r['status'] == 'Half-Day')
    total_week_off = sum(1 for r in records if r['status'] == 'Week Off')

    # --- Weekly Summary ---
    weekly_summary = {}
    for r in records:
        d = datetime.strptime(r['date'], "%Y-%m-%d")
        week_start = (d - timedelta(days=d.weekday())).strftime("%d %b")
        week_end = (d + timedelta(days=6 - d.weekday())).strftime("%d %b")
        wk = f"{week_start} - {week_end}"
        weekly_summary.setdefault(wk, {
            'present': 0, 'absent': 0, 'half_day': 0, 'week_off': 0,
            'total_salary': 0, 'total_ot_pay': 0
        })
        status_key = r['status'].lower().replace(' ', '_')
        if status_key in weekly_summary[wk]:
            weekly_summary[wk][status_key] += 1
        weekly_summary[wk]['total_salary'] += r['salary']
        weekly_summary[wk]['total_ot_pay'] += r['ot_pay']

    weekly_summary_list = [{"week_range": k, **v} for k, v in sorted(weekly_summary.items())]

    return render_template(
        'payroll_view.html',
        employee=emp,
        records_paginated=records,
        total=total_salary,
        total_ot_pay=total_ot_pay,
        page=1,
        total_pages=1,
        start_date=start_date,
        end_date=end_date,
        weekly_summary=weekly_summary_list,
        total_present=total_present,
        total_absent=total_absent,
        total_half_day=total_half_day,
        total_week_off=total_week_off,
        total_expense=round(float(total_expense), 2),
        total_advance=round(float(total_advance), 2)
    )


@app.route('/payroll/<int:employee_id>/export/excel')
@admin_login_required
def export_payroll_excel(employee_id):
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    if not start_date or not end_date:
        today = datetime.today()
        start_date = today.replace(day=1).strftime('%Y-%m-%d')
        end_date = today.strftime('%Y-%m-%d')

    conn = get_db_connection()
    emp = conn.execute("SELECT * FROM employees WHERE id = ?", (employee_id,)).fetchone()
    per_hour_salary = float(emp['per_hour_salary'] or 0)
    shift_hours = float(emp['shift_hours'] or 8)
    week_offs = emp['week_off_days'].split(',') if emp['week_off_days'] else []

    date_cursor = datetime.strptime(start_date, "%Y-%m-%d")
    end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")

    records = []
    while date_cursor <= end_date_obj:
        day_name = date_cursor.strftime("%A")
        date_str = date_cursor.strftime("%Y-%m-%d")

        attendance = conn.execute("""
            SELECT 
                COALESCE(in_time, '') AS in_time, 
                COALESCE(out_time, '') AS out_time 
            FROM attendance 
            WHERE employee_id = ? AND DATE(timestamp) = ?
        """, (employee_id, date_str)).fetchone()

        in_time = attendance['in_time'] if attendance else ''
        out_time = attendance['out_time'] if attendance else ''
        status, hours_worked, salary = "Absent", 0, 0

        # Week off
        if day_name in week_offs:
            status, hours_worked = "Week Off", shift_hours
            salary = hours_worked * per_hour_salary

        # In only / Out only logic
        elif in_time or out_time:
            if in_time and not out_time:
                status, hours_worked = "Half-Day", shift_hours / 2
            elif out_time and not in_time:
                status, hours_worked = "Half-Day", shift_hours / 2
            else:
                fmt = "%H:%M"
                try:
                    in_dt = datetime.strptime(in_time, fmt)
                    out_dt = datetime.strptime(out_time, fmt)
                    worked = max(0, (out_dt - in_dt).total_seconds() / 3600)
                    hours_worked = min(worked, shift_hours)
                    status = "Present" if hours_worked >= (shift_hours * 0.75) else "Half-Day"
                except Exception:
                    status, hours_worked = "Half-Day", shift_hours / 2
            salary = round(hours_worked * per_hour_salary, 2)

        records.append({
            "Date": date_str,
            "Day": day_name,
            "In Time": in_time or "-",
            "Out Time": out_time or "-",
            "Status": status,
            "Hours Worked": round(hours_worked, 2),
            "Salary": round(salary, 2)
        })
        date_cursor += timedelta(days=1)

    conn.close()

    df = pd.DataFrame(records)
    out = BytesIO()
    with pd.ExcelWriter(out, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Payroll')
    out.seek(0)

    return send_file(
        out,
        as_attachment=True,
        download_name=f"payroll_{employee_id}_{start_date}_to_{end_date}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@app.route('/payroll/<int:employee_id>/export/pdf')
@admin_login_required
def export_payroll_pdf(employee_id):
    html = view_payroll(employee_id).get_data(as_text=True)
    pdf = BytesIO()
    pisa.CreatePDF(src=html, dest=pdf)
    pdf.seek(0)
    return send_file(
        pdf,
        download_name=f"payroll_{employee_id}.pdf",
        as_attachment=True
    )

# =================================================
# Misc tools
# =================================================
@app.route('/log-client-error', methods=['POST'])
def log_client_error():
    data = request.get_json(force=True, silent=True) or {}
    err = data.get("error")
    ts = data.get("time")
    print(f"[CLIENT ERROR] {ts} — {err}")
    with open("client_errors.log", "a") as f:
        f.write(f"{ts} — {err}\n")
    return jsonify({"status": "logged"})

@app.route('/test-weekoff')
def test_weekoff():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE employees SET week_off_days=? WHERE id=?", ("Sunday,Monday", 3))
    conn.commit()
    conn.close()
    return "Test update done"

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

# =================================================
# Run
# =================================================
if __name__ == "__main__":
    # debug True for now (disable in prod / use gunicorn)
    app.run(host="0.0.0.0", port=5016, debug=True, use_reloader=False)

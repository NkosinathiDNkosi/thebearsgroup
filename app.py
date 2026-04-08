from flask import Flask, render_template, request, redirect, url_for, jsonify, session
import sqlite3
import os
import re
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import resend

app = Flask(__name__)
app.secret_key = "bears-healthcare-super-secure-2026-admin-key"

# ============================================================
# RESEND EMAIL CONFIG
# ============================================================
RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
resend.api_key = RESEND_API_KEY


# ============================================================
# DATABASE PATH
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "bears_appointments.db")

print("Using DB:", DB_PATH)


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ============================================================
# DATABASE SETUP
# ============================================================
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            email TEXT NOT NULL,
            service TEXT NOT NULL,
            appointment_date TEXT NOT NULL,
            appointment_time TEXT NOT NULL,
            message TEXT,
            status TEXT DEFAULT 'Pending',
            is_deleted INTEGER DEFAULT 0,
            deleted_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


def ensure_columns():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(appointments)")
    columns = [column[1] for column in cursor.fetchall()]

    if "status" not in columns:
        cursor.execute("ALTER TABLE appointments ADD COLUMN status TEXT DEFAULT 'Pending'")

    if "is_deleted" not in columns:
        cursor.execute("ALTER TABLE appointments ADD COLUMN is_deleted INTEGER DEFAULT 0")

    if "deleted_at" not in columns:
        cursor.execute("ALTER TABLE appointments ADD COLUMN deleted_at TEXT")

    conn.commit()
    conn.close()


def create_default_admin():
    conn = get_db_connection()
    cursor = conn.cursor()

    admin_username = "admin"
    admin_password = "Admin@123"

    existing_admin = cursor.execute(
        "SELECT * FROM admins WHERE username = ?",
        (admin_username,)
    ).fetchone()

    if not existing_admin:
        hashed_password = generate_password_hash(admin_password)
        cursor.execute(
            "INSERT INTO admins (username, password) VALUES (?, ?)",
            (admin_username, hashed_password)
        )
        conn.commit()
        print("Default admin created:")
        print("Username: admin")
        print("Password: Admin@123")

    conn.close()


init_db()
ensure_columns()
create_default_admin()


# ============================================================
# VALIDATION HELPERS
# ============================================================
def is_only_spaces(value):
    return not value or value.strip() == ""


def normalize_phone(phone):
    return re.sub(r"[^\d+]", "", phone.replace(" ", ""))


def is_valid_sa_phone(phone):
    normalized = normalize_phone(phone)
    return bool(re.fullmatch(r"(\+27\d{9}|0\d{9})", normalized))


def is_valid_email(email):
    return bool(re.fullmatch(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email.strip()))


def is_valid_date(date_str):
    try:
        selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        today = datetime.today().date()

        if selected_date < today:
            return False, "You cannot choose a past date."

        if selected_date.weekday() == 6:
            return False, "Sundays are unavailable. Please choose another date."

        return True, ""
    except ValueError:
        return False, "Please choose a valid appointment date."


def admin_required():
    return session.get("admin_logged_in") is True


# ============================================================
# EMAIL FUNCTION (RESEND)
# ============================================================
def send_confirmation_email(full_name, email, service, appointment_date, appointment_time):
    try:
        resend.Emails.send({
            "from": "Bears Healthcare <appointments@bearshealthcare.co.za>",
            "to": [email],
            "subject": "Appointment Confirmation - Bears Healthcare",
            "html": f"""
                <h2>Appointment Request Received</h2>

                <p>Dear {full_name},</p>

                <p>Your appointment request has been received successfully.</p>

                <h3>Appointment Details</h3>
                <ul>
                    <li><strong>Service:</strong> {service}</li>
                    <li><strong>Date:</strong> {appointment_date}</li>
                    <li><strong>Time:</strong> {appointment_time}</li>
                    <li><strong>Status:</strong> Pending Confirmation</li>
                </ul>

                <p>We will contact you shortly to confirm your appointment.</p>

                <br>
                <p>Best regards,</p>
                <p><strong>Bears Healthcare</strong></p>
            """
        })

        print("Confirmation email sent")

    except Exception as e:
        print("Email failed:", e)


# ============================================================
# PUBLIC ROUTES
# ============================================================
@app.route("/")
def home():
    success = request.args.get("success")
    error = request.args.get("error")
    return render_template("index.html", success=success, error=error)


@app.route("/booked-slots")
def booked_slots():
    selected_date = request.args.get("date", "").strip()

    if not selected_date:
        return jsonify([])

    conn = get_db_connection()
    rows = conn.execute("""
        SELECT appointment_time
        FROM appointments
        WHERE appointment_date = ?
          AND COALESCE(is_deleted, 0) = 0
    """, (selected_date,)).fetchall()
    conn.close()

    times = sorted([row["appointment_time"] for row in rows if row["appointment_time"]])
    return jsonify(times)


@app.route("/book", methods=["POST"])
def book():
    data = request.form

    full_name = data.get("full_name", "").strip()
    phone = data.get("phone", "").strip()
    email = data.get("email", "").strip()
    service = data.get("service", "").strip()
    appointment_date = data.get("appointment_date", "").strip()
    appointment_time = data.get("appointment_time", "").strip()
    message = data.get("message", "")

    if is_only_spaces(full_name) or len(full_name) < 3:
        return redirect(url_for("home", error="Please enter a valid full name."))

    if is_only_spaces(phone):
        return redirect(url_for("home", error="Phone number cannot be empty."))

    if not is_valid_sa_phone(phone):
        return redirect(url_for("home", error="Enter a valid South African phone number, e.g. 0712345678 or +27712345678."))

    if is_only_spaces(email):
        return redirect(url_for("home", error="Email address cannot be empty."))

    if not is_valid_email(email):
        return redirect(url_for("home", error="Please enter a valid email address."))

    if is_only_spaces(service):
        return redirect(url_for("home", error="Please select a service."))

    if is_only_spaces(appointment_date):
        return redirect(url_for("home", error="Please choose an appointment date."))

    valid_date, date_error = is_valid_date(appointment_date)
    if not valid_date:
        return redirect(url_for("home", error=date_error))

    if is_only_spaces(appointment_time):
        return redirect(url_for("home", error="Please choose an appointment time."))

    if message and is_only_spaces(message):
        return redirect(url_for("home", error="Additional information cannot contain spaces only."))

    clean_message = message.strip()

    conn = get_db_connection()
    cursor = conn.cursor()

    existing_appointment = cursor.execute("""
        SELECT * FROM appointments
        WHERE appointment_date = ?
          AND appointment_time = ?
          AND COALESCE(is_deleted, 0) = 0
    """, (appointment_date, appointment_time)).fetchone()

    if existing_appointment:
        conn.close()
        return redirect(
            url_for(
                "home",
                error="That time slot is already booked. Please choose a different date or time."
            )
        )

    cursor.execute("""
        INSERT INTO appointments
        (full_name, phone, email, service, appointment_date, appointment_time, message, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        full_name,
        normalize_phone(phone),
        email,
        service,
        appointment_date,
        appointment_time,
        clean_message,
        "Pending"
    ))

    conn.commit()
    conn.close()

    # SEND EMAIL CONFIRMATION
    send_confirmation_email(
        full_name,
        email,
        service,
        appointment_date,
        appointment_time
    )

    return redirect(
        url_for("home", success="Your appointment request was submitted successfully.")
    )

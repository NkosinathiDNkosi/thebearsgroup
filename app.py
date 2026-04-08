from flask import Flask, render_template, request, redirect, url_for, jsonify, session
import sqlite3
import os
import re
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import resend  # ✅ ADDED

app = Flask(__name__)
app.secret_key = "bears-healthcare-super-secure-2026-admin-key"

# ============================================================
# 🔥 RESEND CONFIG (ADDED)
# ============================================================
resend.api_key = os.getenv("RESEND_API_KEY")
FROM_EMAIL = os.getenv("FROM_EMAIL")


def send_confirmation_email(appointment):
    try:
        if not resend.api_key or not FROM_EMAIL:
            print("❌ Missing RESEND_API_KEY or FROM_EMAIL")
            return

        resend.Emails.send({
            "from": FROM_EMAIL,
            "to": [appointment["email"]],
            "subject": "Appointment Confirmed - The Bears Healthcare Group",
            "html": f"""
                <h2>Appointment Confirmed</h2>
                <p>Hello {appointment['full_name']},</p>
                <p>Your appointment has been confirmed.</p>

                <p><b>Service:</b> {appointment['service']}</p>
                <p><b>Date:</b> {appointment['appointment_date']}</p>
                <p><b>Time:</b> {appointment['appointment_time']}</p>

                <br>
                <p>We look forward to seeing you.</p>
                <p><b>The Bears Healthcare Group</b></p>
            """
        })

        print("✅ Email sent")

    except Exception as e:
        print("❌ Email error:", e)


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
# ROUTES
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


@app.route("/update-status/<int:appointment_id>", methods=["POST"])
def update_status(appointment_id):
    if not admin_required():
        return redirect(url_for("login"))

    new_status = request.form.get("status", "").strip()

    if new_status not in ["Pending", "Confirmed", "Completed", "Cancelled"]:
        return redirect(url_for("dashboard"))

    conn = get_db_connection()

    appointment = conn.execute(
        "SELECT * FROM appointments WHERE id = ?",
        (appointment_id,)
    ).fetchone()

    conn.execute("""
        UPDATE appointments
        SET status = ?
        WHERE id = ?
    """, (new_status, appointment_id))

    conn.commit()
    conn.close()

    # 🔥 EMAIL TRIGGER
    if new_status == "Confirmed" and appointment:
        send_confirmation_email(appointment)

    return redirect(url_for("dashboard"))

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
# 🔥 RESEND EMAIL CONFIG
# ============================================================
resend.api_key = os.getenv("RESEND_API_KEY")


def send_confirmation_email(appointment):
    try:
        resend.Emails.send({
            "from": os.getenv("FROM_EMAIL"),
            "to": [appointment["email"]],
            "subject": "Appointment Confirmed - Bears Healthcare",
            "html": f"""
                <div style="font-family: Arial; padding:20px;">
                    <h2 style="color:#0E2A47;">Appointment Confirmed</h2>

                    <p>Hello {appointment['full_name']},</p>

                    <p>Your appointment has been confirmed.</p>

                    <div style="background:#f5f5f5; padding:15px; border-radius:10px;">
                        <p><b>Service:</b> {appointment['service']}</p>
                        <p><b>Date:</b> {appointment['appointment_date']}</p>
                        <p><b>Time:</b> {appointment['appointment_time']}</p>
                    </div>

                    <p style="margin-top:20px;">
                        We look forward to seeing you.
                    </p>

                    <p><b>Bears Healthcare Group</b></p>
                </div>
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
            deleted_at TEXT,
            email_sent INTEGER DEFAULT 0
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

    if "email_sent" not in columns:
        cursor.execute("ALTER TABLE appointments ADD COLUMN email_sent INTEGER DEFAULT 0")

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
            return False, "Sundays are unavailable."

        return True, ""
    except ValueError:
        return False, "Invalid date."


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


@app.route("/dashboard")
def dashboard():
    if not admin_required():
        return redirect(url_for("login"))

    conn = get_db_connection()
    appointments = conn.execute("""
        SELECT *
        FROM appointments
        WHERE COALESCE(is_deleted, 0) = 0
        ORDER BY appointment_date ASC, appointment_time ASC
    """).fetchall()
    conn.close()

    return render_template("dashboard.html", appointments=appointments)


# ============================================================
# 🔥 UPDATED STATUS ROUTE WITH EMAIL
# ============================================================
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

    # 🚀 SEND EMAIL ONLY ON CONFIRM (AND ONLY ONCE)
    if appointment and new_status == "Confirmed" and appointment["email_sent"] == 0:
        send_confirmation_email(appointment)

        conn.execute(
            "UPDATE appointments SET email_sent = 1 WHERE id = ?",
            (appointment_id,)
        )
        conn.commit()

    conn.close()

    return redirect(url_for("dashboard"))


# ============================================================
# DELETE
# ============================================================
@app.route("/delete-appointment/<int:appointment_id>", methods=["POST"])
def delete_appointment(appointment_id):
    if not admin_required():
        return redirect(url_for("login"))

    conn = get_db_connection()
    conn.execute("""
        UPDATE appointments
        SET is_deleted = 1,
            deleted_at = ?
        WHERE id = ?
    """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), appointment_id))
    conn.commit()
    conn.close()

    return redirect(url_for("dashboard"))


# ============================================================
# LOGIN / LOGOUT
# ============================================================
@app.route("/login", methods=["GET", "POST"])
def login():
    if admin_required():
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        conn = get_db_connection()
        admin = conn.execute(
            "SELECT * FROM admins WHERE username = ?",
            (username,)
        ).fetchone()
        conn.close()

        if admin and check_password_hash(admin["password"], password):
            session["admin_logged_in"] = True
            session["admin_username"] = admin["username"]
            return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ============================================================
# RUN
# ============================================================
if __name__ == "__main__":
    app.run(debug=True)

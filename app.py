from flask import Flask, render_template, request, redirect, url_for, jsonify, session
import sqlite3
import os
import re
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "bears-healthcare-super-secure-2026-admin-key"

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

    return redirect(
        url_for("home", success="Your appointment request was submitted successfully.")
    )


# ============================================================
# STAFF LOGIN
# ============================================================
@app.route("/login", methods=["GET", "POST"])
def login():
    if admin_required():
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

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

        return render_template("login.html", error="Invalid username or password.")

    return render_template("login.html")


# ============================================================
# PROTECTED DASHBOARD
# ============================================================
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


@app.route("/bin")
def bin_page():
    if not admin_required():
        return redirect(url_for("login"))

    conn = get_db_connection()
    appointments = conn.execute("""
        SELECT *
        FROM appointments
        WHERE COALESCE(is_deleted, 0) = 1
        ORDER BY deleted_at DESC
    """).fetchall()
    conn.close()

    return render_template("bin.html", appointments=appointments)


@app.route("/restore-appointment/<int:appointment_id>", methods=["POST"])
def restore_appointment(appointment_id):
    if not admin_required():
        return redirect(url_for("login"))

    conn = get_db_connection()
    conn.execute("""
        UPDATE appointments
        SET is_deleted = 0,
            deleted_at = NULL
        WHERE id = ?
    """, (appointment_id,))
    conn.commit()
    conn.close()

    return redirect(url_for("bin_page"))


@app.route("/purge-appointment/<int:appointment_id>", methods=["POST"])
def purge_appointment(appointment_id):
    if not admin_required():
        return redirect(url_for("login"))

    conn = get_db_connection()
    conn.execute("DELETE FROM appointments WHERE id = ?", (appointment_id,))
    conn.commit()
    conn.close()

    return redirect(url_for("bin_page"))


@app.route("/change-password", methods=["GET", "POST"])
def change_password():
    if not admin_required():
        return redirect(url_for("login"))

    error = None
    success = None

    if request.method == "POST":
        current_password = request.form.get("current_password", "").strip()
        new_password = request.form.get("new_password", "").strip()

        if len(new_password) < 6:
            error = "New password must be at least 6 characters long."
            return render_template("change_password.html", error=error, success=success)

        conn = get_db_connection()
        admin = conn.execute(
            "SELECT * FROM admins WHERE username = ?",
            (session.get("admin_username"),)
        ).fetchone()

        if not admin or not check_password_hash(admin["password"], current_password):
            conn.close()
            error = "Current password is incorrect."
            return render_template("change_password.html", error=error, success=success)

        new_hashed_password = generate_password_hash(new_password)

        conn.execute("""
            UPDATE admins
            SET password = ?
            WHERE username = ?
        """, (new_hashed_password, session.get("admin_username")))
        conn.commit()
        conn.close()

        success = "Password updated successfully."

    return render_template("change_password.html", error=error, success=success)


# ============================================================
# UPDATE STATUS
# ============================================================
@app.route("/update-status/<int:appointment_id>", methods=["POST"])
def update_status(appointment_id):
    if not admin_required():
        return redirect(url_for("login"))

    new_status = request.form.get("status", "").strip()

    if new_status not in ["Pending", "Confirmed", "Completed", "Cancelled"]:
        return redirect(url_for("dashboard"))

    conn = get_db_connection()
    conn.execute("""
        UPDATE appointments
        SET status = ?
        WHERE id = ?
    """, (new_status, appointment_id))
    conn.commit()
    conn.close()

    return redirect(url_for("dashboard"))


# ============================================================
# SOFT DELETE APPOINTMENT
# ============================================================
@app.route("/delete-appointment/<int:appointment_id>", methods=["POST"])
def delete_appointment(appointment_id):
    if not admin_required():
        return redirect(url_for("login"))

    deleted_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db_connection()
    conn.execute("""
        UPDATE appointments
        SET is_deleted = 1,
            deleted_at = ?
        WHERE id = ?
    """, (deleted_at, appointment_id))
    conn.commit()
    conn.close()

    return redirect(url_for("dashboard"))


# ============================================================
# LOGOUT
# ============================================================
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(debug=True)

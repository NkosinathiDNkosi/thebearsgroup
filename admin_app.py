from flask import Flask, render_template, request, redirect, url_for, session
import os
import sqlite3
import secrets
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import timedelta, datetime

app = Flask(__name__)

# ============================================================
# APP CONFIG
# ============================================================
app.secret_key = "change_this_to_a_long_random_secret"
app.permanent_session_lifetime = timedelta(minutes=30)

# ============================================================
# DATABASE CONNECTION
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "..", "bears_appointments.db")
DB_PATH = os.path.abspath(DB_PATH)

print("Using DB:", DB_PATH)

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ============================================================
# CREATE ADMIN USER
# ============================================================
def create_admin():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )
    """)

    username = "admin"
    password = generate_password_hash("admin123")

    try:
        cursor.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            (username, password)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        pass

    conn.close()

# ============================================================
# ENSURE APPOINTMENTS TABLE + COLUMNS EXIST
# ============================================================
def ensure_appointments_table():
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

    conn.commit()
    conn.close()

def ensure_status_column():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(appointments)")
    columns = [column[1] for column in cursor.fetchall()]

    if "status" not in columns:
        cursor.execute("ALTER TABLE appointments ADD COLUMN status TEXT DEFAULT 'Pending'")
        print("Status column added to appointments table.")

    conn.commit()
    conn.close()

def ensure_bin_columns():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(appointments)")
    columns = [column[1] for column in cursor.fetchall()]

    if "is_deleted" not in columns:
        cursor.execute("ALTER TABLE appointments ADD COLUMN is_deleted INTEGER DEFAULT 0")
        print("is_deleted column added.")

    if "deleted_at" not in columns:
        cursor.execute("ALTER TABLE appointments ADD COLUMN deleted_at TEXT")
        print("deleted_at column added.")

    conn.commit()
    conn.close()

# ============================================================
# LOGIN CHECK
# ============================================================
@app.before_request
def require_login():
    allowed = {"login", "static"}
    if request.endpoint in allowed or request.endpoint is None:
        return

    if "user" not in session:
        return redirect(url_for("login"))

# ============================================================
# ROUTES
# ============================================================
@app.route("/")
def home():
    return redirect(url_for("login"))

# -------------------------
# LOGIN
# -------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    message = request.args.get("message")

    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session.clear()
            session.permanent = True
            session["user"] = username

            token = secrets.token_urlsafe(24)
            session["tab_token"] = token

            return f"""
            <!doctype html>
            <html>
            <head><meta charset="utf-8"></head>
            <body>
              <script>
                sessionStorage.setItem("bears_admin_tab_token", "{token}");
                window.location.replace("{url_for('dashboard')}");
              </script>
            </body>
            </html>
            """
        else:
            error = "Invalid username or password."

    if request.method == "GET":
        session.clear()

    return render_template("login.html", error=error, message=message)

# -------------------------
# LOGOUT
# -------------------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# -------------------------
# CHANGE PASSWORD
# -------------------------
@app.route("/change-password", methods=["GET", "POST"])
def change_password():
    error = None
    success = None

    if request.method == "POST":
        current_password = request.form["current_password"]
        new_password = request.form["new_password"]

        if len(new_password) < 6:
            return render_template(
                "change_password.html",
                error="New password must be at least 6 characters long."
            )

        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE username = ?",
            (session["user"],)
        ).fetchone()

        if not user or not check_password_hash(user["password"], current_password):
            conn.close()
            return render_template(
                "change_password.html",
                error="Current password is incorrect."
            )

        new_hashed = generate_password_hash(new_password)

        conn.execute(
            "UPDATE users SET password = ? WHERE username = ?",
            (new_hashed, session["user"])
        )
        conn.commit()
        conn.close()

        session.clear()
        return redirect(url_for("login", message="Password updated successfully. Please log in again."))

    return render_template("change_password.html", error=error, success=success)

# -------------------------
# DASHBOARD
# -------------------------
@app.route("/dashboard")
def dashboard():
    conn = get_db_connection()
    appointments = conn.execute("""
        SELECT * FROM appointments
        WHERE COALESCE(is_deleted, 0) = 0
        ORDER BY appointment_date DESC, appointment_time DESC
    """).fetchall()
    conn.close()

    return render_template("dashboard.html", appointments=appointments)

# -------------------------
# BIN VIEW
# -------------------------
@app.route("/bin")
def bin_view():
    conn = get_db_connection()
    deleted = conn.execute("""
        SELECT * FROM appointments
        WHERE COALESCE(is_deleted, 0) = 1
        ORDER BY deleted_at DESC
    """).fetchall()
    conn.close()

    return render_template("bin.html", appointments=deleted)

# -------------------------
# CONFIRM APPOINTMENT
# -------------------------
@app.route("/confirm/<int:id>")
def confirm_appointment(id):
    conn = get_db_connection()
    conn.execute(
        "UPDATE appointments SET status = 'Confirmed' WHERE id = ?",
        (id,)
    )
    conn.commit()
    conn.close()

    return redirect(url_for("dashboard"))

# -------------------------
# DELETE -> MOVE TO BIN
# -------------------------
@app.route("/delete/<int:id>")
def delete_appointment(id):
    conn = get_db_connection()
    conn.execute("""
        UPDATE appointments
        SET is_deleted = 1,
            deleted_at = ?
        WHERE id = ?
    """, (datetime.now().isoformat(timespec="seconds"), id))
    conn.commit()
    conn.close()

    return redirect(url_for("dashboard"))

# -------------------------
# RESTORE FROM BIN
# -------------------------
@app.route("/restore/<int:id>")
def restore_appointment(id):
    conn = get_db_connection()
    conn.execute("""
        UPDATE appointments
        SET is_deleted = 0,
            deleted_at = NULL
        WHERE id = ?
    """, (id,))
    conn.commit()
    conn.close()

    return redirect(url_for("bin_view"))

# -------------------------
# PERMANENT DELETE
# -------------------------
@app.route("/purge/<int:id>")
def purge_appointment(id):
    conn = get_db_connection()
    conn.execute(
        "DELETE FROM appointments WHERE id = ? AND COALESCE(is_deleted, 0) = 1",
        (id,)
    )
    conn.commit()
    conn.close()

    return redirect(url_for("bin_view"))

# ============================================================
# RUN APP
# ============================================================
if __name__ == "__main__":
    create_admin()
    ensure_appointments_table()
    ensure_status_column()
    ensure_bin_columns()
    app.run(debug=True)
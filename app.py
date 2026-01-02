from flask import Flask, render_template, request, redirect, send_file, flash, session
import sqlite3
from datetime import datetime
import io
from werkzeug.security import generate_password_hash, check_password_hash

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

app = Flask(__name__)
app.secret_key = "khatabook-secret-key"

DB = "khatabook.db"

# ---------- DB ----------
def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()

    # USERS
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT UNIQUE,
            password TEXT
        )
    """)

    # ENTRIES
    conn.execute("""
        CREATE TABLE IF NOT EXISTS entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            person TEXT,
            amount REAL,
            type TEXT,
            date TEXT
        )
    """)

    conn.commit()
    conn.close()

init_db()

# ---------- DEFAULT ----------
@app.route("/")
def home():
    return redirect("/register")

# ---------- REGISTER ----------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = generate_password_hash(request.form["password"])

        try:
            conn = get_db()
            conn.execute(
                "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
                (name, email, password)
            )
            conn.commit()
            conn.close()

            flash("Registration successful. Please login.", "success")
            return redirect("/login")

        except:
            flash("Email already exists", "danger")

    return render_template("register.html")

# ---------- LOGIN ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE email=?", (email,)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            return redirect("/dashboard")

        flash("Invalid login details", "danger")

    return render_template("login.html")

# ---------- LOGOUT ----------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ---------- DASHBOARD ----------
@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()
    c = conn.cursor()

    # ADD ENTRY
    if request.method == "POST":
        entry_date = request.form.get("date") or datetime.now().strftime("%Y-%m-%d")

        c.execute(
            "INSERT INTO entries (user_id, person, amount, type, date) VALUES (?, ?, ?, ?, ?)",
            (
                session["user_id"],
                request.form["person"],
                float(request.form["amount"]),
                request.form["type"],
                entry_date
            )
        )
        conn.commit()
        return redirect("/dashboard")

    entries = c.execute(
        "SELECT * FROM entries WHERE user_id=? ORDER BY date ASC, id ASC",
        (session["user_id"],)
    ).fetchall()

    running_balance = 0
    ledger_entries = []

    for e in entries:
        credit = "-"
        debit = "-"

        if e["type"] == "IN":
            running_balance += e["amount"]
            credit = e["amount"]
        else:
            running_balance -= e["amount"]
            debit = e["amount"]

        ledger_entries.append({
            "id": e["id"],
            "date": e["date"],
            "person": e["person"],
            "credit": credit,
            "debit": debit,
            "balance": running_balance
        })

    total_in = sum(e["amount"] for e in entries if e["type"] == "IN")
    total_out = sum(e["amount"] for e in entries if e["type"] == "OUT")
    balance = total_in - total_out

    today = datetime.now().strftime("%Y-%m-%d")

    conn.close()

    return render_template(
        "dashboard.html",
        entries=ledger_entries,
        total_in=total_in,
        total_out=total_out,
        balance=balance,
        today=today,
        user=session["user_name"],
        datetime=datetime
    )

# ---------- DELETE ----------
@app.route("/delete", methods=["POST"])
def delete_entry():
    if "user_id" not in session:
        return redirect("/login")

    entry_id = request.form["id"]

    conn = get_db()
    conn.execute(
        "DELETE FROM entries WHERE id=? AND user_id=?",
        (entry_id, session["user_id"])
    )
    conn.commit()
    conn.close()

    flash("Entry deleted", "danger")
    return redirect("/dashboard")

# ---------- RUN ----------
if __name__ == "__main__":
    app.run(debug=True)

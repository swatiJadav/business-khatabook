from flask import Flask, render_template, request, redirect, send_file, flash, session
import sqlite3
from datetime import datetime, date
from werkzeug.security import generate_password_hash, check_password_hash
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
import os

# ---------- APP ----------
app = Flask(__name__)
app.secret_key = "khatabook-secret-key"
DB = "khatabook.db"

# ---------- FONT (RENDER SAFE) ----------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_PATH = os.path.join(BASE_DIR, "static", "fonts", "DejaVuSans.ttf")
pdfmetrics.registerFont(TTFont("DejaVu", FONT_PATH))

# ---------- DB ----------
def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT UNIQUE,
            password TEXT
        )
    """)
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

# ---------- ROUTES ----------
@app.route("/")
def home():
    return redirect("/login")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        try:
            conn = get_db()
            conn.execute(
                "INSERT INTO users (name,email,password) VALUES (?,?,?)",
                (
                    request.form["name"],
                    request.form["email"],
                    generate_password_hash(request.form["password"])
                )
            )
            conn.commit()
            conn.close()
            flash("Registration successful", "success")
            return redirect("/login")
        except:
            flash("Email already exists", "danger")
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE email=?",
            (request.form["email"],)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user["password"], request.form["password"]):
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            return redirect("/dashboard")

        flash("Invalid login", "danger")
    return render_template("login.html")

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
    cur = conn.cursor()

    # ADD ENTRY
    if request.method == "POST":
        cur.execute(
            "INSERT INTO entries (user_id,person,amount,type,date) VALUES (?,?,?,?,?)",
            (
                session["user_id"],
                request.form["person"],
                float(request.form["amount"]),
                request.form["type"],
                request.form.get("date") or date.today().isoformat()
            )
        )
        conn.commit()
        return redirect("/dashboard")

    rows = cur.execute(
        "SELECT * FROM entries WHERE user_id=? ORDER BY date,id",
        (session["user_id"],)
    ).fetchall()

    # CALCULATIONS
    running = 0
    total_credit = 0
    total_debit = 0
    ledger = []

    for r in rows:
        credit = debit = "-"
        if r["type"] == "IN":
            running += r["amount"]
            total_credit += r["amount"]
            credit = r["amount"]
        else:
            running -= r["amount"]
            total_debit += r["amount"]
            debit = r["amount"]

        ledger.append({
            "date": r["date"],
            "person": r["person"],
            "credit": credit,
            "debit": debit,
            "balance": running
        })

    conn.close()

    return render_template(
        "dashboard.html",
        entries=ledger,
        user=session["user_name"],
        total_credit=total_credit,
        total_debit=total_debit,
        balance=running,
        today=date.today().isoformat()
    )

# ---------- PDF ----------
@app.route("/download-pdf")
def download_pdf():
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM entries WHERE user_id=? ORDER BY date,id",
        (session["user_id"],)
    ).fetchall()
    conn.close()

    balance = 0
    data = []

    for r in rows:
        credit = debit = "-"
        if r["type"] == "IN":
            balance += r["amount"]
            credit = f"₹ {r['amount']}"
        else:
            balance -= r["amount"]
            debit = f"₹ {r['amount']}"

        data.append((r["date"], r["person"], credit, debit, f"₹ {balance}"))

    file_path = "netlink_report.pdf"
    c = canvas.Canvas(file_path, pagesize=A4)
    width, height = A4

    c.setFont("DejaVu", 18)
    c.drawCentredString(width / 2, height - 60, "Netlink Report")

    start_x = 60
    start_y = height - 120
    row_h = 28
    col_w = [90, 120, 90, 90, 100]

    x = [start_x]
    for w in col_w:
        x.append(x[-1] + w)

    headers = ["Date", "Person", "Credit", "Debit", "Balance"]
    c.setFont("DejaVu", 11)

    y = start_y
    for i, h in enumerate(headers):
        c.drawCentredString((x[i] + x[i+1]) / 2, y, h)

    c.line(x[0], y - 8, x[-1], y - 8)

    c.setFont("DejaVu", 10)
    y -= row_h

    for row in data:
        for i, val in enumerate(row):
            c.drawCentredString((x[i] + x[i+1]) / 2, y, val)
        y -= row_h

    bottom = y + row_h - 8
    for xi in x:
        c.line(xi, start_y + 8, xi, bottom)

    c.rect(x[0], bottom, x[-1] - x[0], (start_y + 8) - bottom)

    c.save()
    return send_file(file_path, as_attachment=True)

# ---------- RUN ----------
if __name__ == "__main__":
    app.run(debug=True)

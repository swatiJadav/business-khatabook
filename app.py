from flask import Flask, render_template, request, redirect, send_file, flash, session
import sqlite3
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os

app = Flask(__name__)
app.secret_key = "khatabook-secret-key"
DB = "khatabook.db"

# ---------- FONT SAFE ----------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_PATH = os.path.join(BASE_DIR, "static", "fonts", "DejaVuSans.ttf")

FONT_NAME = "Helvetica"
if os.path.exists(FONT_PATH):
    try:
        pdfmetrics.registerFont(TTFont("DejaVu", FONT_PATH))
        FONT_NAME = "DejaVu"
    except:
        pass

# ---------- DB ----------
def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT UNIQUE,
            password TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS entries(
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

# ---------- AUTH ----------
@app.route("/")
def home():
    return redirect("/login")

@app.route("/login", methods=["GET","POST"])
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
@app.route("/dashboard", methods=["GET","POST"])
def dashboard():
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()
    cur = conn.cursor()

    if request.method == "POST":
        cur.execute(
            "INSERT INTO entries(user_id,person,amount,type,date) VALUES (?,?,?,?,?)",
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

    running = 0
    total_in = 0
    total_out = 0
    ledger = []

    for r in rows:
        credit = debit = "-"
        if r["type"] == "IN":
            running += r["amount"]
            total_in += r["amount"]
            credit = r["amount"]
        else:
            running -= r["amount"]
            total_out += r["amount"]
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
        user=session["user_name"],
        entries=ledger,
        total_in=total_in,
        total_out=total_out,
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
    w, h = A4

    c.setFont(FONT_NAME, 18)
    c.drawCentredString(w/2, h-60, "Netlink Report")

    start_x = 60
    start_y = h - 120
    row_h = 26
    col_w = [90,120,90,90,100]

    x = [start_x]
    for cw in col_w:
        x.append(x[-1] + cw)

    headers = ["Date","Person","Credit","Debit","Balance"]
    c.setFont(FONT_NAME, 11)
    y = start_y

    for i,hdr in enumerate(headers):
        c.drawCentredString((x[i]+x[i+1])/2, y, hdr)

    c.setFont(FONT_NAME, 10)
    y -= row_h

    for row in data:
        for i,val in enumerate(row):
            c.drawCentredString((x[i]+x[i+1])/2, y, val)
        y -= row_h

    c.save()
    return send_file(file_path, as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True)

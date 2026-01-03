from flask import Flask, render_template, request, redirect, send_file, session
import sqlite3, os
from datetime import date
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

app = Flask(__name__)
app.secret_key = "secret-key"

DB = "khatabook.db"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_PATH = os.path.join(BASE_DIR, "static", "fonts", "DejaVuSans.ttf")

FONT_NAME = "Helvetica"
if os.path.exists(FONT_PATH):
    pdfmetrics.registerFont(TTFont("DejaVu", FONT_PATH))
    FONT_NAME = "DejaVu"

# ---------------- DB ----------------
def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

# ---------------- DASHBOARD ----------------
@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    if "user" not in session:
        session["user"] = "Jadav Swati"

    conn = get_db()
    cur = conn.cursor()

    if request.method == "POST":
        cur.execute(
            "INSERT INTO entries (person,amount,type,date) VALUES (?,?,?,?)",
            (
                request.form["person"],
                float(request.form["amount"]),
                request.form["type"],
                request.form["date"],
            ),
        )
        conn.commit()
        return redirect("/dashboard")

    rows = cur.execute("SELECT * FROM entries ORDER BY date,id").fetchall()

    total_in = total_out = balance = 0
    ledger = []

    for r in rows:
        credit = debit = "-"
        if r["type"] == "IN":
            credit = r["amount"]
            total_in += r["amount"]
            balance += r["amount"]
        else:
            debit = r["amount"]
            total_out += r["amount"]
            balance -= r["amount"]

        ledger.append({
            "id": r["id"],
            "date": r["date"],
            "person": r["person"],
            "credit": credit,
            "debit": debit,
            "balance": balance
        })

    conn.close()

    return render_template(
        "dashboard.html",
        entries=ledger,
        total_in=total_in,
        total_out=total_out,
        balance=balance,
        today=date.today().isoformat(),
        user=session["user"]
    )

# ---------------- DELETE ----------------
@app.route("/delete/<int:id>")
def delete(id):
    conn = get_db()
    conn.execute("DELETE FROM entries WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect("/dashboard")

# ---------------- PDF ----------------
@app.route("/download-pdf")
def download_pdf():
    conn = get_db()
    rows = conn.execute("SELECT * FROM entries ORDER BY date,id").fetchall()
    conn.close()

    file_path = "netlink_report.pdf"
    c = canvas.Canvas(file_path, pagesize=A4)
    w, h = A4

    c.setFont(FONT_NAME, 18)
    c.drawCentredString(w/2, h-50, "Netlink Report")

    headers = ["Date", "Person", "Credit", "Debit", "Balance"]
    col_w = [90, 120, 90, 90, 100]
    x = [50]
    for cw in col_w:
        x.append(x[-1] + cw)

    y = h - 100
    c.setFont(FONT_NAME, 11)

    for i, head in enumerate(headers):
        c.drawCentredString((x[i]+x[i+1])/2, y, head)

    c.line(x[0], y-5, x[-1], y-5)

    balance = 0
    y -= 25
    c.setFont(FONT_NAME, 10)

    for r in rows:
        credit = debit = "-"
        if r["type"] == "IN":
            credit = r["amount"]
            balance += r["amount"]
        else:
            debit = r["amount"]
            balance -= r["amount"]

        row = [r["date"], r["person"], credit, debit, balance]
        for i, val in enumerate(row):
            c.drawCentredString((x[i]+x[i+1])/2, y, str(val))
        y -= 22

    c.save()
    return send_file(file_path, as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True)

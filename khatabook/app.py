from flask import Flask, render_template, request, redirect, send_file
import sqlite3
from datetime import datetime
import io

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

app = Flask(__name__)
DB = "khatabook.db"

# ---------- DB ----------
def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person TEXT,
            amount REAL,
            type TEXT,
            date TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ---------- DASHBOARD ----------
@app.route("/", methods=["GET", "POST"])
def index():
    conn = get_db()
    c = conn.cursor()

    # ADD ENTRY
    if request.method == "POST":
        entry_date = request.form.get("date")
        if not entry_date:
            entry_date = datetime.now().strftime("%Y-%m-%d")

        c.execute(
            "INSERT INTO entries (person, amount, type, date) VALUES (?, ?, ?, ?)",
            (
                request.form["person"],
                request.form["amount"],
                request.form["type"],
                entry_date
            )
        )
        conn.commit()
        conn.close()
        return redirect("/")

    # FILTER (ONLY FOR SCREEN)
    from_date = request.args.get("from_date")
    to_date = request.args.get("to_date")

    query = "SELECT * FROM entries"
    params = []

    if from_date and to_date:
        query += " WHERE date BETWEEN ? AND ?"
        params = [from_date, to_date]

    query += " ORDER BY date DESC"
    entries = c.execute(query, params).fetchall()

    total_in = sum(e["amount"] for e in entries if e["type"] == "IN")
    total_out = sum(e["amount"] for e in entries if e["type"] == "OUT")
    balance = total_in - total_out

    today = datetime.now().strftime("%Y-%m-%d")

    conn.close()

    return render_template(
        "dashboard.html",
        entries=entries,
        total_in=total_in,
        total_out=total_out,
        balance=balance,
        from_date=from_date,
        to_date=to_date,
        today=today
    )

# ---------- PDF DOWNLOAD (ALL ENTRIES ONLY) ----------
@app.route("/download-pdf")
def download_pdf():
    conn = get_db()
    c = conn.cursor()

    entries = c.execute(
        "SELECT date, person, amount, type FROM entries ORDER BY date ASC"
    ).fetchall()

    conn.close()

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    y = height - 40

    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(40, y, "Business KhataBook - All Entries")
    y -= 30

    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(40, y, "Date")
    pdf.drawString(130, y, "Person")
    pdf.drawString(300, y, "Amount")
    pdf.drawString(380, y, "Type")
    y -= 20

    pdf.setFont("Helvetica", 10)

    for e in entries:
        if y < 40:
            pdf.showPage()
            pdf.setFont("Helvetica", 10)
            y = height - 40

        pdf.drawString(40, y, e["date"])
        pdf.drawString(130, y, e["person"])
        pdf.drawString(300, y, f"₹ {e['amount']}")
        pdf.drawString(380, y, e["type"])
        y -= 15

    pdf.save()
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="khatabook_all_entries.pdf",
        mimetype="application/pdf"
    )

# ---------- RUN ----------
if __name__ == "__main__":
    app.run()



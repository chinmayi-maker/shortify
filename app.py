
import os
import re
from urllib.parse import urlparse

print("CURRENT FOLDER:")
print(os.getcwd())
from flask import Flask, render_template, request, redirect, session, flash, jsonify
import requests
import sqlite3
import random
import string
import os
import qrcode
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

app.secret_key = os.environ.get("SECRET_KEY", "shortify_secret")

DB = "urls.db"


# =========================
# DATABASE
# =========================

def get_db():

    conn = sqlite3.connect(DB)

    conn.row_factory = sqlite3.Row

    return conn


def init_db():

    conn = get_db()

    cur = conn.cursor()

    # USERS TABLE

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        email TEXT,
        created_at TEXT
    )
    """)

    # URLS TABLE

    cur.execute("""
    CREATE TABLE IF NOT EXISTS urls(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        long_url TEXT,
        short_code TEXT UNIQUE,
        category TEXT,
        clicks INTEGER DEFAULT 0,
        created_at TEXT
    )
    """)

    conn.commit()
    conn.close()


# =========================
# NORMALIZE URL
# =========================

def normalize_long_url(long_url):

    long_url = (long_url or "").strip()

    if not long_url:
        return ""

    parsed = urlparse(long_url)

    if parsed.scheme in ("http", "https"):
        return long_url

    if not parsed.scheme and not long_url.startswith(("/", "#")):
        return "https://" + long_url

    return long_url


# =========================
# GENERATE SHORT CODE
# =========================

def generate_code(length=6):

    return ''.join(
        random.choices(
            string.ascii_letters + string.digits,
            k=length
        )
    )


# =========================
# CREATE QR
# =========================

def create_qr(url, code):

    safe_code = re.sub(r"[^A-Za-z0-9._-]+", "_", code or "qr")
    qr_dir = os.path.join(app.root_path, "static", "qr")

    os.makedirs(qr_dir, exist_ok=True)

    img = qrcode.make(url)

    img.save(os.path.join(qr_dir, f"{safe_code}.png"))

    return safe_code


def create_short_url_record(long_url, category, custom_code=None, user_id=None):

    long_url = normalize_long_url(long_url)
    category = (category or "").strip() or "general"
    code = (custom_code or "").strip() or generate_code()

    conn = get_db()

    try:
        while True:
            exists = conn.execute("""
            SELECT *
            FROM urls
            WHERE short_code=?
            """, (code,)).fetchone()

            if not exists:
                break

            if custom_code:
                return None, None, "Short Code Already Exists"

            code = generate_code()

        conn.execute("""
        INSERT INTO urls(
            user_id,
            long_url,
            short_code,
            category,
            created_at
        )
        VALUES(?,?,?,?,?)
        """, (
            user_id,
            long_url,
            code,
            category,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))

        conn.commit()

    finally:
        conn.close()

    short_url = request.host_url + code

    return code, short_url, None


# =========================
# EXTERNAL SHORTENER (is.gd)
# =========================

def shorten_with_isgd(long_url):

    try:
        r = requests.get(
            "https://is.gd/create.php",
            params={"format": "simple", "url": long_url},
            timeout=5
        )

        if r.status_code == 200:
            short = r.text.strip()
            if short.startswith("http"):
                return short

    except Exception:
        pass

    return None


# =========================
# HOME
# =========================

@app.route("/")
def home():

    if "user_id" in session:
        return redirect("/dashboard")

    return redirect("/login")


# =========================
# REGISTER
# =========================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form["username"]

        email = request.form["email"]

        password = request.form["password"]

        hashed_password = generate_password_hash(password)

        conn = get_db()

        try:

            conn.execute("""
            INSERT INTO users(
                username,
                password,
                email,
                created_at
            )
            VALUES(?,?,?,?)
            """, (
                username,
                hashed_password,
                email,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ))

            conn.commit()

            flash("Account Created Successfully")

            return redirect("/login")

        except:

            flash("Username Already Exists")

        finally:

            conn.close()

    return render_template("register.html")


# =========================
# LOGIN
# =========================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form["username"]

        password = request.form["password"]

        conn = get_db()

        user = conn.execute(
            "SELECT * FROM users WHERE username=?",
            (username,)
        ).fetchone()

        conn.close()

        if user and check_password_hash(
            user["password"],
            password
        ):

            session["user_id"] = user["id"]

            session["username"] = user["username"]

            return redirect("/dashboard")

        flash("Invalid Username Or Password")

    return render_template("login.html")


# =========================
# LOGOUT
# =========================

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/login")


# =========================
# DASHBOARD
# =========================

@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()

    urls = conn.execute("""
    SELECT *
    FROM urls
    WHERE user_id=?
    ORDER BY id DESC
    """, (
        session["user_id"],
    )).fetchall()

    total_urls = conn.execute("""
    SELECT COUNT(*)
    FROM urls
    WHERE user_id=?
    """, (
        session["user_id"],
    )).fetchone()[0]

    total_clicks = conn.execute("""
    SELECT COALESCE(SUM(clicks),0)
    FROM urls
    WHERE user_id=?
    """, (
        session["user_id"],
    )).fetchone()[0]

    conn.close()

    return render_template(
        "dashboard.html",
        urls=urls,
        total_urls=total_urls,
        total_clicks=total_clicks
    )


# =========================
# SHORTEN API
# =========================

@app.route("/shorten", methods=["POST"])
def shorten_api():

    payload = request.get_json(silent=True) or request.form or {}

    long_url = (payload.get("url") or payload.get("long_url") or "").strip()

    if not long_url:
        return jsonify({"error": "Long URL is required"}), 400

    category = (payload.get("category") or "general").strip()
    custom_code = (payload.get("custom_code") or "").strip()

    code, short_url, error = create_short_url_record(
        long_url=long_url,
        category=category,
        custom_code=custom_code,
        user_id=session.get("user_id")
    )

    if error:
        return jsonify({"error": error}), 409

    qr_file = create_qr(short_url, code)
    external_short = shorten_with_isgd(long_url)

    return jsonify({
        "short_url": short_url,
        "code": code,
        "qr_file": qr_file,
        "external_short": external_short
    })


# =========================
# CREATE URL
# =========================

@app.route("/create", methods=["GET", "POST"])
def create():

    if "user_id" not in session:
        return redirect("/login")

    short_url = None
    code = None
    qr_file = None
    external_short = None

    if request.method == "POST":

        long_url = request.form["long_url"]

        category = request.form.get("category", "")

        custom_code = request.form.get("custom_code", "")

        code, short_url, error = create_short_url_record(
            long_url=long_url,
            category=category,
            custom_code=custom_code,
            user_id=session["user_id"]
        )

        if error:
            flash(error)
            return redirect("/create")

        qr_file = create_qr(short_url, code)

        # Also create an external short link via is.gd (best-effort)
        external_short = shorten_with_isgd(long_url)

        # include external short in flashed message if present
        if external_short:
            flash(f"External short: {external_short}")

        flash("Short URL Created Successfully")

    return render_template(
        "create.html",
        short_url=short_url,
        code=code,
        qr_file=qr_file,
        external_short=external_short
    )


# =========================
# REDIRECT URL
# =========================

@app.route("/<code>")
def redirect_url(code):

    conn = get_db()

    row = conn.execute("""
    SELECT *
    FROM urls
    WHERE short_code=?
    """, (
        code,
    )).fetchone()

    if not row:

        conn.close()

        return render_template("404.html")

    conn.execute("""
    UPDATE urls
    SET clicks=clicks+1
    WHERE short_code=?
    """, (
        code,
    ))

    conn.commit()

    conn.close()

    return redirect(row["long_url"])


# =========================
# DELETE URL
# =========================

@app.route("/delete/<int:id>")
def delete(id):

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()

    conn.execute("""
    DELETE FROM urls
    WHERE id=?
    AND user_id=?
    """, (
        id,
        session["user_id"]
    ))

    conn.commit()

    conn.close()

    flash("URL Deleted")

    return redirect("/dashboard")


# =========================
# TOP URLS
# =========================

@app.route("/top-urls")
def top_urls():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()

    urls = conn.execute("""
    SELECT *
    FROM urls
    WHERE user_id=?
    ORDER BY clicks DESC
    LIMIT 10
    """, (
        session["user_id"],
    )).fetchall()

    conn.close()

    return render_template(
        "top_urls.html",
        urls=urls
    )


# =========================
# PROFILE
# =========================

@app.route("/profile")
def profile():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()

    user = conn.execute("""
    SELECT *
    FROM users
    WHERE id=?
    """, (
        session["user_id"],
    )).fetchone()

    total_urls = conn.execute("""
    SELECT COUNT(*)
    FROM urls
    WHERE user_id=?
    """, (
        session["user_id"],
    )).fetchone()[0]

    total_clicks = conn.execute("""
    SELECT COALESCE(SUM(clicks),0)
    FROM urls
    WHERE user_id=?
    """, (
        session["user_id"],
    )).fetchone()[0]

    conn.close()

    return render_template(
        "profile.html",
        user=user,
        total_urls=total_urls,
        total_clicks=total_clicks
    )


# =========================
# 404
# =========================

@app.errorhandler(404)
def not_found(error):

    return render_template("404.html"), 404


# =========================
# INIT DATABASE
# =========================

with app.app_context():
    init_db()


# =========================
# RUN
# =========================

if __name__ == "__main__":

    app.run(
        host="127.0.0.1",
        port=int(os.environ.get("PORT", "5001")),
        debug=True,
        use_reloader=False
    )
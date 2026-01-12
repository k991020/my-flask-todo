import sqlite3
import os
from pathlib import Path
from functools import wraps

from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,   # JS로 쿠키 접근 차단
    SESSION_COOKIE_SAMESITE="Lax",   # CSRF 완화 (기본 방어)
)

app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key")

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "todos.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS todos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                done INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )
        conn.commit()


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            # API 요청이면 JSON으로 401 반환
            if request.path.startswith("/api/"):
                return jsonify({"error": "unauthorized"}), 401
            # 페이지 요청이면 로그인으로 redirect
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper



@app.get("/")
@login_required
def home():
    return render_template("index.html")


# ---------- Login ----------
@app.get("/login")
def login():
    if "user_id" in session:
        return redirect(url_for("home"))
    return render_template("login.html")


@app.post("/login")
def login_post():
    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""

    if not username or not password:
        return render_template("login.html", error="아이디/비밀번호를 입력해라.")

    with get_conn() as conn:
        user = conn.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?",
            (username,),
        ).fetchone()

    if user is None or not check_password_hash(user["password_hash"], password):
        return render_template("login.html", error="로그인 실패. 정보가 틀렸다.")

    session["user_id"] = user["id"]
    session["username"] = user["username"]
    return redirect(url_for("home"))

# ---------- Signup ----------
@app.get("/signup")
def signup():
    if "user_id" in session:
        return redirect(url_for("home"))
    return render_template("signup.html")


@app.post("/signup")
def signup_post():
    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""

    if len(username) < 3 or len(password) < 4:
        return render_template("signup.html", error="아이디 3자+, 비번 4자+.")

    pw_hash = generate_password_hash(password)

    try:
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, pw_hash),
            )
            conn.commit()
    except sqlite3.IntegrityError:
        return render_template("signup.html", error="이미 존재하는 아이디다.")

    return redirect(url_for("login"))


@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------- TODO API (user_id별 분리) ----------
@app.get("/api/todos")
@login_required
def list_todos():
    user_id = session["user_id"]
    flt = (request.args.get("filter") or "all").lower()

    where = "WHERE user_id = ?"
    params = [user_id]

    if flt == "active":
        where += " AND done = 0"
    elif flt == "done":
        where += " AND done = 1"

    sql = f"SELECT id, title, done FROM todos {where} ORDER BY id DESC"

    with get_conn() as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()

    todos = [{"id": r["id"], "title": r["title"], "done": bool(r["done"])} for r in rows]
    return jsonify(todos)


@app.post("/api/todos")
@login_required
def add_todo():
    user_id = session["user_id"]
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400

    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO todos (user_id, title, done) VALUES (?, ?, 0)",
            (user_id, title),
        )
        todo_id = cur.lastrowid
        row = conn.execute(
            "SELECT id, title, done FROM todos WHERE id = ? AND user_id = ?",
            (todo_id, user_id),
        ).fetchone()

    return jsonify({"id": row["id"], "title": row["title"], "done": bool(row["done"])}), 201


@app.patch("/api/todos/<int:todo_id>")
@login_required
def toggle_todo(todo_id: int):
    user_id = session["user_id"]
    with get_conn() as conn:
        row = conn.execute(
            "SELECT done FROM todos WHERE id = ? AND user_id = ?",
            (todo_id, user_id),
        ).fetchone()

        if row is None:
            return jsonify({"error": "not found"}), 404

        new_done = 0 if row["done"] else 1
        conn.execute(
            "UPDATE todos SET done = ? WHERE id = ? AND user_id = ?",
            (new_done, todo_id, user_id),
        )

        row2 = conn.execute(
            "SELECT id, title, done FROM todos WHERE id = ? AND user_id = ?",
            (todo_id, user_id),
        ).fetchone()

    return jsonify({"id": row2["id"], "title": row2["title"], "done": bool(row2["done"])})


@app.delete("/api/todos/<int:todo_id>")
@login_required
def delete_todo(todo_id: int):
    user_id = session["user_id"]
    with get_conn() as conn:
        cur = conn.execute(
            "DELETE FROM todos WHERE id = ? AND user_id = ?",
            (todo_id, user_id),
        )
        deleted = cur.rowcount

    if deleted == 0:
        return jsonify({"error": "not found"}), 404

    return jsonify({"ok": True})

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        # 이미 존재하는 아이디 체크
        if user_exists(username):
            return render_template(
                "signup.html",
                error="이미 존재하는 아이디입니다."
            )

        create_user(username, password)
        return redirect("/login")

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        with get_conn() as conn:
            user = conn.execute(
                "SELECT id, username, password_hash FROM users WHERE username = ?",
                (username,),
            ).fetchone()

        if user is None or not check_password_hash(user["password_hash"], password):
            return render_template("login.html", error="로그인 실패. 정보가 틀렸다.")

        session["user_id"] = user["id"]
        session["username"] = user["username"]
        return redirect("/")

    return render_template("login.html")


if __name__ == "__main__":
    init_db()
    debug = os.environ.get("FLASK_DEBUG") == "1"
    app.run(debug=debug)

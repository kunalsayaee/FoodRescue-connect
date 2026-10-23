import functools
import sqlite3

from flask import (Blueprint, abort, flash, g, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_db
from .utils import now_str, parse_float

bp = Blueprint("auth", __name__, url_prefix="/auth")


@bp.before_app_request
def load_user():
    user_id = session.get("user_id")
    g.user = (
        get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if user_id else None
    )


def login_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            flash("Please log in to continue.", "info")
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)
    return wrapped


def role_required(role):
    def decorator(view):
        @functools.wraps(view)
        def wrapped(*args, **kwargs):
            if g.user is None:
                flash("Please log in to continue.", "info")
                return redirect(url_for("auth.login"))
            if g.user["role"] != role:
                abort(403, f"This page is only for {role} accounts.")
            return view(*args, **kwargs)
        return wrapped
    return decorator


@bp.route("/register", methods=("GET", "POST"))
def register():
    if request.method == "POST":
        f = request.form
        name, email = f.get("name", "").strip(), f.get("email", "").strip().lower()
        password, role = f.get("password", ""), f.get("role", "")
        error = None
        if not name:
            error = "Enter your name."
        elif "@" not in email:
            error = "Enter a valid email address."
        elif len(password) < 8:
            error = "Password must be at least 8 characters."
        elif role not in ("donor", "ngo"):
            error = "Choose whether you donate food or collect it."
        if error is None:
            try:
                db = get_db()
                db.execute(
                    "INSERT INTO users (name, email, password_hash, role, organization, phone, city, lat, lng, created_at)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (name, email, generate_password_hash(password), role,
                     f.get("organization", "").strip(), f.get("phone", "").strip(),
                     f.get("city", "").strip(), parse_float(f.get("lat")),
                     parse_float(f.get("lng")), now_str()),
                )
                db.commit()
            except sqlite3.IntegrityError:
                error = "That email is already registered."
            else:
                flash("Account created. You can log in now.", "success")
                return redirect(url_for("auth.login"))
        flash(error, "error")
    return render_template("register.html")


@bp.route("/login", methods=("GET", "POST"))
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = get_db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if user is None or not check_password_hash(user["password_hash"], request.form.get("password", "")):
            flash("Email or password is incorrect.", "error")
        else:
            session.clear()
            session["user_id"] = user["id"]
            return redirect(url_for("main.dashboard"))
    return render_template("login.html")


@bp.route("/logout", methods=("POST",))
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("main.index"))

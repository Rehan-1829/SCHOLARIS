"""Sign in, sign out and password changes."""

from collections import defaultdict, deque
from datetime import datetime, timedelta
from urllib.parse import urlsplit

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user

from ..extensions import db
from ..models import User

bp = Blueprint("auth", __name__)

# Simple in-process throttle. Good enough for a single-worker college deployment;
# a production system would keep this in Redis.
_failures: dict[str, deque] = defaultdict(deque)


def _client_key(email: str) -> str:
    return f"{request.remote_addr}|{email}".lower()


def _recent_failures(key: str) -> int:
    window = timedelta(minutes=current_app.config["LOGIN_WINDOW_MINUTES"])
    cutoff = datetime.utcnow() - window
    attempts = _failures[key]
    while attempts and attempts[0] < cutoff:
        attempts.popleft()
    return len(attempts)


def _safe_next(target: str | None) -> str:
    if not target:
        return ""
    parts = urlsplit(target)
    if parts.scheme or parts.netloc or not target.startswith("/"):
        return ""
    return target


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        key = _client_key(email)

        if _recent_failures(key) >= current_app.config["LOGIN_MAX_ATTEMPTS"]:
            flash("Too many failed attempts. Wait a few minutes and try again.", "error")
            return render_template("auth/login.html", email=email), 429

        user = User.query.filter(db.func.lower(User.email) == email).first()
        if user is None or not user.check_password(password):
            _failures[key].append(datetime.utcnow())
            flash("That email and password do not match an account.", "error")
            return render_template("auth/login.html", email=email), 401

        if not user.is_active:
            flash("This account has been deactivated. Contact the registrar.", "error")
            return render_template("auth/login.html", email=email), 403

        _failures.pop(key, None)
        login_user(user)
        user.last_login_at = datetime.utcnow()
        db.session.commit()

        destination = _safe_next(request.args.get("next"))
        if destination:
            return redirect(destination)
        return redirect(url_for("dashboard.index"))

    return render_template("auth/login.html", email="")


@bp.post("/logout")
@login_required
def logout():
    logout_user()
    flash("Signed out.", "info")
    return redirect(url_for("auth.login"))


@bp.route("/account", methods=["GET", "POST"])
@login_required
def account():
    if request.method == "POST":
        current_password = request.form.get("current_password") or ""
        new_password = request.form.get("new_password") or ""
        confirm = request.form.get("confirm_password") or ""

        if not current_user.check_password(current_password):
            flash("Current password is incorrect.", "error")
        elif len(new_password) < 8:
            flash("New password must be at least 8 characters.", "error")
        elif new_password != confirm:
            flash("New passwords do not match.", "error")
        else:
            current_user.set_password(new_password)
            db.session.commit()
            flash("Password updated.", "success")
            return redirect(url_for("auth.account"))

    return render_template("auth/account.html")

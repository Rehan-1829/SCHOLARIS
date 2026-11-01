"""Application factory for Scholaris."""

from datetime import date
from pathlib import Path

from flask import Flask, render_template
from flask_login import current_user

from .config import Config
from .extensions import csrf, db, login_manager


def create_app(config_object=Config) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_object)
    # A hosted Postgres deployment runs on a read-only filesystem; only a local
    # SQLite database needs the instance folder to exist.
    if app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite"):
        Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)

    from .models import User

    @login_manager.user_loader
    def load_user(user_id: str):
        return db.session.get(User, int(user_id))

    from .blueprints.auth import bp as auth_bp
    from .blueprints.courses import bp as courses_bp
    from .blueprints.dashboard import bp as dashboard_bp
    from .blueprints.finance import bp as finance_bp
    from .blueprints.reports import bp as reports_bp
    from .blueprints.students import bp as students_bp

    for blueprint in (
        auth_bp,
        dashboard_bp,
        students_bp,
        courses_bp,
        finance_bp,
        reports_bp,
    ):
        app.register_blueprint(blueprint)

    @app.context_processor
    def inject_layout_globals():
        return {
            "current_term": app.config["CURRENT_TERM"],
            "college_name": app.config["COLLEGE_NAME"],
            "attendance_threshold": app.config["ATTENDANCE_THRESHOLD"],
            "today": date.today(),
        }

    @app.template_filter("money")
    def money(value) -> str:
        try:
            amount = float(value or 0)
        except (TypeError, ValueError):
            amount = 0.0
        formatted = f"{amount:,.2f}"
        if formatted.endswith(".00"):
            formatted = formatted[:-3]
        return f"₹{formatted}"

    @app.template_filter("pct")
    def pct(value, digits: int = 1) -> str:
        if value is None:
            return "—"
        return f"{float(value):.{digits}f}%"

    @app.template_filter("method")
    def method_label(value) -> str:
        labels = {
            "upi": "UPI",
            "netbanking": "Net banking",
            "card": "Card",
            "cash": "Cash",
            "cheque": "Cheque",
            "scholarship": "Scholarship",
        }
        return labels.get(value or "", (value or "").title())

    @app.template_filter("day")
    def day(value) -> str:
        if not value:
            return "—"
        return value.strftime("%d %b %Y")

    @app.template_filter("iso_day")
    def iso_day(value) -> str:
        if not value:
            return ""
        return value.isoformat()

    @app.errorhandler(403)
    def forbidden(_error):
        return render_template("error.html", code=403, title="Not your record",
                               message="Your account does not have access to this page."), 403

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("error.html", code=404, title="Nothing filed here",
                               message="That page or record does not exist."), 404

    @app.errorhandler(500)
    def server_error(_error):  # pragma: no cover - defensive
        db.session.rollback()
        return render_template("error.html", code=500, title="Something broke",
                               message="The registrar hit an internal error. Try again."), 500

    from .cli import register_cli

    register_cli(app)

    with app.app_context():
        db.create_all()

    return app

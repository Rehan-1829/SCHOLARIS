"""Small request-parsing helpers used by several blueprints."""

from datetime import date, datetime


def clean(value) -> str:
    return (value or "").strip()


def parse_date(value, default=None):
    value = clean(value)
    if not value:
        return default
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return default


def parse_int(value, default=None):
    try:
        return int(clean(value))
    except (TypeError, ValueError):
        return default


def parse_float(value, default=None):
    try:
        return float(clean(value))
    except (TypeError, ValueError):
        return default


def parse_decimal(value, default=None):
    from decimal import Decimal, InvalidOperation

    try:
        return Decimal(clean(value))
    except (InvalidOperation, TypeError, ValueError):
        return default


def default_term() -> str:
    from flask import current_app

    return current_app.config["CURRENT_TERM"]


def today() -> date:
    return date.today()

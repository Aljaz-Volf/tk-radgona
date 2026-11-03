from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from flask import current_app


def utc_now_naive():
    """Return UTC in the representation used by SQLite DateTime columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def local_today():
    """Return today's date in the club's configured timezone."""
    return datetime.now(ZoneInfo(current_app.config["APP_TIMEZONE"])).date()


def one_year_after(value):
    """Return the same calendar date next year, clamping leap day to 28 February."""
    try:
        return value.replace(year=value.year + 1)
    except ValueError:
        return value.replace(year=value.year + 1, day=28)


def local_to_utc(value):
    """Convert a value entered in the club's local time to naive UTC."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=ZoneInfo(current_app.config["APP_TIMEZONE"]))
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def utc_to_local(value):
    """Convert a stored UTC value for a datetime-local form field."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(ZoneInfo(current_app.config["APP_TIMEZONE"])).replace(tzinfo=None)

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from flask import current_app


def utc_now_naive():
    """Return UTC in the representation used by SQLite DateTime columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


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

from datetime import datetime
from math import asin, cos, radians, sin, sqrt

DT_FORMAT = "%Y-%m-%dT%H:%M"


def now_str():
    return datetime.now().strftime(DT_FORMAT)


def parse_dt(value):
    try:
        return datetime.strptime(value, DT_FORMAT)
    except (TypeError, ValueError):
        return None


def parse_float(value):
    try:
        return float(value) if value not in (None, "") else None
    except ValueError:
        return None


def haversine_km(lat1, lng1, lat2, lng2):
    """Great-circle distance between two points in kilometres."""
    lat1, lng1, lat2, lng2 = map(radians, (lat1, lng1, lat2, lng2))
    a = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lng2 - lng1) / 2) ** 2
    return 6371 * 2 * asin(sqrt(a))


def minutes_left(expires_at):
    dt = parse_dt(expires_at)
    if not dt:
        return 0
    return int((dt - datetime.now()).total_seconds() // 60)


def time_left(expires_at):
    m = minutes_left(expires_at)
    if m <= 0:
        return "expired"
    h, mins = divmod(m, 60)
    if h >= 24:
        return f"{h // 24}d {h % 24}h left"
    return f"{h}h {mins:02d}m left" if h else f"{mins}m left"


def pretty_dt(value):
    dt = parse_dt(value)
    return dt.strftime("%d %b, %I:%M %p") if dt else (value or "")

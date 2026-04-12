import re
from calendar import monthrange
from datetime import date, timedelta


def normalize_phone(phone: str | None) -> str | None:
    if phone is None:
        return None
    digits = re.sub(r"\D", "", phone)
    return digits or None


def add_one_month(value: date) -> date:
    month = value.month + 1
    year = value.year
    if month == 13:
        month = 1
        year += 1
    day = min(value.day, monthrange(year, month)[1])
    return date(year, month, day)


def calculate_end_date(start_date: date, duration_type: str | None, duration_days: int | None) -> date | None:
    if duration_type == "한달":
        return add_one_month(start_date) - timedelta(days=1)
    if duration_days:
        return start_date + timedelta(days=duration_days - 1)
    return None

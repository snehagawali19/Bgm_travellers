from datetime import UTC, datetime
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def to_ist(value: datetime) -> datetime:
    return as_utc(value).astimezone(IST)


def ist_day_bounds(date_str: str) -> tuple[datetime, datetime]:
    start = datetime.fromisoformat(f"{date_str}T00:00:00").replace(tzinfo=IST)
    end = datetime.fromisoformat(f"{date_str}T23:59:59.999999").replace(tzinfo=IST)
    return start.astimezone(UTC), end.astimezone(UTC)

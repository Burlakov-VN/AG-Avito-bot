"""Generate DateBegin field for Avito rows."""

from datetime import date, datetime, timedelta, timezone


def generate_date_begin(rules: dict, index: int = 0, total: int = 1) -> str:
    """Generate DateBegin based on date rules.

    Modes:
        single: one date for all rows (single_date or today)
        range: distribute rows evenly across date range

    Supports ISO 8601 format with timezone:
        date_format: "iso" → 2025-11-19T08:15:00+05:00
    """
    fmt = rules.get("date_format", "iso")
    tz_offset_hours = rules.get("timezone_offset", 5)
    tz = timezone(timedelta(hours=tz_offset_hours))
    base_hour = rules.get("base_hour", 8)
    minute_step = rules.get("minute_step", 7)
    mode = rules.get("mode", "single")

    if mode == "range":
        start_str = rules.get("range_start")
        end_str = rules.get("range_end")
        if start_str and end_str:
            start = date.fromisoformat(start_str)
            end = date.fromisoformat(end_str)
            if total <= 1:
                d = start
            else:
                delta = (end - start).days
                day_offset = int(delta * index / (total - 1))
                d = start + timedelta(days=day_offset)
            return _format_date(d, fmt, tz, base_hour, minute_step, index)
    # single mode
    single = rules.get("single_date")
    if single:
        d = date.fromisoformat(single)
    else:
        d = date.today()
    return _format_date(d, fmt, tz, base_hour, minute_step, index)


def _format_date(
    d: date,
    fmt: str,
    tz: timezone,
    base_hour: int,
    minute_step: int,
    index: int,
) -> str:
    """Format date with optional ISO 8601 datetime output."""
    if fmt == "iso":
        # Stagger times: 08:00, 08:07, 08:14, ...
        total_minutes = base_hour * 60 + (index * minute_step)
        hour = total_minutes // 60
        minute = total_minutes % 60
        # Wrap around 24h
        hour = hour % 24
        dt = datetime(d.year, d.month, d.day, hour, minute, 0, tzinfo=tz)
        return dt.isoformat()
    return d.strftime(fmt)

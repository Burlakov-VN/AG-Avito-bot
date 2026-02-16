"""Generate DateBegin field for Avito rows."""

from datetime import date, timedelta


def generate_date_begin(rules: dict, index: int = 0, total: int = 1) -> str:
    """Generate DateBegin based on date rules.

    Modes:
        single: one date for all rows (single_date or today)
        range: distribute rows evenly across date range
    """
    fmt = rules.get("date_format", "%d.%m.%Y")
    mode = rules.get("mode", "single")

    if mode == "range":
        start_str = rules.get("range_start")
        end_str = rules.get("range_end")
        if start_str and end_str:
            start = date.fromisoformat(start_str)
            end = date.fromisoformat(end_str)
            if total <= 1:
                return start.strftime(fmt)
            delta = (end - start).days
            day_offset = int(delta * index / (total - 1))
            return (start + timedelta(days=day_offset)).strftime(fmt)

    # single mode
    single = rules.get("single_date")
    if single:
        d = date.fromisoformat(single)
    else:
        d = date.today()
    return d.strftime(fmt)

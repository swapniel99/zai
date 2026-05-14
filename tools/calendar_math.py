"""calendar_math tool — resolves natural language date expressions to concrete dates."""

import calendar
import re
from datetime import datetime, timedelta

import dateparser
import parsedatetime


_cal = parsedatetime.Calendar()

_FUZZY_MONTH_PATTERN = re.compile(
    r"(early|mid(?:dle)?|late)\s+"
    r"(january|february|march|april|may|june|july|august|september|october|november|december)"
    r"(?:\s+(\d{4}))?",
    re.IGNORECASE,
)
_FUZZY_DAY = {"early": 5, "mid": 15, "middle": 15, "late": 25}

_ORDINAL_PATTERN = re.compile(
    r"(last|first|second|third|fourth)\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
    r"\s+(?:of\s+)?(january|february|march|april|may|june|july|august|september|october|november|december)"
    r"(?:\s+(\d{4}))?",
    re.IGNORECASE,
)

_WEEKDAY_MAP = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}
_MONTH_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}
_ORDINAL_MAP = {"first": 0, "second": 1, "third": 2, "fourth": 3, "last": -1}


def _resolve_fuzzy_month(query: str, now: datetime) -> datetime | None:
    """Resolves 'early/mid/late [Month] [Year]' to an approximate date."""
    m = _FUZZY_MONTH_PATTERN.search(query)
    if not m:
        return None
    fuzzy, month_name, year_str = m.groups()
    year = int(year_str) if year_str else now.year
    month = _MONTH_MAP[month_name.lower()]
    # If month already passed this year and no year specified, use next year
    if not year_str and datetime(year, month, 1) < now:
        year += 1
    day = _FUZZY_DAY[fuzzy.lower()]
    # Clamp to last day of month
    last_day = calendar.monthrange(year, month)[1]
    day = min(day, last_day)
    return datetime(year, month, day)


def _resolve_ordinal_weekday(query: str, now: datetime) -> datetime | None:
    """Resolves expressions like 'last Sunday of December 2026'."""
    m = _ORDINAL_PATTERN.search(query)
    if not m:
        return None

    ordinal, weekday_name, month_name, year_str = m.groups()
    year = int(year_str) if year_str else now.year
    month = _MONTH_MAP[month_name.lower()]
    target_weekday = _WEEKDAY_MAP[weekday_name.lower()]
    ordinal_idx = _ORDINAL_MAP[ordinal.lower()]

    # calendar.monthcalendar returns weeks; 0 = day not in month
    weeks = calendar.monthcalendar(year, month)
    days = [week[target_weekday] for week in weeks if week[target_weekday] != 0]

    if not days:
        return None

    day = days[ordinal_idx]
    return datetime(year, month, day)


def _resolve_parsedatetime(query: str, now: datetime) -> datetime | None:
    result, parse_status = _cal.parseDT(query, sourceTime=now)
    # parse_status: 0 = failed, 1 = time only, 2 = date only, 3 = date+time
    # Accept status=1 when date differs from today — parsedatetime quirk for
    # relative weekday expressions like "next Friday" that set status=1 but
    # correctly advance the date component.
    if parse_status in (2, 3):
        return result
    if parse_status == 1 and result.date() != now.date():
        return result
    return None


def _resolve_dateparser(query: str, now: datetime) -> datetime | None:
    result = dateparser.parse(
        query,
        settings={
            "PREFER_DATES_FROM": "future",
            "RELATIVE_BASE": now,
            "RETURN_AS_TIMEZONE_AWARE": False,
        },
    )
    return result


def calendar_math(query: str) -> str:
    """
    Resolves a natural language date expression to a concrete date string.
    Use this tool whenever you need to calculate or verify a specific date.
    Always prefer this tool over guessing dates yourself.

    Supported expression types (use these patterns):
    - Fuzzy month        : "early May", "mid October", "late April 2027"
    - Ordinal weekday    : "last Sunday of December", "first Monday of March 2027",
                          "third Friday of August"
    - Relative offsets   : "14 days from today", "3 weeks from now", "in 2 months",
                          "next Friday", "next Tuesday"
    - Absolute dates     : "March 22", "October 31 2027", "tomorrow", "today"
    """
    now = datetime.now()

    result = (
        _resolve_fuzzy_month(query, now)
        or _resolve_ordinal_weekday(query, now)
        or _resolve_parsedatetime(query, now)
        or _resolve_dateparser(query, now)
    )

    if result is None:
        return f"Could not resolve date expression: '{query}'"

    day_name = result.strftime("%A")
    date_str = result.strftime("%Y-%m-%d")
    human_str = result.strftime("%B %d, %Y")
    return f"{day_name}, {human_str} ({date_str})"


if __name__ == "__main__":
    cases = [
        "last Sunday of December",
        "last Sunday of December 2026",
        "first Monday of March 2027",
        "14 days from today",
        "3 weeks from now",
        "next Friday",
        "March 22",
        "late April",
        "early June 2027",
        "mid September",
        "today",
        "tomorrow",
    ]
    for q in cases:
        print(f"  {q!r:45} -> {calendar_math(q)}")

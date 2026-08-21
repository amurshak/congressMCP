"""Congress-number / calendar helpers.

Congress N convenes on January 3 of year 1789 + 2*(N-1) and runs two years.
Kept free of network and server imports so feature modules and tests can use
it directly.
"""
from datetime import date, datetime, timezone
from typing import Optional


def congress_start_year(congress: int) -> int:
    """First calendar year of the given Congress (119 -> 2025)."""
    return 1789 + 2 * (congress - 1)


def congress_start_date(congress: int) -> date:
    """Convening date of the given Congress (January 3 of its first year)."""
    return date(congress_start_year(congress), 1, 3)


def current_congress(today: Optional[date] = None) -> int:
    """Congress in session on `today` (UTC) -- defaults to now.

    Between January 1 and January 2 of an odd year the previous Congress is
    still seated, so those two days roll back by one.
    """
    today = today or datetime.now(timezone.utc).date()
    congress = (today.year - 1789) // 2 + 1
    if today.year % 2 == 1 and today < date(today.year, 1, 3):
        congress -= 1
    return congress


def iso_utc(d: date) -> str:
    """Render a date as the Congress.gov `YYYY-MM-DDT00:00:00Z` form."""
    return f"{d.isoformat()}T00:00:00Z"

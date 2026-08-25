"""Shared Retry-After parsing for the Congress.gov and GovInfo clients.

Extracted from congress_api/features/bill_text/client.py's original
`_retry_after` (issue #58 code review): that helper had no clamp on the
numeric branch, so a negative, zero, or non-finite ``Retry-After`` value
(`"-30"`, `"nan"`, a past HTTP-date after clock skew) sailed straight into
``asyncio.sleep()`` -- a negative/zero value fires the retry immediately
(worse than no Retry-After handling at all against a throttled key), and
``asyncio.sleep(float('nan'))`` never returns. Both congress_api/core/api_wrapper.py
and bill_text/client.py backed off using a copy of the same unclamped logic;
this is the one fixed implementation both call.
"""

import math
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional


def parse_retry_after(value: Optional[str]) -> Optional[float]:
    """Seconds to wait from a Retry-After header value, or None if unusable.

    Retry-After is either a delay in seconds or an HTTP-date (RFC 7231
    §7.1.3). A parsed value that isn't a positive, finite number of seconds
    (negative, zero, NaN, infinite, or a past HTTP-date) is treated the same
    as a missing header -- None -- so callers fall back to their own
    backoff instead of sleeping for zero seconds or hanging forever.
    """
    if not value:
        return None
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        try:
            seconds = (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds()
        except (TypeError, ValueError):
            return None
    if not math.isfinite(seconds) or seconds <= 0:
        return None
    return seconds

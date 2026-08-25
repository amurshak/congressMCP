"""Issue #58 code review: the shared Retry-After parser must reject values
that would fire a retry immediately (negative, zero) or hang forever
(NaN/infinite) instead of sleeping them literally. This is the one
implementation both congress_api/core/api_wrapper.py and
congress_api/features/bill_text/client.py's GovInfo backoff use.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from congress_api.core.retry_timing import parse_retry_after


def test_numeric_seconds():
    assert parse_retry_after("3") == 3.0
    assert parse_retry_after("0.5") == 0.5


def test_missing_or_empty_is_none():
    assert parse_retry_after(None) is None
    assert parse_retry_after("") is None


def test_negative_seconds_rejected():
    """A negative Retry-After must not fire the retry with zero/negative
    delay -- that is strictly worse than no Retry-After handling."""
    assert parse_retry_after("-30") is None


def test_zero_seconds_rejected():
    assert parse_retry_after("0") is None


def test_nan_rejected():
    """asyncio.sleep(float('nan')) never returns; NaN must not reach it."""
    assert parse_retry_after("nan") is None


def test_infinity_rejected():
    assert parse_retry_after("inf") is None


def test_garbage_string_is_none():
    assert parse_retry_after("soon") is None


def test_future_http_date_returns_positive_seconds():
    from datetime import datetime, timedelta, timezone
    from email.utils import format_datetime

    future = datetime.now(timezone.utc) + timedelta(seconds=45)
    value = format_datetime(future, usegmt=True)
    seconds = parse_retry_after(value)
    assert seconds is not None
    assert 40 <= seconds <= 50


def test_past_http_date_rejected():
    """Clock skew or a stale cached 429 can carry a Retry-After date already
    in the past; that must fall back to backoff, not sleep(0) or negative."""
    assert parse_retry_after("Wed, 21 Oct 2015 07:28:00 GMT") is None


def test_result_is_always_finite_and_positive():
    """Every non-None result must be safe to hand straight to asyncio.sleep --
    the property the unclamped original helper violated (a negative/NaN
    value sailed through as-is)."""
    for value in ["-30", "0", "nan", "inf", "-inf",
                  "Wed, 21 Oct 2015 07:28:00 GMT", "garbage", None, ""]:
        seconds = parse_retry_after(value)
        if seconds is not None:
            assert math.isfinite(seconds) and seconds > 0

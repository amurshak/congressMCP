"""Issue #58: a 429 from Congress.gov must not be retried immediately and in
quick succession -- it must honor Retry-After (falling back to exponential
backoff with jitter, capped), surface X-RateLimit-Remaining when exhausted,
and per-endpoint timeouts must actually reach httpx.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class FakeContext:
    async def info(self, *_):
        pass

    async def error(self, *_):
        pass


def _rate_limited(retry_after=None, remaining=None):
    return {
        "error": "API request failed: 429",
        "status_code": 429,
        "request_time": 0.01,
        "retry_after": retry_after,
        "rate_limit_remaining": remaining,
    }


# ---------------------------------------------------------------------------
# DefensiveAPIWrapper: Retry-After pacing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_429_sleeps_for_retry_after_seconds():
    """A numeric Retry-After header paces the retry, not the blind backoff."""
    from congress_api.core import api_wrapper as mod
    from congress_api.core.exceptions import CongressionalAPIError

    sleep_calls = []

    async def fake_sleep(seconds):
        sleep_calls.append(seconds)

    with patch.object(mod, "make_api_request",
                      AsyncMock(return_value=_rate_limited(retry_after="3"))), \
            patch.object(mod.asyncio, "sleep", fake_sleep):
        with pytest.raises(CongressionalAPIError):
            await mod.safe_congressional_request("/bill/119", FakeContext(), {},
                                                 endpoint_type="bills")  # retry_count=3

    # Every retry used the server's Retry-After value (3s), not 1s/2s/4s backoff.
    assert sleep_calls == [3, 3, 3]


@pytest.mark.asyncio
async def test_429_retry_after_beyond_cap_is_capped_not_abandoned():
    """A Retry-After longer than the endpoint's max_retry_delay is still
    honored, just capped -- per spec (documentation/fulltext/03-data-
    sources.md's rate-limits section): "respect Retry-After on both 429 and
    503, capped at a maximum wait." Capped-and-retried, not abandoned."""
    from congress_api.core import api_wrapper as mod
    from congress_api.core.exceptions import CongressionalAPIError

    sleep_calls = []

    async def fake_sleep(seconds):
        sleep_calls.append(seconds)

    mock = AsyncMock(return_value=_rate_limited(retry_after="120"))
    with patch.object(mod, "make_api_request", mock), \
            patch.object(mod.asyncio, "sleep", fake_sleep):
        with pytest.raises(CongressionalAPIError) as ei:
            await mod.safe_congressional_request("/bill/119", FakeContext(), {},
                                                 endpoint_type="default")  # max_retry_delay=5.0

    assert mock.await_count == 2  # 1 initial + 1 retry (default retry_count=1)
    assert sleep_calls == [5.0]  # capped, not the raw 120s
    assert ei.value.error_response.error_code == "RATE_LIMIT_EXCEEDED"


@pytest.mark.asyncio
async def test_429_without_retry_after_falls_back_to_backoff_with_jitter():
    """No Retry-After header: exponential backoff+jitter, still capped -- and
    still far from 'retried immediately'."""
    from congress_api.core import api_wrapper as mod
    from congress_api.core.exceptions import CongressionalAPIError

    sleep_calls = []

    async def fake_sleep(seconds):
        sleep_calls.append(seconds)

    with patch.object(mod, "make_api_request",
                      AsyncMock(return_value=_rate_limited())), \
            patch.object(mod.asyncio, "sleep", fake_sleep):
        with pytest.raises(CongressionalAPIError):
            await mod.safe_congressional_request("/bill/119", FakeContext(), {},
                                                 endpoint_type="bills")  # retry_count=3

    assert len(sleep_calls) == 3
    # First backoff step starts near retry_delay=1.0 (+ up to 0.25 jitter).
    assert 1.0 <= sleep_calls[0] <= 1.25
    # Later steps grow (backoff_multiplier=2.0) up to the 5.0s cap.
    assert sleep_calls[-1] <= 5.0
    assert sleep_calls[0] <= sleep_calls[-1]


def test_next_delay_backoff_clamp_actually_fires():
    """A direct check that the exponential-backoff branch's min(..., cap) is
    load-bearing -- 'bills' (retry_count=3) never grows past 4.25s so the
    wrapper-level test above passes whether or not the clamp exists."""
    from congress_api.core.api_wrapper import _next_delay

    assert _next_delay(None, fallback_delay=10.0, cap=5.0) == 5.0
    assert _next_delay(None, fallback_delay=1.0, cap=5.0) <= 5.0


@pytest.mark.asyncio
async def test_rate_limit_remaining_surfaced_when_exhausted():
    from congress_api.core import api_wrapper as mod
    from congress_api.core.exceptions import CongressionalAPIError

    with patch.object(mod, "make_api_request",
                      AsyncMock(return_value=_rate_limited(retry_after="1", remaining="0"))), \
            patch.object(mod.asyncio, "sleep", AsyncMock()):
        with pytest.raises(CongressionalAPIError) as ei:
            await mod.safe_congressional_request("/bill/119", FakeContext(), {},
                                                 endpoint_type="default")

    err = ei.value.error_response
    assert err.error_code == "RATE_LIMIT_EXCEEDED"
    assert "X-RateLimit-Remaining: 0" in err.message


@pytest.mark.asyncio
async def test_503_also_honors_retry_after():
    """503 shares the Retry-After treatment with 429 (both are in
    _RETRY_AFTER_STATUSES, mirroring the GovInfo client's {429, 503})."""
    from congress_api.core import api_wrapper as mod
    from congress_api.core.exceptions import CongressionalAPIError

    def _unavailable(retry_after):
        return {"error": "API request failed: 503", "status_code": 503,
                "request_time": 0.01, "retry_after": retry_after,
                "rate_limit_remaining": None}

    sleep_calls = []

    async def fake_sleep(seconds):
        sleep_calls.append(seconds)

    with patch.object(mod, "make_api_request",
                      AsyncMock(return_value=_unavailable("2"))), \
            patch.object(mod.asyncio, "sleep", fake_sleep):
        with pytest.raises(CongressionalAPIError) as ei:
            await mod.safe_congressional_request("/bill/119", FakeContext(), {},
                                                 endpoint_type="bills")  # retry_count=3

    assert sleep_calls == [2, 2, 2]
    assert ei.value.error_response.error_code == "SERVER_ERROR"


@pytest.mark.asyncio
async def test_unusable_retry_after_falls_back_to_backoff_not_immediate_retry():
    """A negative/NaN Retry-After (issue #58 code review) must not fire the
    next attempt with ~0 delay against a key that's still being throttled --
    it should be treated the same as no header at all."""
    from congress_api.core import api_wrapper as mod
    from congress_api.core.exceptions import CongressionalAPIError

    sleep_calls = []

    async def fake_sleep(seconds):
        sleep_calls.append(seconds)

    with patch.object(mod, "make_api_request",
                      AsyncMock(return_value=_rate_limited(retry_after="-30"))), \
            patch.object(mod.asyncio, "sleep", fake_sleep):
        with pytest.raises(CongressionalAPIError):
            await mod.safe_congressional_request("/bill/119", FakeContext(), {},
                                                 endpoint_type="bills")

    assert all(s >= 1.0 for s in sleep_calls)


@pytest.mark.asyncio
async def test_rate_limit_remaining_omitted_when_nonzero():
    from congress_api.core import api_wrapper as mod
    from congress_api.core.exceptions import CongressionalAPIError

    with patch.object(mod, "make_api_request",
                      AsyncMock(return_value=_rate_limited(retry_after="1", remaining="42"))), \
            patch.object(mod.asyncio, "sleep", AsyncMock()):
        with pytest.raises(CongressionalAPIError) as ei:
            await mod.safe_congressional_request("/bill/119", FakeContext(), {},
                                                 endpoint_type="default")

    assert "X-RateLimit-Remaining" not in ei.value.error_response.message


@pytest.mark.asyncio
async def test_wrapper_passes_endpoint_timeout_to_make_api_request():
    """The per-endpoint config.timeout (issue #58) must actually reach
    make_api_request, not just be computed and discarded."""
    from congress_api.core import api_wrapper as mod

    mock = AsyncMock(return_value={"result": "ok"})
    with patch.object(mod, "make_api_request", mock):
        await mod.safe_congressional_request("/bound-congressional-record/2020",
                                             FakeContext(), {})  # timeout=15.0

    assert mock.await_args.kwargs["timeout"] == 15.0


# ---------------------------------------------------------------------------
# client_handler: timeout actually reaches httpx, headers are captured
# ---------------------------------------------------------------------------

class _FakeAppContext:
    def __init__(self, client):
        self.client = client
        self.api_key = "TESTKEY"
        self.request_count = 0


class _FakeRequestContext:
    def __init__(self, app_ctx):
        self.lifespan_context = app_ctx


class _FakeCtx:
    def __init__(self, app_ctx):
        self.request_context = _FakeRequestContext(app_ctx)

    def error(self, *_):
        pass


@pytest.mark.asyncio
async def test_make_api_request_forwards_timeout_kwarg_to_httpx():
    from congress_api.core import client_handler as mod

    response = MagicMock()
    response.json.return_value = {"ok": True}
    fake_client = MagicMock()
    fake_client.get = AsyncMock(return_value=response)

    with patch.object(mod, "ENABLE_CACHING", False):
        await mod.make_api_request("/bill/119", _FakeCtx(_FakeAppContext(fake_client)),
                                    {"limit": 5}, timeout=8.0)

    # A bare float would also loosen the 5s connect timeout the client was
    # built with and tie write/pool to a value meant to vary per-endpoint
    # for reads; only the read leg should track the override.
    import httpx
    sent_timeout = fake_client.get.await_args.kwargs["timeout"]
    assert sent_timeout == httpx.Timeout(connect=5.0, read=8.0, write=10.0, pool=10.0)
    assert sent_timeout.connect == 5.0
    assert sent_timeout.read == 8.0
    assert sent_timeout.write == 10.0
    assert sent_timeout.pool == 10.0


@pytest.mark.asyncio
async def test_make_api_request_omits_timeout_kwarg_when_not_given():
    """Passing timeout=None straight to httpx disables the timeout outright,
    so an unset override must not appear in the call at all."""
    from congress_api.core import client_handler as mod

    response = MagicMock()
    response.json.return_value = {"ok": True}
    fake_client = MagicMock()
    fake_client.get = AsyncMock(return_value=response)

    with patch.object(mod, "ENABLE_CACHING", False):
        await mod.make_api_request("/bill/119", _FakeCtx(_FakeAppContext(fake_client)), {})

    assert "timeout" not in fake_client.get.await_args.kwargs


@pytest.mark.asyncio
async def test_make_api_request_captures_retry_after_and_rate_limit_headers():
    import httpx
    from congress_api.core import client_handler as mod

    request = httpx.Request("GET", "https://api.congress.gov/v3/bill/119")
    response = httpx.Response(
        429, request=request,
        headers={"Retry-After": "7", "X-RateLimit-Remaining": "0"},
    )
    fake_client = MagicMock()
    fake_client.get = AsyncMock(return_value=response)

    with patch.object(mod, "ENABLE_CACHING", False):
        result = await mod.make_api_request(
            "/bill/119", _FakeCtx(_FakeAppContext(fake_client)), {})

    assert result["status_code"] == 429
    assert result["retry_after"] == "7"
    assert result["rate_limit_remaining"] == "0"


@pytest.mark.asyncio
async def test_make_api_request_reports_timeout_distinctly():
    """A real httpx timeout must be classifiable as API_TIMEOUT downstream,
    not collapsed into the generic 'Network error' message."""
    import httpx
    from congress_api.core import client_handler as mod

    fake_client = MagicMock()
    fake_client.get = AsyncMock(side_effect=httpx.ReadTimeout("timed out"))

    with patch.object(mod, "ENABLE_CACHING", False):
        result = await mod.make_api_request(
            "/bill/119", _FakeCtx(_FakeAppContext(fake_client)), {}, timeout=8.0)

    assert "timeout" in result["error"].lower()
    assert "status_code" not in result


@pytest.mark.asyncio
async def test_timeout_message_does_not_leak_endpoint_digits():
    """The returned error message must not embed the endpoint: an endpoint
    like /bill/118/hr/404 would false-positive api_wrapper's no-status-code
    '400'/'404' substring scan and wrongly short-circuit retries on a plain
    timeout (issue #58 code review)."""
    import httpx
    from congress_api.core import client_handler as mod

    fake_client = MagicMock()
    fake_client.get = AsyncMock(side_effect=httpx.ReadTimeout("timed out"))

    with patch.object(mod, "ENABLE_CACHING", False):
        result = await mod.make_api_request(
            "/bill/118/hr/404", _FakeCtx(_FakeAppContext(fake_client)), {})

    assert "404" not in result["error"]
    assert "400" not in result["error"]


@pytest.mark.asyncio
async def test_timeout_on_endpoint_with_404_in_path_still_retries():
    """End-to-end: a real timeout against an endpoint whose path contains
    '404' must still use the endpoint's full retry budget, not short-circuit
    the way an actual 404 status does."""
    import httpx
    from congress_api.core import api_wrapper as mod
    from congress_api.core.exceptions import CongressionalAPIError

    fake_client = MagicMock()
    fake_client.get = AsyncMock(side_effect=httpx.ReadTimeout("timed out"))
    ctx = _FakeCtx(_FakeAppContext(fake_client))

    with patch("congress_api.core.client_handler.ENABLE_CACHING", False), \
            patch.object(mod.asyncio, "sleep", AsyncMock()):
        with pytest.raises(CongressionalAPIError) as ei:
            await mod.safe_congressional_request("/bill/118/hr/404", ctx, {},
                                                 endpoint_type="bills")  # retry_count=3

    assert fake_client.get.await_count == 4  # 1 initial + 3 retries, none skipped
    assert ei.value.error_response.error_code == "API_TIMEOUT"


@pytest.mark.asyncio
async def test_wrapper_classifies_real_timeout_as_api_timeout():
    """End-to-end through DefensiveAPIWrapper: the distinct timeout message
    from make_api_request must classify as API_TIMEOUT."""
    import httpx
    from congress_api.core import api_wrapper as mod
    from congress_api.core.exceptions import CongressionalAPIError

    fake_client = MagicMock()
    fake_client.get = AsyncMock(side_effect=httpx.ReadTimeout("timed out"))
    ctx = _FakeCtx(_FakeAppContext(fake_client))

    with patch("congress_api.core.client_handler.ENABLE_CACHING", False), \
            patch.object(mod.asyncio, "sleep", AsyncMock()):
        with pytest.raises(CongressionalAPIError) as ei:
            await mod.safe_congressional_request("/bill/119", ctx, {},
                                                 endpoint_type="default")

    assert ei.value.error_response.error_code == "API_TIMEOUT"

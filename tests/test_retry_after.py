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
async def test_429_retry_after_is_capped_at_max_retry_delay():
    """A large/malformed Retry-After can't stall a tool call past the
    endpoint's configured cap."""
    from congress_api.core import api_wrapper as mod
    from congress_api.core.exceptions import CongressionalAPIError

    sleep_calls = []

    async def fake_sleep(seconds):
        sleep_calls.append(seconds)

    with patch.object(mod, "make_api_request",
                      AsyncMock(return_value=_rate_limited(retry_after="120"))), \
            patch.object(mod.asyncio, "sleep", fake_sleep):
        with pytest.raises(CongressionalAPIError):
            await mod.safe_congressional_request("/bill/119", FakeContext(), {},
                                                 endpoint_type="default")  # max_retry_delay=5.0

    assert sleep_calls and all(s <= 5.0 for s in sleep_calls)


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

    assert fake_client.get.await_args.kwargs["timeout"] == 8.0


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

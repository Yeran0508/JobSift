from collections.abc import Callable

import httpx
import pytest
from jobsift.acquisition.adapters import (
    HttpSourceAdapter,
    RateLimiter,
    RetryExhaustedError,
)
from jobsift.acquisition.models import AcquisitionMethod, SourceConfig


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def _adapter(
    config: SourceConfig,
    handler: Callable[[httpx.Request], httpx.Response],
    sleeps: list[float],
) -> HttpSourceAdapter:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return HttpSourceAdapter(
        config,
        client=client,
        rate_limiter=RateLimiter(120, sleeper=lambda _seconds: None),
        sleeper=sleeps.append,
    )


def test_rate_limiter_spaces_requests() -> None:
    clock = FakeClock()
    limiter = RateLimiter(2, clock=clock, sleeper=clock.sleep)

    waits = [limiter.acquire(), limiter.acquire(), limiter.acquire()]

    assert clock.sleeps == [30.0, 30.0]
    assert waits == [0.0, 30.0, 30.0]


def test_http_adapter_sends_identified_public_get(greenhouse_config: SourceConfig) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"jobs": []}, headers={"content-type": "application/json"})

    adapter = _adapter(greenhouse_config, handler, [])
    page = adapter.fetch()

    assert len(requests) == 1
    assert requests[0].headers["user-agent"].startswith("JobSift/0.1")
    assert requests[0].headers["accept"] == "application/json"
    assert page.content_type == "application/json"
    assert page.content == b'{"jobs":[]}'
    assert page.fetch_stats.attempts == 1
    assert page.fetch_stats.retries == 0
    assert adapter.last_stats == page.fetch_stats


def test_http_adapter_honors_retry_after_then_succeeds(
    greenhouse_config: SourceConfig,
) -> None:
    responses = iter(
        [
            httpx.Response(429, headers={"retry-after": "2"}),
            httpx.Response(200, json={"jobs": []}),
        ]
    )
    sleeps: list[float] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        return next(responses)

    page = _adapter(greenhouse_config, handler, sleeps).fetch()

    assert sleeps == [2.0]
    assert page.fetch_stats.attempts == 2
    assert page.fetch_stats.retries == 1
    assert page.fetch_stats.backoff_seconds == 2.0


def test_http_adapter_retries_transport_error_with_exponential_backoff(
    greenhouse_config: SourceConfig,
) -> None:
    attempts = 0
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.ConnectError("temporary", request=request)
        return httpx.Response(200, json={"jobs": []})

    _adapter(greenhouse_config, handler, sleeps).fetch()

    assert attempts == 2
    assert sleeps == [1.0]


def test_http_adapter_rejects_non_retryable_status(greenhouse_config: SourceConfig) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    with pytest.raises(httpx.HTTPStatusError):
        _adapter(greenhouse_config, handler, []).fetch()


def test_http_adapter_fails_after_bounded_attempts(greenhouse_config: SourceConfig) -> None:
    sleeps: list[float] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, headers={"retry-after": "invalid"})

    with pytest.raises(RetryExhaustedError, match="failed after 3 attempts"):
        _adapter(greenhouse_config, handler, sleeps).fetch()

    assert sleeps == [1.0, 2.0]


def test_http_adapter_bounds_transport_error_retries(
    greenhouse_config: SourceConfig,
) -> None:
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("still unavailable", request=request)

    with pytest.raises(RetryExhaustedError, match="failed after 3 attempts"):
        _adapter(greenhouse_config, handler, sleeps).fetch()

    assert sleeps == [1.0, 2.0]


def test_http_adapter_rejects_non_http_method(
    greenhouse_config: SourceConfig,
) -> None:
    invalid = greenhouse_config.model_copy(update={"method": AcquisitionMethod.SELENIUM})
    client = httpx.Client(transport=httpx.MockTransport(lambda _request: httpx.Response(200)))

    with pytest.raises(ValueError, match="requires method=api or method=http"):
        HttpSourceAdapter(invalid, client=client, rate_limiter=RateLimiter(1))


def test_http_adapter_requires_endpoint_and_policy(greenhouse_config: SourceConfig) -> None:
    invalid = greenhouse_config.model_copy(update={"endpoint_url": None})
    client = httpx.Client(transport=httpx.MockTransport(lambda _request: httpx.Response(200)))

    with pytest.raises(ValueError, match="requires endpoint_url and http policy"):
        HttpSourceAdapter(invalid, client=client, rate_limiter=RateLimiter(1))

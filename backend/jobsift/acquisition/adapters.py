import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

import httpx
from pydantic import BaseModel, HttpUrl

from jobsift.acquisition.models import AcquisitionMethod, SourceConfig


class FetchedPage(BaseModel):
    source_url: HttpUrl
    content: bytes
    content_type: str
    fetched_at: datetime


class SourceAdapter(Protocol):
    @property
    def config(self) -> SourceConfig: ...

    def fetch(self) -> FetchedPage: ...


class RetryExhaustedError(RuntimeError):
    """Raised when a bounded HTTP retry policy cannot obtain a response."""


class RateLimiter:
    def __init__(
        self,
        requests_per_minute: int,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self._interval_seconds = 60.0 / requests_per_minute
        self._clock = clock
        self._sleeper = sleeper
        self._next_allowed_at = 0.0
        self._lock = threading.Lock()

    def acquire(self) -> None:
        with self._lock:
            now = self._clock()
            wait_seconds = max(0.0, self._next_allowed_at - now)
            if wait_seconds:
                self._sleeper(wait_seconds)
                now = self._clock()
            self._next_allowed_at = max(now, self._next_allowed_at) + self._interval_seconds


class FixtureSourceAdapter:
    def __init__(self, config: SourceConfig, fixture_path: Path) -> None:
        if config.method is not AcquisitionMethod.FIXTURE:
            raise ValueError("FixtureSourceAdapter requires method=fixture")
        self._config = config
        self._fixture_path = fixture_path

    @property
    def config(self) -> SourceConfig:
        return self._config

    def fetch(self) -> FetchedPage:
        return FetchedPage(
            source_url=self._config.base_url,
            content=self._fixture_path.read_bytes(),
            content_type="text/html; charset=utf-8",
            fetched_at=datetime.now(UTC),
        )


class HttpSourceAdapter:
    _retryable_statuses = {408, 429, 500, 502, 503, 504}

    def __init__(
        self,
        config: SourceConfig,
        *,
        client: httpx.Client,
        rate_limiter: RateLimiter,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if config.method not in {AcquisitionMethod.API, AcquisitionMethod.HTTP}:
            raise ValueError("HttpSourceAdapter requires method=api or method=http")
        if config.endpoint_url is None or config.http is None:
            raise ValueError("HttpSourceAdapter requires endpoint_url and http policy")
        self._config = config
        self._client = client
        self._rate_limiter = rate_limiter
        self._sleeper = sleeper

    @property
    def config(self) -> SourceConfig:
        return self._config

    def fetch(self) -> FetchedPage:
        self._config.assert_collection_allowed()
        policy = self._config.http
        endpoint_url = self._config.endpoint_url
        assert policy is not None
        assert endpoint_url is not None
        last_error: Exception | None = None

        for attempt in range(1, policy.max_attempts + 1):
            self._rate_limiter.acquire()
            try:
                response = self._client.get(
                    str(endpoint_url),
                    headers={"User-Agent": policy.user_agent, "Accept": "application/json"},
                    timeout=policy.timeout_seconds,
                )
            except httpx.TransportError as error:
                last_error = error
                if attempt == policy.max_attempts:
                    break
                self._sleeper(self._backoff_seconds(attempt))
                continue

            if response.status_code < 400:
                return FetchedPage(
                    source_url=endpoint_url,
                    content=response.content,
                    content_type=response.headers.get("content-type", "application/octet-stream"),
                    fetched_at=datetime.now(UTC),
                )
            if response.status_code not in self._retryable_statuses:
                response.raise_for_status()
            last_error = httpx.HTTPStatusError(
                f"retryable HTTP status {response.status_code}",
                request=response.request,
                response=response,
            )
            if attempt == policy.max_attempts:
                break
            self._sleeper(self._retry_delay(response, attempt))

        raise RetryExhaustedError(
            f"source {self._config.source_id} failed after {policy.max_attempts} attempts"
        ) from last_error

    def _retry_delay(self, response: httpx.Response, attempt: int) -> float:
        retry_after = response.headers.get("retry-after")
        if retry_after is not None:
            try:
                return min(float(retry_after), self._config.http.max_backoff_seconds)
            except ValueError:
                pass
        return self._backoff_seconds(attempt)

    def _backoff_seconds(self, attempt: int) -> float:
        policy = self._config.http
        assert policy is not None
        exponential = policy.initial_backoff_seconds * (2 ** (attempt - 1))
        return min(exponential, policy.max_backoff_seconds)

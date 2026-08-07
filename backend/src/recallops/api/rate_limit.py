"""Small in-memory limiter for paid AI endpoints."""

from collections.abc import Callable
from dataclasses import dataclass
from threading import Lock
from time import monotonic

from fastapi import HTTPException, Request, status

from recallops.config import get_settings


@dataclass
class _ClientWindow:
    started_at: float
    count: int


class FixedWindowRateLimiter:
    """Process-local fixed-window limiter for demo deployment safety."""

    def __init__(
        self,
        *,
        max_requests: int,
        window_seconds: int,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        if max_requests < 1:
            raise ValueError("max_requests must be at least 1")
        if window_seconds < 1:
            raise ValueError("window_seconds must be at least 1")
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._clock = clock
        self._lock = Lock()
        self._windows: dict[str, _ClientWindow] = {}

    def allow(self, identifier: str) -> bool:
        now = self._clock()
        with self._lock:
            window = self._windows.get(identifier)
            if window is None or now - window.started_at >= self.window_seconds:
                self._windows[identifier] = _ClientWindow(started_at=now, count=1)
                return True

            if window.count >= self.max_requests:
                return False

            window.count += 1
            return True

    def reset(self) -> None:
        with self._lock:
            self._windows = {}


_limiters_by_config: dict[tuple[int, int], FixedWindowRateLimiter] = {}
_limiters_lock = Lock()


def paid_ai_rate_limit(request: Request) -> None:
    """Reject excessive paid provider requests without exposing internals."""

    settings = get_settings()
    if not settings.enable_ai_rate_limit:
        return

    limiter = _limiter_for(
        settings.ai_rate_limit_requests,
        settings.ai_rate_limit_window_seconds,
    )
    if limiter.allow(_client_identifier(request)):
        return

    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="AI request rate limit exceeded. Please try again shortly.",
    )


def reset_ai_rate_limiter_for_tests() -> None:
    with _limiters_lock:
        _limiters_by_config.clear()


def _limiter_for(max_requests: int, window_seconds: int) -> FixedWindowRateLimiter:
    config_key = (max_requests, window_seconds)
    with _limiters_lock:
        limiter = _limiters_by_config.get(config_key)
        if limiter is None:
            limiter = FixedWindowRateLimiter(
                max_requests=max_requests,
                window_seconds=window_seconds,
            )
            _limiters_by_config[config_key] = limiter
        return limiter


def _client_identifier(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for is not None:
        first_hop = forwarded_for.split(",", 1)[0].strip()
        if first_hop:
            return first_hop

    if request.client is not None and request.client.host:
        return request.client.host
    return "unknown-client"

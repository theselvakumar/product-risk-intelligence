"""Sliding window in-memory rate limiter for DRISHTI regulatory APIs."""

import asyncio
import time
from collections import defaultdict
from typing import Callable, Dict, List
from fastapi import HTTPException, Request, status


class SlidingWindowRateLimiter:
    """Thread-safe, in-memory sliding window rate limiter with automated window eviction."""

    def __init__(self):
        self._requests: Dict[str, List[float]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def is_rate_limited(self, key: str, max_requests: int, window_seconds: int = 60) -> tuple[bool, int]:
        """
        Check if an identity key (IP or user ID) has exceeded max_requests in window_seconds.
        Returns: (is_limited, retry_after_seconds)
        """
        now = time.time()
        cutoff = now - window_seconds

        async with self._lock:
            # Evict timestamps older than cutoff
            timestamps = [t for t in self._requests[key] if t > cutoff]
            self._requests[key] = timestamps

            if len(timestamps) >= max_requests:
                oldest_in_window = timestamps[0]
                retry_after = max(1, int(oldest_in_window + window_seconds - now))
                return True, retry_after

            # Record this request
            self._requests[key].append(now)
            return False, 0

    async def reset(self):
        """Clear all rate limit tracking."""
        async with self._lock:
            self._requests.clear()


# Global singleton instance
global_rate_limiter = SlidingWindowRateLimiter()


def rate_limit(max_requests: int = 60, window_seconds: int = 60) -> Callable:
    """
    FastAPI dependency enforcing sliding window rate limiting per client IP.
    Returns HTTP 429 Too Many Requests if rate exceeded.
    """
    async def dependency(request: Request):
        # Resolve client key (prefer X-Forwarded-For or direct client IP)
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()
        elif request.client:
            client_ip = request.client.host
        else:
            client_ip = "127.0.0.1"

        path_key = f"{client_ip}:{request.url.path}"
        is_limited, retry_after = await global_rate_limiter.is_rate_limited(
            key=path_key,
            max_requests=max_requests,
            window_seconds=window_seconds,
        )

        if is_limited:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Maximum {max_requests} requests per {window_seconds} seconds.",
                headers={"Retry-After": str(retry_after)},
            )

    return dependency

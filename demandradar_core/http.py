"""Small HTTP client with bounded retries and rate-limit awareness."""

import json
import time
import urllib.error
import urllib.request
from email.utils import parsedate_to_datetime

from .constants import RETRYABLE_HTTP_STATUS, USER_AGENT


def _retry_after_seconds(headers, now=None):
    """Read Retry-After or GitHub rate-limit reset headers when available."""
    now = time.time() if now is None else now
    if not headers:
        return None

    retry_after = headers.get("Retry-After")
    if retry_after:
        try:
            return max(0.0, float(retry_after))
        except (TypeError, ValueError):
            try:
                when = parsedate_to_datetime(retry_after)
                return max(0.0, when.timestamp() - now)
            except (TypeError, ValueError, OverflowError):
                pass

    if headers.get("X-RateLimit-Remaining") == "0":
        try:
            reset = float(headers.get("X-RateLimit-Reset", 0))
            return max(0.0, reset - now)
        except (TypeError, ValueError):
            pass

    return None


def _is_retryable_http_error(exc):
    headers = exc.headers or {}
    if exc.code in RETRYABLE_HTTP_STATUS:
        return True
    return exc.code == 403 and headers.get("X-RateLimit-Remaining") == "0"


def fetch_json(
    url,
    headers=None,
    timeout=12,
    retries=3,
    backoff=0.75,
    max_delay=30,
    opener=None,
    sleeper=None,
):
    """Fetch and decode JSON with retries for transient network/API failures.

    Retryable cases include timeouts, URL errors, HTTP 408/429/5xx and GitHub-style
    403 rate limits. Delay hints from Retry-After and X-RateLimit-Reset are honored
    but capped by *max_delay* so a collector cannot block forever.
    """
    request_headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    request_headers.update(headers or {})
    opener = opener or urllib.request.urlopen
    sleeper = sleeper or time.sleep
    last_error = None

    for attempt in range(max(0, int(retries)) + 1):
        request = urllib.request.Request(url, headers=request_headers)
        retry_hint = None
        try:
            with opener(request, timeout=timeout) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw)
        except urllib.error.HTTPError as exc:
            last_error = exc
            if not _is_retryable_http_error(exc):
                raise
            retry_hint = _retry_after_seconds(exc.headers or {})
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = exc

        if attempt >= retries:
            raise last_error

        delay = retry_hint if retry_hint is not None else backoff * (2 ** attempt)
        sleeper(min(float(max_delay), max(0.0, float(delay))))

    raise last_error  # pragma: no cover

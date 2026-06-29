import json
import math
import socket
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Callable, Dict, Optional

from common.api_resilience import (
    compact_quota_message,
    is_daily_request_quota_body,
    parse_retry_delay_seconds,
)


class TransportError(Exception):
    pass


class StopRequested(Exception):
    pass


_RATE_LIMIT_LOCK = threading.Lock()
_RATE_LIMIT_UNTIL_BY_SCOPE: Dict[str, float] = {}


def _sleep_with_stop(seconds: float, should_stop: Optional[Callable[[], bool]] = None) -> None:
    remaining = max(0.0, float(seconds))
    while remaining > 0:
        if should_stop and should_stop():
            raise StopRequested("Stopped by user request.")
        chunk = min(0.25, remaining)
        time.sleep(chunk)
        remaining -= chunk

def http_post_json(
    url: str,
    headers: Dict[str, str],
    payload: Dict[str, Any],
    timeout: int = 180,
    retries: int = 2,
    retry_delay: float = 2.0,
    should_stop: Optional[Callable[[], bool]] = None,
    user_agent: Optional[str] = None,
    rate_limit_scope: Optional[str] = None,
) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    effective_headers = dict(headers)
    effective_headers.setdefault("Accept", "application/json")
    effective_headers.setdefault("User-Agent", user_agent or "ClinicalExtractor/1.0 (+desktop)")
    request = urllib.request.Request(url, data=data, headers=effective_headers, method="POST")
    last_error: Optional[Exception] = None
    transient_attempt = 0
    rate_limit_attempt = 0
    max_rate_limit_retries = max(8, retries + 6)
    scope_key = str(rate_limit_scope or "global").strip().lower() or "global"

    while True:
        with _RATE_LIMIT_LOCK:
            now = time.time()
            wait_until = float(_RATE_LIMIT_UNTIL_BY_SCOPE.get(scope_key, 0.0) or 0.0)
            wait_for = max(0.0, wait_until - now)
        if wait_for > 0:
            _sleep_with_stop(wait_for, should_stop)
        if should_stop and should_stop():
            raise StopRequested("Stopped by user request.")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            retry_after = parse_retry_delay_seconds(body)
            if exc.code == 429 and is_daily_request_quota_body(body):
                compact = compact_quota_message(exc.code, body)
                body_preview = body.strip()
                if len(body_preview) > 1200:
                    body_preview = body_preview[:1200] + " ...<truncated>"
                if body_preview:
                    raise TransportError(f"{compact}\nResponse body: {body_preview}") from exc
                raise TransportError(compact) from exc
            if exc.code == 429 and rate_limit_attempt < max_rate_limit_retries:
                rate_limit_attempt += 1
                sleep_seconds = retry_after if retry_after is not None else max(5.0, retry_delay * (rate_limit_attempt + 1))
                sleep_seconds = max(1, min(int(math.ceil(sleep_seconds)), 300))
                with _RATE_LIMIT_LOCK:
                    _RATE_LIMIT_UNTIL_BY_SCOPE[scope_key] = max(
                        float(_RATE_LIMIT_UNTIL_BY_SCOPE.get(scope_key, 0.0) or 0.0),
                        time.time() + sleep_seconds,
                    )
                _sleep_with_stop(sleep_seconds, should_stop)
                last_error = exc
                continue
            if exc.code in (408, 500, 502, 503, 504) and transient_attempt < retries:
                transient_attempt += 1
                sleep_seconds = retry_after if retry_after is not None else retry_delay * transient_attempt
                _sleep_with_stop(max(1, min(int(math.ceil(sleep_seconds)), 120)), should_stop)
                last_error = exc
                continue
            compact = compact_quota_message(exc.code, body)
            body_preview = body.strip()
            if len(body_preview) > 1200:
                body_preview = body_preview[:1200] + " ...<truncated>"
            if body_preview:
                raise TransportError(f"{compact}\nResponse body: {body_preview}") from exc
            raise TransportError(compact) from exc
        except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
            last_error = exc
            if transient_attempt < retries:
                transient_attempt += 1
                _sleep_with_stop(retry_delay * transient_attempt, should_stop)
                continue
            raise TransportError(
                f"Network timeout/error after {retries + 1} attempts. "
                f"Try reducing records per request or increasing timeout. Details: {exc}"
            ) from exc
        except json.JSONDecodeError as exc:
            raise TransportError(f"Failed to decode HTTP response JSON: {exc}") from exc

    raise TransportError(f"Request failed: {last_error}")


def http_get_json(url: str, timeout: int = 60, user_agent: Optional[str] = None) -> Dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": user_agent or "ClinicalExtractor/1.0 (+desktop)",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise TransportError(f"HTTP {exc.code}: {body}") from exc
    except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
        raise TransportError(f"Network error while checking model availability: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise TransportError(f"Invalid JSON while checking model availability: {exc}") from exc

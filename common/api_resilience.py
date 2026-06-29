import json
import math
import re
from typing import Any, Optional


def _error_text(value: Any) -> str:
    return str(value or "").strip()


def parse_retry_delay_seconds(error_body: str) -> Optional[int]:
    def parse_delay(delay_text: str) -> Optional[int]:
        text = delay_text.strip().lower()
        ms_match = re.match(r"^(\d+(?:\.\d+)?)ms$", text)
        if ms_match:
            ms_value = float(ms_match.group(1))
            if ms_value <= 0:
                return 0
            return max(1, math.ceil(ms_value / 1000.0))
        s_match = re.match(r"^(\d+(?:\.\d+)?)s$", text)
        if s_match:
            s_value = float(s_match.group(1))
            if s_value <= 0:
                return 0
            return max(1, math.ceil(s_value))
        return None

    try:
        payload = json.loads(error_body)
    except Exception:
        payload = None

    if isinstance(payload, dict):
        error_obj = payload.get("error")
        if isinstance(error_obj, dict):
            details = error_obj.get("details", [])
            if isinstance(details, dict):
                details = [details]
            if isinstance(details, list):
                for detail in details:
                    if not isinstance(detail, dict):
                        continue
                    retry_delay = detail.get("retryDelay")
                    if isinstance(retry_delay, str):
                        parsed = parse_delay(retry_delay)
                        if parsed is not None:
                            return parsed
        if isinstance(error_obj, str):
            message = error_obj
        elif isinstance(error_obj, dict):
            message = str(error_obj.get("message", ""))
        else:
            message = str(payload.get("message", ""))
        match = re.search(r"(?:retry|try again) in\s+(\d+(?:\.\d+)?)(ms|s)", message, flags=re.I)
        if match:
            parsed = parse_delay(f"{match.group(1)}{match.group(2)}")
            if parsed is not None:
                return parsed

    match = re.search(r"(?:retry|try again) in\s+(\d+(?:\.\d+)?)(ms|s)", error_body, flags=re.I)
    if match:
        parsed = parse_delay(f"{match.group(1)}{match.group(2)}")
        if parsed is not None:
            return parsed
    return None


def parse_retry_wait_seconds_from_error(exc: Any) -> int:
    text = _error_text(exc)
    if not text:
        return 0
    match = re.search(r"(?:retry|try again) in\s+(\d+(?:\.\d+)?)(ms|s)?", text, flags=re.I)
    if not match:
        return 0
    value = float(match.group(1))
    unit = (match.group(2) or "s").lower()
    if unit == "ms":
        return max(1, int(math.ceil(value / 1000.0)))
    return max(1, int(math.ceil(value)))


def is_daily_request_quota_body(body: str) -> bool:
    return "GenerateRequestsPerDayPerProjectPerModel-FreeTier" in body


def compact_quota_message(status: int, body: str) -> str:
    try:
        payload = json.loads(body)
    except Exception:
        return f"HTTP {status}: {body}"
    if not isinstance(payload, dict):
        return f"HTTP {status}: {body}"

    error = payload.get("error", {})
    if isinstance(error, dict):
        message = str(error.get("message", f"HTTP {status}"))
    elif isinstance(error, str):
        message = error
    else:
        message = str(payload.get("message", f"HTTP {status}"))

    limit_match = re.search(r"Limit\s+([0-9]+)", message, flags=re.I)
    requested_match = re.search(r"Requested\s+([0-9]+)", message, flags=re.I)
    if limit_match and requested_match:
        message += f" (limit={limit_match.group(1)}, requested={requested_match.group(1)})"

    retry_seconds = parse_retry_delay_seconds(body)
    if retry_seconds is not None:
        message += f" Suggested wait: {retry_seconds}s."
    if "generate_content_free_tier_input_token_count" in body:
        message += " You hit the free-tier input-token-per-minute limit for this model."
    if "GenerateRequestsPerDayPerProjectPerModel-FreeTier" in body:
        message += " You hit the free-tier daily request quota for this model/project."
    elif "GenerateRequestsPerMinutePerProjectPerModel-FreeTier" in body:
        message += " You hit the free-tier requests-per-minute limit for this model/project."
    elif "generate_content_free_tier_requests" in body:
        message += " You hit a free-tier request quota for this model/project."
    return f"HTTP {status}: {message}"


def is_request_too_large_error(exc: Any) -> bool:
    text = _error_text(exc).lower()
    if not text:
        return False
    return (
        "http 413" in text
        or "request too large" in text
        or ("rate_limit_exceeded" in text and "requested" in text and "limit" in text)
        or ("tokens per minute" in text and "requested" in text and "limit" in text)
        or "context_length_exceeded" in text
    )


def is_retryable_error(exc: Any) -> bool:
    text = _error_text(exc).lower()
    if not text:
        return False
    return (
        "http 429" in text
        or "rate limit" in text
        or "rate_limit_exceeded" in text
        or "too many requests" in text
        or "retry" in text
        or "temporarily unavailable" in text
        or "timeout" in text
        or "timed out" in text
        or "http 408" in text
        or "http 500" in text
        or "http 502" in text
        or "http 503" in text
        or "http 504" in text
        or "network" in text
        or "connection" in text
    )


def is_rate_limit_error(exc: Any) -> bool:
    text = _error_text(exc).lower()
    if not text:
        return False
    return (
        "http 429" in text
        or '"status":429' in text
        or "too many requests" in text
        or "rate_limit_exceeded" in text
        or "tokens per minute" in text
    )


def is_model_output_error(exc: Any) -> bool:
    text = _error_text(exc).lower()
    if not text:
        return False
    return (
        "invalid json" in text
        or "decode" in text
        or "empty response" in text
        or "empty content" in text
        or "returned no choices" in text
        or "returned no candidates" in text
        or "model returned" in text
    )


def should_split_batch(exc: Exception, record_count: int) -> bool:
    if record_count <= 1:
        return False
    if exc.__class__.__name__ == "MalformedModelOutputError":
        return True
    message = _error_text(exc).lower()
    return "timeout" in message or "too large" in message or "invalid json" in message


def is_hard_request_quota_error(exc: Exception) -> bool:
    lowered = _error_text(exc).lower()
    return (
        "generaterequestsperdayperprojectperformodel-freetier".lower() in lowered
        or "daily request quota" in lowered
    )

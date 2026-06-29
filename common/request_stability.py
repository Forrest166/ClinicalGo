import math
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Sequence, TypeVar

from common.api_resilience import (
    is_request_too_large_error,
    parse_retry_wait_seconds_from_error,
)


T = TypeVar("T")


@dataclass(frozen=True)
class RuntimeGuardRule:
    min_timeout_seconds: int = 30
    min_retries: int = 0
    max_concurrency: int = 1


@dataclass(frozen=True)
class RuntimeSettings:
    timeout_seconds: int
    retries: int
    concurrency: int


RUNTIME_GUARD_RULES: Dict[tuple[str, str], RuntimeGuardRule] = {
    ("NVIDIA NIM", "deepseek-ai/deepseek-r1-distill-qwen-32b"): RuntimeGuardRule(
        min_timeout_seconds=300,
        min_retries=4,
        max_concurrency=5,
    ),
}


def apply_runtime_guards(
    *,
    provider: str,
    model: str,
    timeout_seconds: int,
    retries: int,
    concurrency: int,
    progress: Optional[Callable[[str], None]] = None,
    label: Optional[str] = None,
) -> RuntimeSettings:
    guarded_timeout = max(30, int(timeout_seconds))
    guarded_retries = max(0, int(retries))
    guarded_concurrency = max(1, int(concurrency))
    rule = RUNTIME_GUARD_RULES.get((str(provider or "").strip(), str(model or "").strip()))
    if not rule:
        return RuntimeSettings(
            timeout_seconds=guarded_timeout,
            retries=guarded_retries,
            concurrency=guarded_concurrency,
        )

    prefix = label or f"Model-specific guard for {model}"
    if guarded_timeout < int(rule.min_timeout_seconds):
        guarded_timeout = int(rule.min_timeout_seconds)
        if progress:
            progress(f"{prefix}: timeout raised to {guarded_timeout}s.")
    if guarded_retries < int(rule.min_retries):
        guarded_retries = int(rule.min_retries)
        if progress:
            progress(f"{prefix}: retries raised to {guarded_retries}.")
    if guarded_concurrency > int(rule.max_concurrency):
        guarded_concurrency = int(rule.max_concurrency)
        if progress:
            progress(
                f"{prefix}: concurrency capped at {guarded_concurrency} to reduce timeout storms."
            )
    return RuntimeSettings(
        timeout_seconds=guarded_timeout,
        retries=guarded_retries,
        concurrency=guarded_concurrency,
    )


def sleep_with_stop(
    seconds: float,
    should_stop: Optional[Callable[[], bool]] = None,
    cancel_exception_cls: type[Exception] = RuntimeError,
    cancel_message: str = "Stopped by user request.",
) -> None:
    remaining = max(0.0, float(seconds))
    while remaining > 0:
        if should_stop and should_stop():
            raise cancel_exception_cls(cancel_message)
        chunk = min(0.25, remaining)
        time.sleep(chunk)
        remaining -= chunk


class AdaptiveRateLimitController:
    def __init__(
        self,
        *,
        max_workers: int,
        label: str,
        progress: Optional[Callable[[str], None]] = None,
        pause_log_interval_seconds: float = 6.0,
    ) -> None:
        self.max_workers = max(1, int(max_workers))
        self.label = str(label or "LLM")
        self.progress = progress
        self.pause_log_interval_seconds = max(1.0, float(pause_log_interval_seconds))
        self._lock = threading.Lock()
        self._pause_until = 0.0
        self._rate_limit_hits = 0
        self._rate_limit_last_event = 0.0
        self._worker_cap = self.max_workers
        self._last_pause_log_at = 0.0
        self._last_cap_log_at = 0.0
        self._last_retry_log_at = 0.0

    def pause_remaining(self) -> float:
        with self._lock:
            return max(0.0, float(self._pause_until - time.time()))

    def worker_cap(self) -> int:
        with self._lock:
            return max(1, min(self.max_workers, int(self._worker_cap)))

    def wait_if_needed(
        self,
        should_stop: Optional[Callable[[], bool]] = None,
        cancel_exception_cls: type[Exception] = RuntimeError,
        cancel_message: str = "Stopped by user request.",
    ) -> None:
        while True:
            if should_stop and should_stop():
                raise cancel_exception_cls(cancel_message)
            remaining = self.pause_remaining()
            if remaining <= 0:
                return
            now = time.time()
            if self.progress and now - self._last_pause_log_at >= self.pause_log_interval_seconds:
                self.progress(
                    f"{self.label} rate-limit cooldown active; waiting ~{int(math.ceil(remaining))}s "
                    f"(worker-cap={self.worker_cap()}/{self.max_workers})."
                )
                self._last_pause_log_at = now
            sleep_with_stop(
                min(1.0, remaining),
                should_stop=should_stop,
                cancel_exception_cls=cancel_exception_cls,
                cancel_message=cancel_message,
            )

    def on_rate_limit_event(
        self,
        exc: Exception,
        attempt: int,
        max_attempts: int,
    ) -> None:
        suggested_wait = parse_retry_wait_seconds_from_error(exc)
        base_wait = suggested_wait if suggested_wait > 0 else max(4, 2 ** int(attempt))
        reduced_to: Optional[int] = None
        with self._lock:
            self._rate_limit_hits += 1
            self._rate_limit_last_event = time.time()
            pressure_bonus = min(30, self._rate_limit_hits // 2)
            wait_seconds = min(120, max(2, base_wait + pressure_bonus))
            jitter = (self._rate_limit_hits % 5) * 0.4
            target_until = time.time() + wait_seconds + jitter
            if target_until > self._pause_until:
                self._pause_until = target_until
            if self._rate_limit_hits >= 3 and self._worker_cap > 1:
                if self._rate_limit_hits >= 10:
                    new_cap = max(1, self.max_workers // 3)
                else:
                    new_cap = max(1, self.max_workers // 2)
                if new_cap < self._worker_cap:
                    self._worker_cap = new_cap
                    reduced_to = self._worker_cap
            pause_now = max(0, int(math.ceil(self._pause_until - time.time())))
            current_cap = self._worker_cap

        now = time.time()
        if self.progress and reduced_to is not None and now - self._last_cap_log_at >= 1.0:
            self.progress(
                f"{self.label} adaptive throttling: worker-cap reduced to "
                f"{reduced_to}/{self.max_workers} due to repeated 429 responses."
            )
            self._last_cap_log_at = now
        if self.progress and now - self._last_retry_log_at >= 1.0:
            self.progress(
                f"{self.label} transient batch issue; retry {attempt}/{max_attempts} "
                f"after rate-limit cooldown (~{pause_now}s, worker-cap={current_cap}/{self.max_workers}): {exc}"
            )
            self._last_retry_log_at = now

    def maybe_relax(self) -> None:
        grown_to: Optional[int] = None
        with self._lock:
            idle_seconds = time.time() - self._rate_limit_last_event
            if idle_seconds < 20:
                return
            if self._rate_limit_hits > 0:
                self._rate_limit_hits = max(0, self._rate_limit_hits - 1)
            if self._worker_cap < self.max_workers and self._rate_limit_hits <= 1:
                self._worker_cap += 1
                grown_to = self._worker_cap
        now = time.time()
        if self.progress and grown_to is not None and now - self._last_cap_log_at >= 1.0:
            self.progress(
                f"{self.label} adaptive throttling eased: worker-cap restored to "
                f"{grown_to}/{self.max_workers}."
            )
            self._last_cap_log_at = now


def merge_usage_dicts(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, int]:
    return {
        "prompt_tokens": int(left.get("prompt_tokens", 0) or 0) + int(right.get("prompt_tokens", 0) or 0),
        "completion_tokens": int(left.get("completion_tokens", 0) or 0) + int(right.get("completion_tokens", 0) or 0),
        "total_tokens": int(left.get("total_tokens", 0) or 0) + int(right.get("total_tokens", 0) or 0),
    }


def run_with_auto_split(
    items: Sequence[Any],
    run_fn: Callable[[Sequence[Any]], T],
    merge_fn: Callable[[T, T], T],
    *,
    progress: Optional[Callable[[str], None]] = None,
    label: str = "LLM batch",
    depth: int = 0,
    max_depth: int = 8,
    split_predicate: Callable[[Exception], bool] = is_request_too_large_error,
) -> T:
    try:
        return run_fn(items)
    except Exception as exc:
        if len(items) <= 1 or depth >= max_depth or not split_predicate(exc):
            raise
        mid = len(items) // 2
        if mid <= 0 or mid >= len(items):
            raise
        if progress:
            progress(
                f"{label} batch too large; auto-splitting {len(items)} -> {mid}+{len(items) - mid}."
            )
        left = run_with_auto_split(
            items[:mid],
            run_fn,
            merge_fn,
            progress=progress,
            label=label,
            depth=depth + 1,
            max_depth=max_depth,
            split_predicate=split_predicate,
        )
        right = run_with_auto_split(
            items[mid:],
            run_fn,
            merge_fn,
            progress=progress,
            label=label,
            depth=depth + 1,
            max_depth=max_depth,
            split_predicate=split_predicate,
        )
        return merge_fn(left, right)

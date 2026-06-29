from typing import Any, Callable, List, Optional, Sequence, Tuple

from common.api_resilience import (
    is_hard_request_quota_error as shared_is_hard_request_quota_error,
    should_split_batch as shared_should_split_batch,
)


class StopRequested(Exception):
    pass


def should_split_batch(exc: Exception, record_count: int) -> bool:
    return shared_should_split_batch(exc, record_count)


def is_hard_request_quota_error(exc: Exception) -> bool:
    return shared_is_hard_request_quota_error(exc)


def covered_source_ids_from_rows(
    rows: Sequence[Any],
    normalize_source_index_value: Callable[[Any], str],
) -> List[int]:
    covered: List[int] = []
    seen: set[int] = set()
    for row in rows:
        row.source_index = normalize_source_index_value(row.source_index)
        if not row.source_index.isdigit():
            continue
        rid = int(row.source_index)
        if rid not in seen:
            seen.add(rid)
            covered.append(rid)
    return covered


def run_batch_adaptive(
    run_batch_fn: Callable[[Sequence[str], Sequence[int]], Any],
    records: Sequence[str],
    record_ids: Sequence[int],
    progress: Optional[Callable[[str], None]] = None,
    should_stop: Optional[Callable[[], bool]] = None,
    cancel_exception_cls: type[Exception] = StopRequested,
) -> List[Tuple[Any, List[int]]]:
    if should_stop and should_stop():
        raise cancel_exception_cls("Stopped by user request.")
    try:
        return [(run_batch_fn(records, record_ids), list(record_ids))]
    except Exception as exc:
        if should_stop and should_stop():
            raise cancel_exception_cls("Stopped by user request.")
        if not should_split_batch(exc, len(records)):
            raise
        midpoint = max(1, len(records) // 2)
        if progress:
            progress(
                f"Batch with {len(records)} records failed ({exc}). "
                f"Retrying as two smaller batches: {midpoint} + {len(records) - midpoint}."
            )
        left = run_batch_adaptive(
            run_batch_fn,
            records[:midpoint],
            record_ids[:midpoint],
            progress,
            should_stop,
            cancel_exception_cls,
        )
        right = run_batch_adaptive(
            run_batch_fn,
            records[midpoint:],
            record_ids[midpoint:],
            progress,
            should_stop,
            cancel_exception_cls,
        )
        return left + right


def recover_missing_rows(
    run_batch_fn: Callable[[Sequence[str], Sequence[int]], Any],
    records: Sequence[str],
    record_ids: Sequence[int],
    covered_source_ids_fn: Callable[[Sequence[Any]], List[int]],
    progress: Optional[Callable[[str], None]] = None,
    should_stop: Optional[Callable[[], bool]] = None,
    cancel_exception_cls: type[Exception] = StopRequested,
) -> List[Tuple[Any, List[int]]]:
    if not record_ids:
        return []
    if should_stop and should_stop():
        raise cancel_exception_cls("Stopped by user request.")

    try:
        result = run_batch_fn(records, record_ids)
    except Exception as exc:
        if should_stop and should_stop():
            raise cancel_exception_cls("Stopped by user request.")
        if is_hard_request_quota_error(exc):
            if progress:
                progress(
                    f"Recovery skipped for {len(record_ids)} records because the model hit a hard request quota ({exc}). "
                    f"Falling back without further API retries."
                )
            return []
        if len(record_ids) <= 1:
            if progress:
                progress(f"Recovery failed for record {record_ids[0]} ({exc}). Falling back to placeholder row.")
            return []
        midpoint = max(1, len(record_ids) // 2)
        if progress:
            progress(
                f"Recovery retry for {len(record_ids)} missing records failed ({exc}). "
                f"Splitting recovery into {midpoint} + {len(record_ids) - midpoint}."
            )
        left = recover_missing_rows(
            run_batch_fn,
            records[:midpoint],
            record_ids[:midpoint],
            covered_source_ids_fn,
            progress,
            should_stop,
            cancel_exception_cls,
        )
        right = recover_missing_rows(
            run_batch_fn,
            records[midpoint:],
            record_ids[midpoint:],
            covered_source_ids_fn,
            progress,
            should_stop,
            cancel_exception_cls,
        )
        return left + right

    covered_ids = covered_source_ids_fn(result.rows)
    if len(covered_ids) == len(record_ids):
        return [(result, covered_ids)]

    recovered: List[Tuple[Any, List[int]]] = [(result, covered_ids)]
    missing_pairs = [(record, rid) for record, rid in zip(records, record_ids) if rid not in set(covered_ids)]
    if not missing_pairs:
        return recovered
    if len(record_ids) == 1:
        return recovered

    if len(covered_ids) == 0:
        if progress:
            progress(
                f"Recovery batch returned 0/{len(record_ids)} records. "
                f"Stopping recovery for this batch and falling back."
            )
        return recovered

    if progress:
        progress(
            f"Model returned rows for {len(covered_ids)}/{len(record_ids)} records in a recovery batch. "
            f"Retrying {len(missing_pairs)} still-missing records."
        )
    missing_records = [pair[0] for pair in missing_pairs]
    missing_ids = [pair[1] for pair in missing_pairs]
    return recovered + recover_missing_rows(
        run_batch_fn,
        missing_records,
        missing_ids,
        covered_source_ids_fn,
        progress,
        should_stop,
        cancel_exception_cls,
    )

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, List, Optional, Sequence, Tuple


@dataclass
class FailedBatch:
    batch_number: int
    record_ids: List[int]
    batch_records: Sequence[Any]
    error_message: str

    @property
    def record_count(self) -> int:
        return len(self.record_ids)


@dataclass
class PermanentBatchFailure:
    batch_number: int
    record_ids: List[int]
    error_message: str

    @property
    def record_count(self) -> int:
        return len(self.record_ids)

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_number": int(self.batch_number),
            "record_ids": [int(value) for value in self.record_ids],
            "record_count": int(self.record_count),
            "error_message": str(self.error_message or "").strip(),
        }


@dataclass
class BatchRecoverySummary:
    collected_batches: int = 0
    collected_records: int = 0
    recovered_batches: int = 0
    recovered_records: int = 0
    permanent_failures: List[PermanentBatchFailure] = field(default_factory=list)
    manifest_path: str = ""

    @property
    def permanent_batch_count(self) -> int:
        return len(self.permanent_failures)

    @property
    def permanent_record_count(self) -> int:
        return sum(item.record_count for item in self.permanent_failures)


class FailedBatchQueue:
    def __init__(self) -> None:
        self._items: List[FailedBatch] = []

    def add(self, *, batch_number: int, batch_records: Sequence[Any], error: Exception) -> FailedBatch:
        item = FailedBatch(
            batch_number=int(batch_number),
            record_ids=[int(getattr(record, "record_id", 0) or 0) for record in batch_records],
            batch_records=list(batch_records),
            error_message=str(error),
        )
        self._items.append(item)
        return item

    def items(self) -> List[FailedBatch]:
        return list(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __bool__(self) -> bool:
        return bool(self._items)


def failure_manifest_path_for_output(output_path: str) -> str:
    path = Path(str(output_path or "").strip())
    stem = path.stem or "output"
    return str(path.with_name(f"{stem}_failed_batches.json"))


def write_failure_manifest(output_path: str, failures: Sequence[PermanentBatchFailure]) -> str:
    manifest_path = Path(failure_manifest_path_for_output(output_path))
    if not failures:
        if manifest_path.exists():
            manifest_path.unlink()
        return str(manifest_path)
    payload = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "failed_batch_count": len(failures),
        "failed_record_count": sum(item.record_count for item in failures),
        "batches": [item.to_dict() for item in failures],
    }
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(manifest_path)


def replay_failed_batches(
    failures: Sequence[FailedBatch],
    *,
    run_batch_fn: Callable[[Sequence[Any]], List[Tuple[Any, List[int]]]],
    on_success: Callable[[FailedBatch, List[Tuple[Any, List[int]]]], None],
    on_failure: Optional[Callable[[FailedBatch, Exception], None]] = None,
    progress: Optional[Callable[[str], None]] = None,
    should_stop: Optional[Callable[[], bool]] = None,
    cancel_exception_cls: type[Exception] = RuntimeError,
) -> BatchRecoverySummary:
    queue = list(failures)
    summary = BatchRecoverySummary(
        collected_batches=len(queue),
        collected_records=sum(item.record_count for item in queue),
    )
    if not queue:
        return summary
    if progress:
        progress(
            f"Main pass finished with {summary.collected_batches} failed batches "
            f"covering {summary.collected_records} records. Starting replay pass."
        )
    total = len(queue)
    for index, failed_batch in enumerate(queue, start=1):
        if should_stop and should_stop():
            raise cancel_exception_cls("Stopped by user request.")
        if progress:
            progress(
                f"Replay {index}/{total} for batch {failed_batch.batch_number} "
                f"(records={failed_batch.record_count}). Original error: {failed_batch.error_message}"
            )
        try:
            segments = run_batch_fn(failed_batch.batch_records)
        except Exception as exc:
            if on_failure:
                on_failure(failed_batch, exc)
            summary.permanent_failures.append(
                PermanentBatchFailure(
                    batch_number=failed_batch.batch_number,
                    record_ids=list(failed_batch.record_ids),
                    error_message=str(exc),
                )
            )
            if progress:
                progress(
                    f"Replay failed again for batch {failed_batch.batch_number} "
                    f"(records={failed_batch.record_count}): {exc}"
                )
            continue
        on_success(failed_batch, segments)
        summary.recovered_batches += 1
        summary.recovered_records += failed_batch.record_count
        if progress:
            progress(
                f"Replay recovered batch {failed_batch.batch_number} "
                f"(records={failed_batch.record_count})."
            )
    return summary

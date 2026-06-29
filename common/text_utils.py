import math
import re
from typing import Any, Iterator, List, Sequence, TypeVar

T = TypeVar("T")


def clean_text(value: Any, *, normalize_numeric: bool = False, collapse_whitespace: bool = False) -> str:
    if value is None:
        return ""
    if normalize_numeric and isinstance(value, float):
        if math.isnan(value):
            return ""
        if value.is_integer():
            return str(int(value))
    text = str(value).strip()
    if collapse_whitespace:
        text = re.sub(r"\s+", " ", text)
    return text


def normalize_alnum_key(text: str) -> str:
    return "".join(ch for ch in str(text or "").strip().lower() if ch.isalnum())


def normalize_ascii_key(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(text or "").strip().lower())


def estimate_token_count(text: str) -> int:
    return max(1, math.ceil(len(text) / 4))


def iter_batches(items: Sequence[T], batch_size: int) -> Iterator[List[T]]:
    size = max(1, int(batch_size))
    batch: List[T] = []
    for item in items:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch

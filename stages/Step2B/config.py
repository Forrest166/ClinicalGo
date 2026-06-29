import time
from pathlib import Path

from common.paths import data_dir, data_path, interrupt_dir, interrupt_path


APP_TITLE = "Step2B Population Characteristics Refiner"
INPUT_PREFIX = "Step2A"
OUTPUT_PREFIX = "Step2B"
OUTPUT_HEADERS = [
    "Record ID",
    "PMID",
    "Age",
    "Gender",
    "Ethnicity",
    "Occupation",
    "Social Status",
    "Treatment History",
]
DEFAULT_SHEET_NAME = "Results"


def latest_step2a_output() -> str:
    candidates = sorted(data_dir().glob(f"{INPUT_PREFIX}*.xlsx"), key=lambda item: item.stat().st_mtime, reverse=True)
    if candidates:
        return str(candidates[0])
    return str(data_path(f"{INPUT_PREFIX}_clinical_extraction_output.xlsx"))


def default_output_path() -> str:
    return str(data_path(f"{OUTPUT_PREFIX}_population_metrics_output.xlsx"))


def ensure_output_prefix(output_path: str) -> str:
    raw = str(output_path or "").strip()
    if not raw:
        return default_output_path()
    path = Path(raw)
    if path.name.lower().startswith(OUTPUT_PREFIX.lower()):
        return str(path)
    return str(path.with_name(f"{OUTPUT_PREFIX}_{path.name}"))


def checkpoint_path_for_output(output_path: str) -> str:
    path = Path(output_path)
    stem = path.stem or "output"
    pattern = f"{OUTPUT_PREFIX}_{stem}_interrupt_*.checkpoint.jsonl"
    existing = sorted(interrupt_dir().glob(pattern), key=lambda item: item.stat().st_mtime, reverse=True)
    if existing:
        return str(existing[0])
    ts = time.strftime("%Y%m%d_%H%M%S")
    return str(interrupt_path(f"{OUTPUT_PREFIX}_{stem}_interrupt_{ts}.checkpoint.jsonl"))

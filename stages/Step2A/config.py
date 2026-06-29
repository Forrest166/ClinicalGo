import re
import time
from datetime import datetime
from pathlib import Path

from common.paths import interrupt_dir, interrupt_path


APP_TITLE = "Step2A Initial Extractor"
OUTPUT_PREFIX = "Step2A"
PIPELINE_OUTPUT_DIR_NAME = "pipeline_output"
DEFAULT_STEP1_RUN_DIR_NAME = "step1_run_1966-2005"
OUTPUT_HEADERS = [
    "Record ID",
    "Record Index",
    "PMID",
    "NCT ID",
    "Journal",
    "Year",
    "Indication",
    "Population Raw",
    "Severity",
    "Treatment History",
    "Population Status",
    "Target",
    "Intervention",
    "Intervention Type",
    "Comparator",
    "Outcome Direction",
    "Phase",
    "Sample Size",
    "Follow-up Time",
    "Evidence Snippet",
]
RESULT_SHEET_NAME = "Results"


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PIPELINE_OUTPUT_DIR = PROJECT_ROOT / PIPELINE_OUTPUT_DIR_NAME
STEP2A_OUTPUT_DIR = PIPELINE_OUTPUT_DIR / OUTPUT_PREFIX
STEP1_SOURCE_DIR = PIPELINE_OUTPUT_DIR / "Step1" / DEFAULT_STEP1_RUN_DIR_NAME


def _ensure_step2a_output_dir() -> Path:
    STEP2A_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return STEP2A_OUTPUT_DIR


def _normalize_source_stem(source_path: str) -> str:
    stem = Path(source_path).stem or "output"
    cleaned = re.sub(r"^Step1_", "", stem)
    cleaned = re.sub(r"_(cleaned_abstracts|extraction_results|quality_metrics)$", "", cleaned)
    cleaned = re.sub(r"^(?P<base>.+?)_\d{6,}$", r"\g<base>", cleaned)
    cleaned = cleaned.strip("_ ").strip()
    return cleaned or "output"


def default_source_path() -> str:
    if not STEP1_SOURCE_DIR.is_dir():
        return str(STEP1_SOURCE_DIR)
    candidates = sorted(STEP1_SOURCE_DIR.glob("*.txt"), key=lambda item: item.stat().st_mtime, reverse=True)
    if not candidates:
        return str(STEP1_SOURCE_DIR)
    preferred_patterns = ("cleaned_abstracts", "extraction_results", "quality_metrics")
    for pattern in preferred_patterns:
        for candidate in candidates:
            if pattern in candidate.stem:
                return str(candidate)
    if candidates:
        return str(candidates[0])
    return str(STEP1_SOURCE_DIR)


def default_output_path(source_path: str = "") -> str:
    output_dir = _ensure_step2a_output_dir()
    source_stem = _normalize_source_stem(source_path or "output")
    ts = datetime.now().strftime("%y%m%d%H")
    return str(output_dir / f"{OUTPUT_PREFIX}_{source_stem}_{ts}.xlsx")


def ensure_output_prefix(source_path: str, _output_hint: str = "") -> str:
    return default_output_path(source_path or _output_hint)


def checkpoint_path_for_output(output_path: str) -> str:
    path = Path(output_path)
    stem = path.stem or "output"
    pattern = f"{OUTPUT_PREFIX}_{stem}_interrupt_*.checkpoint.jsonl"
    existing = sorted(interrupt_dir().glob(pattern), key=lambda item: item.stat().st_mtime, reverse=True)
    if existing:
        return str(existing[0])
    ts = time.strftime("%Y%m%d_%H%M%S")
    return str(interrupt_path(f"{OUTPUT_PREFIX}_{stem}_interrupt_{ts}.checkpoint.jsonl"))

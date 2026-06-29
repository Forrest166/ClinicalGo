from __future__ import annotations

from pathlib import Path

from common.paths import data_dir, data_path, project_root


APP_TITLE = "Step2C Population Standardizer"
STEP2A_OUTPUT_NAME = "Step2A_clinical_extraction_output.xlsx"
STEP2B_OUTPUT_NAME = "Step2B_population_metrics_output.xlsx"
STEP2C_RAW_OUTPUT_NAME = "Step2C_population_raw_merged.xlsx"
STEP2C_NORMALIZED_OUTPUT_NAME = "Step2C_population_standardized_output.xlsx"
STEP2C_SUMMARY_OUTPUT_NAME = "Step2C_population_standardization_summary.json"
RESULT_SHEET_NAME = "Results"
RULES_DIR = project_root() / "rules"


def latest_matching_workbook(prefixes: list[str], fallback_name: str) -> str:
    candidates = []
    for prefix in prefixes:
        candidates.extend(data_dir().glob(f"{prefix}*.xlsx"))
    candidates = sorted(candidates, key=lambda item: item.stat().st_mtime, reverse=True)
    if candidates:
        return str(candidates[0])
    return str(data_path(fallback_name))


def default_step2a_input() -> str:
    return latest_matching_workbook(["Step2A"], STEP2A_OUTPUT_NAME)


def default_step2b_input() -> str:
    return latest_matching_workbook(["Step2B"], STEP2B_OUTPUT_NAME)


def default_step2a_output() -> str:
    return str(data_path(STEP2A_OUTPUT_NAME))


def default_step2b_output() -> str:
    return str(data_path(STEP2B_OUTPUT_NAME))


def default_raw_output() -> str:
    return str(data_path(STEP2C_RAW_OUTPUT_NAME))


def default_normalized_output() -> str:
    return str(data_path(STEP2C_NORMALIZED_OUTPUT_NAME))


def default_summary_output() -> str:
    return str(data_path(STEP2C_SUMMARY_OUTPUT_NAME))


def ensure_rules_dir() -> Path:
    RULES_DIR.mkdir(parents=True, exist_ok=True)
    return RULES_DIR

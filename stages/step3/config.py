from __future__ import annotations

from datetime import datetime

from common.paths import data_path


APP_TITLE = "Step3 Analysis"
DEFAULT_INPUT_NAME = "Step2C_population_standardized_output.xlsx"


def default_input_path() -> str:
    return str(data_path(DEFAULT_INPUT_NAME))


def default_output_dir() -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return str(data_path(f"Step3_analysis_report_{stamp}"))

from pathlib import Path
from typing import Tuple

SYSTEM_INTERRUPT_DIR_NAME = "system_interrupt_files"
DATA_DIR_NAME = "data_files"


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def data_dir() -> Path:
    path = project_root() / DATA_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def interrupt_dir() -> Path:
    path = project_root() / SYSTEM_INTERRUPT_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def ensure_standard_dirs() -> Tuple[Path, Path]:
    return interrupt_dir(), data_dir()


def data_path(filename: str) -> Path:
    return data_dir() / filename


def interrupt_path(filename: str) -> Path:
    return interrupt_dir() / filename

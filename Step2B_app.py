import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
STAGE_DIR = PROJECT_ROOT / "stages" / "Step2B"
for path in (PROJECT_ROOT, STAGE_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from app import main


if __name__ == "__main__":
    main()

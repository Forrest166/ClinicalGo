from __future__ import annotations

import argparse
import json
import sys

from .config import (
    APP_TITLE,
    default_normalized_output,
    default_raw_output,
    default_step2a_input,
    default_step2a_output,
    default_step2b_input,
    default_step2b_output,
    default_summary_output,
    ensure_rules_dir,
)
from .pipeline import run_step2c


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=APP_TITLE)
    parser.add_argument("--step2a-input", default=default_step2a_input())
    parser.add_argument("--step2b-input", default=default_step2b_input())
    parser.add_argument("--step2a-output", default=default_step2a_output())
    parser.add_argument("--step2b-output", default=default_step2b_output())
    parser.add_argument("--raw-output", default=default_raw_output())
    parser.add_argument("--normalized-output", default=default_normalized_output())
    parser.add_argument("--summary-output", default=default_summary_output())
    return parser


def run_cli(argv: list[str] | None = None) -> int:
    ensure_rules_dir()
    args = build_arg_parser().parse_args(argv)
    summary = run_step2c(
        step2a_input=args.step2a_input,
        step2b_input=args.step2b_input,
        step2a_output=args.step2a_output,
        step2b_output=args.step2b_output,
        raw_output=args.raw_output,
        normalized_output=args.normalized_output,
        summary_output=args.summary_output,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    actual_argv = list(sys.argv[1:] if argv is None else argv)
    if actual_argv:
        return run_cli(actual_argv)
    from .gui import main as gui_main

    gui_main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

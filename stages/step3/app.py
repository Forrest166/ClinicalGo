from __future__ import annotations

import argparse
import json
import sys

from .config import APP_TITLE, default_input_path, default_output_dir
from .pipeline import run_step3_analysis


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=APP_TITLE)
    parser.add_argument("inputs", nargs="*", default=[default_input_path()])
    parser.add_argument("--output-dir", default=default_output_dir())
    parser.add_argument("--cluster-count", type=int, default=8)
    parser.add_argument("--network-min-edge", type=int, default=10)
    return parser


def run_cli(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    summary = run_step3_analysis(
        input_paths=args.inputs,
        output_dir=args.output_dir,
        cluster_count=args.cluster_count,
        network_min_edge=args.network_min_edge,
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

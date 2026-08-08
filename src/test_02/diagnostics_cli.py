"""Command-line entry point for offline client environment diagnostics."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

from .diagnostics import DEFAULT_BASE_URL, DEFAULT_TIMEOUT, environment_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect the test-02 client environment without making a network request"
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Base URL to validate")
    parser.add_argument("--timeout", default=str(DEFAULT_TIMEOUT), help="Request timeout to validate")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = environment_report(args.base_url, args.timeout)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

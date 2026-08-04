import argparse
import json
import sys
from collections.abc import Sequence

from .client import ApiClient, ApiError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read data from test-01")
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:3000",
        help="Base URL of the test-01 API",
    )
    parser.add_argument("command", choices=("health", "items"))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    client = ApiClient(args.base_url)

    try:
        payload = client.health() if args.command == "health" else {"data": client.list_items()}
    except ApiError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

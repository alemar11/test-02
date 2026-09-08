import argparse
import csv
import json
import sys
from collections.abc import Sequence

from .client import MAX_PAGE, ApiClient, ApiError


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("expected a positive integer") from error
    if parsed < 1:
        raise argparse.ArgumentTypeError("expected a positive integer")
    return parsed


def _limit(value: str) -> int:
    parsed = _positive_int(value)
    if parsed > 100:
        raise argparse.ArgumentTypeError("expected an integer from 1 to 100")
    return parsed


def _page(value: str) -> int:
    parsed = _positive_int(value)
    if parsed > MAX_PAGE:
        raise argparse.ArgumentTypeError(f"expected an integer from 1 to {MAX_PAGE}")
    return parsed


def _page_size(value: str) -> int:
    parsed = _positive_int(value)
    if parsed > 100:
        raise argparse.ArgumentTypeError("expected an integer from 1 to 100")
    return parsed


def _csv_rows(
    items: list[dict[str, object]],
) -> list[tuple[str, str, str, str, str]]:
    rows: list[tuple[str, str, str, str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            raise ApiError("export item must be an object")
        scalar_values: list[str] = []
        for field in ("id", "name", "status", "category"):
            value = item.get(field)
            if type(value) is not str:
                raise ApiError(
                    f"export item field '{field}' must be a string"
                )
            scalar_values.append(value)

        labels = item.get("labels")
        if not isinstance(labels, list) or not all(
            type(label) is str for label in labels
        ):
            raise ApiError("export item field 'labels' must be a list of strings")

        rows.append(
            (
                scalar_values[0],
                scalar_values[1],
                scalar_values[2],
                scalar_values[3],
                json.dumps(labels, separators=(",", ":")),
            )
        )
    return rows


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read data from test-01")
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:3000",
        help="Base URL of the test-01 API",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("health", help="Read API health")
    commands.add_parser(
        "capabilities",
        help="Discover compatible provider capabilities",
    )
    item = commands.add_parser("item", help="Read one item by exact ID")
    item.add_argument("item_id", help="Exact item ID")
    items = commands.add_parser("items", help="Discover items")
    items.add_argument("--status", help="Exact status filter")
    items.add_argument("--category", help="Exact category filter")
    items.add_argument("--label", help="Exact label membership filter")
    items.add_argument("--q", help="Case-insensitive item name search")
    items.add_argument("--sort", choices=("id", "name", "status"))
    items.add_argument("--order", choices=("asc", "desc"))
    items.add_argument("--page", type=_page, default=1)
    items.add_argument("--limit", type=_limit, default=20)
    batch = commands.add_parser("batch", help="Read a bounded batch of items")
    batch.add_argument("ids", nargs="+", metavar="ID", help="Item IDs to read")
    facets = commands.add_parser("facets", help="Read item label facets")
    facets.add_argument("--status", help="Exact status filter")
    facets.add_argument("--category", help="Exact category filter")
    facets.add_argument("--label", help="Exact label membership filter")
    facets.add_argument("--q", help="Case-insensitive item name search")
    summary = commands.add_parser("summary", help="Read the item summary")
    summary.add_argument("--status", help="Exact status filter")
    summary.add_argument("--category", help="Exact category filter")
    summary.add_argument("--label", help="Exact label membership filter")
    summary.add_argument("--q", help="Case-insensitive item name search")
    export = commands.add_parser("export", help="Export matching items as CSV")
    export.add_argument("--status", help="Exact status filter")
    export.add_argument("--category", help="Exact category filter")
    export.add_argument("--label", help="Exact label membership filter")
    export.add_argument("--q", help="Case-insensitive item name search")
    export.add_argument("--sort", choices=("id", "name", "status"))
    export.add_argument("--order", choices=("asc", "desc"))
    export.add_argument("--page-size", type=_page_size, default=100)
    export.add_argument("--max-pages", type=_positive_int, default=1000)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if (
        args.command in {"items", "export"}
        and args.order is not None
        and args.sort is None
    ):
        parser.error("--order requires --sort")

    client = ApiClient(args.base_url)

    try:
        if args.command == "health":
            payload = client.health()
        elif args.command == "capabilities":
            payload = client.capabilities()
        elif args.command == "items":
            payload = client.discover_items(
                status=args.status,
                category=args.category,
                label=args.label,
                q=args.q,
                sort=args.sort,
                order=args.order,
                page=args.page,
                limit=args.limit,
            )
        elif args.command == "item":
            payload = client.get_item(args.item_id)
        elif args.command == "batch":
            payload = client.get_items(args.ids)
        elif args.command == "facets":
            payload = client.item_facets(
                status=args.status,
                category=args.category,
                label=args.label,
                q=args.q,
            )
        elif args.command == "export":
            items = list(
                client.iter_items(
                    status=args.status,
                    category=args.category,
                    label=args.label,
                    q=args.q,
                    sort=args.sort,
                    order=args.order,
                    page_size=args.page_size,
                    max_pages=args.max_pages,
                )
            )
            rows = _csv_rows(items)
            writer = csv.writer(sys.stdout, lineterminator="\n")
            writer.writerow(("id", "name", "status", "category", "labels"))
            writer.writerows(rows)
            return 0
        else:
            payload = client.item_summary(
                status=args.status,
                category=args.category,
                label=args.label,
                q=args.q,
            )
    except ApiError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

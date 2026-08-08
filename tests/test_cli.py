import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

from test_02.cli import main
from test_02.client import ApiError


class CliTests(unittest.TestCase):
    @patch("test_02.cli.ApiClient")
    def test_items_prints_the_deterministic_discovery_envelope(self, client_class) -> None:
        envelope = {
            "data": [{"labels": ["featured"], "id": "item-1"}],
            "pagination": {"totalPages": 1, "total": 1, "page": 1, "limit": 5},
            "query": {
                "status": "active",
                "category": "core-service",
                "label": "featured",
                "q": "first",
                "sort": "name",
                "order": "desc",
                "page": 1,
                "limit": 5,
            },
        }
        client_class.return_value.discover_items.return_value = envelope
        output = io.StringIO()

        with redirect_stdout(output):
            result = main(
                [
                    "--base-url",
                    "http://api.example.test",
                    "items",
                    "--status",
                    "active",
                    "--category",
                    "core-service",
                    "--label",
                    "featured",
                    "--q",
                    "first",
                    "--sort",
                    "name",
                    "--order",
                    "desc",
                    "--limit",
                    "5",
                ]
            )

        self.assertEqual(result, 0)
        client_class.assert_called_once_with("http://api.example.test")
        client_class.return_value.discover_items.assert_called_once_with(
            status="active",
            category="core-service",
            label="featured",
            q="first",
            sort="name",
            order="desc",
            page=1,
            limit=5,
        )
        self.assertEqual(output.getvalue(), json.dumps(envelope, indent=2, sort_keys=True) + "\n")

    @patch("test_02.cli.ApiClient")
    def test_health_keeps_the_existing_command_behavior(self, client_class) -> None:
        client_class.return_value.health.return_value = {"status": "ok"}
        output = io.StringIO()

        with redirect_stdout(output):
            result = main(["health"])

        self.assertEqual(result, 0)
        self.assertEqual(output.getvalue(), '{\n  "status": "ok"\n}\n')

    @patch("test_02.cli.ApiClient")
    def test_order_without_sort_is_rejected_before_client_creation(self, client_class) -> None:
        errors = io.StringIO()

        with redirect_stderr(errors), self.assertRaises(SystemExit) as raised:
            main(["items", "--order", "asc"])

        self.assertEqual(raised.exception.code, 2)
        self.assertIn("--order requires --sort", errors.getvalue())
        client_class.assert_not_called()

    @patch("test_02.cli.ApiClient")
    def test_invalid_pagination_is_rejected_before_client_creation(self, client_class) -> None:
        errors = io.StringIO()

        with redirect_stderr(errors), self.assertRaises(SystemExit) as raised:
            main(["items", "--limit", "101"])

        self.assertEqual(raised.exception.code, 2)
        self.assertIn("expected an integer from 1 to 100", errors.getvalue())
        client_class.assert_not_called()

    @patch("test_02.cli.ApiClient")
    def test_api_errors_are_reported_without_json_output(self, client_class) -> None:
        client_class.return_value.discover_items.side_effect = ApiError("transport failed")
        output = io.StringIO()
        errors = io.StringIO()

        with redirect_stdout(output), redirect_stderr(errors):
            result = main(["items", "--label", "featured"])

        self.assertEqual(result, 1)
        self.assertEqual(output.getvalue(), "")
        self.assertEqual(errors.getvalue(), "error: transport failed\n")


if __name__ == "__main__":
    unittest.main()

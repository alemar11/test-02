import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

from test_02.cli import main
from test_02.client import ApiError


class CliTests(unittest.TestCase):
    @patch("test_02.cli.ApiClient")
    def test_capabilities_prints_deterministic_sorted_key_json(self, client_class) -> None:
        manifest = {
            "schemaVersion": 1,
            "capabilities": [
                {"path": "/health", "method": "GET", "id": "health"},
            ],
        }
        client_class.return_value.capabilities.return_value = manifest
        output = io.StringIO()

        with redirect_stdout(output):
            result = main(
                [
                    "--base-url",
                    "http://api.example.test",
                    "capabilities",
                ]
            )

        self.assertEqual(result, 0)
        client_class.assert_called_once_with("http://api.example.test", timeout=5.0)
        client_class.return_value.capabilities.assert_called_once_with()
        self.assertEqual(
            output.getvalue(),
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        )

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
        client_class.assert_called_once_with("http://api.example.test", timeout=5.0)
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
    def test_facets_prints_deterministic_filtered_label_counts(self, client_class) -> None:
        envelope = {
            "data": {
                "total": 2,
                "byLabel": {"support": 1, "read-only": 2, "featured": 1},
            },
            "filters": {
                "status": "active",
                "category": "core-service",
                "label": "featured",
                "q": "item",
            },
        }
        client_class.return_value.item_facets.return_value = envelope
        output = io.StringIO()

        with redirect_stdout(output):
            result = main(
                [
                    "--base-url",
                    "http://api.example.test",
                    "facets",
                    "--status",
                    "active",
                    "--category",
                    "core-service",
                    "--label",
                    "featured",
                    "--q",
                    "ITEM",
                ]
            )

        self.assertEqual(result, 0)
        client_class.assert_called_once_with("http://api.example.test", timeout=5.0)
        client_class.return_value.item_facets.assert_called_once_with(
            status="active",
            category="core-service",
            label="featured",
            q="ITEM",
        )
        self.assertEqual(
            output.getvalue(),
            json.dumps(envelope, indent=2, sort_keys=True) + "\n",
        )

    @patch("test_02.cli.ApiClient")
    def test_summary_prints_deterministic_unfiltered_json(self, client_class) -> None:
        envelope = {
            "insights": {
                "total": 2,
                "matching": 2,
                "filters": {
                    "status": None,
                    "category": None,
                    "label": None,
                    "q": None,
                },
                "byStatus": {"inactive": 1, "active": 1},
            },
            "data": {
                "total": 2,
                "byStatus": {"inactive": 1, "active": 1},
                "byCategory": {"support-service": 1, "core-service": 1},
            },
        }
        client_class.return_value.item_summary.return_value = envelope
        output = io.StringIO()

        with redirect_stdout(output):
            result = main(["summary"])

        self.assertEqual(result, 0)
        client_class.return_value.item_summary.assert_called_once_with(
            status=None,
            category=None,
            label=None,
            q=None,
        )
        self.assertEqual(
            output.getvalue(),
            json.dumps(envelope, indent=2, sort_keys=True) + "\n",
        )

    @patch("test_02.cli.ApiClient")
    def test_summary_delegates_filtered_options_without_recounting(
        self,
        client_class,
    ) -> None:
        envelope = {
            "data": {
                "total": 1,
                "byStatus": {"active": 1},
                "byCategory": {"support-service": 1},
            },
            "insights": {
                "total": 2,
                "matching": 1,
                "byStatus": {"active": 1},
                "filters": {
                    "status": "active",
                    "category": "support-service",
                    "label": "support",
                    "q": "second",
                },
            },
        }
        client_class.return_value.item_summary.return_value = envelope
        output = io.StringIO()

        with redirect_stdout(output):
            result = main(
                [
                    "--base-url",
                    "http://api.example.test",
                    "summary",
                    "--status",
                    "active",
                    "--category",
                    "support-service",
                    "--label",
                    "support",
                    "--q",
                    " SECOND ",
                ]
            )

        self.assertEqual(result, 0)
        client_class.assert_called_once_with("http://api.example.test", timeout=5.0)
        client_class.return_value.item_summary.assert_called_once_with(
            status="active",
            category="support-service",
            label="support",
            q=" SECOND ",
        )
        self.assertEqual(
            output.getvalue(),
            json.dumps(envelope, indent=2, sort_keys=True) + "\n",
        )

    @patch("test_02.cli.ApiClient")
    def test_health_keeps_the_existing_command_behavior(self, client_class) -> None:
        client_class.return_value.health.return_value = {"status": "ok"}
        output = io.StringIO()

        with redirect_stdout(output):
            result = main(["health"])

        self.assertEqual(result, 0)
        client_class.assert_called_once_with(
            "http://127.0.0.1:3000",
            timeout=5.0,
        )
        self.assertEqual(output.getvalue(), '{\n  "status": "ok"\n}\n')

    @patch("test_02.cli.ApiClient")
    def test_global_timeout_is_passed_to_every_command(self, client_class) -> None:
        for command, method_name in (
            ("health", "health"),
            ("capabilities", "capabilities"),
            ("items", "discover_items"),
            ("facets", "item_facets"),
            ("summary", "item_summary"),
        ):
            with self.subTest(command=command):
                client_class.reset_mock()
                getattr(client_class.return_value, method_name).return_value = {}
                output = io.StringIO()

                with redirect_stdout(output):
                    result = main(
                        [
                            "--base-url",
                            "http://api.example.test",
                            "--timeout",
                            "1.25",
                            command,
                        ]
                    )

                self.assertEqual(result, 0)
                client_class.assert_called_once_with(
                    "http://api.example.test",
                    timeout=1.25,
                )

    @patch("test_02.cli.ApiClient")
    def test_invalid_timeout_is_rejected_before_client_creation(self, client_class) -> None:
        for timeout in ("not-a-number", "0", "-1", "nan", "inf", "-inf", "1e309"):
            with self.subTest(timeout=timeout):
                errors = io.StringIO()

                with redirect_stderr(errors), self.assertRaises(SystemExit) as raised:
                    main([f"--timeout={timeout}", "health"])

                self.assertEqual(raised.exception.code, 2)
                self.assertIn("expected a finite positive number", errors.getvalue())
                client_class.assert_not_called()
                client_class.reset_mock()

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
    def test_unsafe_page_is_rejected_before_client_creation(self, client_class) -> None:
        errors = io.StringIO()

        with redirect_stderr(errors), self.assertRaises(SystemExit) as raised:
            main(["items", "--page", "9007199254740992"])

        self.assertEqual(raised.exception.code, 2)
        self.assertIn("expected an integer from 1 to 9007199254740991", errors.getvalue())
        client_class.assert_not_called()

    @patch("test_02.cli.ApiClient")
    def test_facets_rejects_unsupported_controls_before_client_creation(
        self,
        client_class,
    ) -> None:
        for option in (("--sort", "name"), ("--page", "1"), ("--limit", "20")):
            with self.subTest(option=option):
                errors = io.StringIO()

                with redirect_stderr(errors), self.assertRaises(SystemExit) as raised:
                    main(["facets", *option])

                self.assertEqual(raised.exception.code, 2)
                self.assertIn("unrecognized arguments", errors.getvalue())

        client_class.assert_not_called()

    @patch("test_02.cli.ApiClient")
    def test_summary_rejects_unsupported_controls_before_client_creation(
        self,
        client_class,
    ) -> None:
        for option in (
            ("--sort", "name"),
            ("--order", "asc"),
            ("--page", "1"),
            ("--limit", "20"),
        ):
            with self.subTest(option=option):
                output = io.StringIO()
                errors = io.StringIO()

                with (
                    redirect_stdout(output),
                    redirect_stderr(errors),
                    self.assertRaises(SystemExit) as raised,
                ):
                    main(["summary", *option])

                self.assertEqual(raised.exception.code, 2)
                self.assertEqual(output.getvalue(), "")
                self.assertIn("unrecognized arguments", errors.getvalue())

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

    @patch("test_02.cli.ApiClient")
    def test_capability_errors_use_the_existing_cli_error_contract(
        self,
        client_class,
    ) -> None:
        client_class.return_value.capabilities.side_effect = ApiError(
            "GET /api/capabilities returned unsupported schema version 2; expected 1"
        )
        output = io.StringIO()
        errors = io.StringIO()

        with redirect_stdout(output), redirect_stderr(errors):
            result = main(["capabilities"])

        self.assertEqual(result, 1)
        self.assertEqual(output.getvalue(), "")
        self.assertEqual(
            errors.getvalue(),
            "error: GET /api/capabilities returned unsupported schema version 2; "
            "expected 1\n",
        )

    @patch("test_02.cli.ApiClient")
    def test_facet_errors_use_the_existing_cli_error_contract(self, client_class) -> None:
        client_class.return_value.item_facets.side_effect = ApiError(
            "GET /api/items/facets returned invalid facet data"
        )
        output = io.StringIO()
        errors = io.StringIO()

        with redirect_stdout(output), redirect_stderr(errors):
            result = main(["facets", "--label", "featured"])

        self.assertEqual(result, 1)
        self.assertEqual(output.getvalue(), "")
        self.assertEqual(
            errors.getvalue(),
            "error: GET /api/items/facets returned invalid facet data\n",
        )

    @patch("test_02.cli.ApiClient")
    def test_summary_errors_use_the_existing_cli_error_contract(self, client_class) -> None:
        client_class.return_value.item_summary.side_effect = ApiError(
            "GET /api/items/summary returned invalid summary data"
        )
        output = io.StringIO()
        errors = io.StringIO()

        with redirect_stdout(output), redirect_stderr(errors):
            result = main(["summary", "--label", "support"])

        self.assertEqual(result, 1)
        self.assertEqual(output.getvalue(), "")
        self.assertEqual(
            errors.getvalue(),
            "error: GET /api/items/summary returned invalid summary data\n",
        )


if __name__ == "__main__":
    unittest.main()

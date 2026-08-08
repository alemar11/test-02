import contextlib
import io
import json
import os
import socket
import unittest
from importlib import metadata
from unittest import mock

from test_02 import environment_report
from test_02.diagnostics_cli import main


class EnvironmentReportTests(unittest.TestCase):
    def test_valid_environment_has_normalized_structured_output(self) -> None:
        report = environment_report(
            "HTTPS://API.Example.Test/service///",
            "2.5",
            python_version=(3, 13, 2),
            package_version="0.1.0",
        )

        self.assertEqual(
            report,
            {
                "schema_version": 1,
                "ok": True,
                "diagnostics": {
                    "base_url": {"status": "pass", "value": "https://api.example.test/service"},
                    "timeout": {"status": "pass", "value": 2.5},
                    "python": {"status": "pass", "value": "3.13.2", "required": ">=3.13"},
                    "package": {"status": "pass", "name": "test-02", "version": "0.1.0"},
                },
                "network_calls": 0,
            },
        )

    def test_failures_are_explicit_and_complete(self) -> None:
        for timeout in ("not-a-number", "nan", "inf", "0", "-1"):
            with self.subTest(timeout=timeout):
                report = environment_report(
                    "not a URL",
                    timeout,
                    python_version=(3, 12, 9),
                    package_version="0.1.0",
                )
                self.assertFalse(report["ok"])
                self.assertEqual(report["diagnostics"]["base_url"]["code"], "invalid_base_url")
                self.assertEqual(report["diagnostics"]["timeout"]["code"], "invalid_timeout")
                self.assertEqual(report["diagnostics"]["python"]["code"], "unsupported_python")

    def test_malformed_authorities_are_rejected(self) -> None:
        for base_url in (
            "http://%zz",
            "http://.",
            "http://example.com:",
            "http://example.com\\evil",
            "http://127.0.0.1:0",
            "http://[v1.foo]",
            "http://☃.com",
            "http://example.test/%zz",
            "http://example.test/\x00",
            "http://a..b",
            "http://-example.test",
            "http://example-.test",
            "http://example_test",
        ):
            with self.subTest(base_url=base_url):
                report = environment_report(
                    base_url,
                    5,
                    python_version=(3, 13, 0),
                    package_version="0.1.0",
                )

                self.assertFalse(report["ok"])
                self.assertEqual(report["diagnostics"]["base_url"]["code"], "invalid_base_url")

    def test_non_ascii_hostname_uses_the_client_idna_normalization(self) -> None:
        report = environment_report(
            "http://faß.de/",
            5,
            python_version=(3, 13, 0),
            package_version="0.1.0",
        )

        self.assertTrue(report["ok"])
        self.assertEqual(report["diagnostics"]["base_url"]["value"], "http://xn--fa-hia.de")

    def test_report_is_repeatable_offline_and_does_not_mutate_process_state(self) -> None:
        environment_before = os.environ.copy()
        path_before = list(os.sys.path)
        arguments = ("http://localhost:3000/", "5")

        with (
            mock.patch.object(socket, "create_connection", side_effect=AssertionError("network call")),
            mock.patch("requests.Session", side_effect=AssertionError("HTTP session created")),
        ):
            first = environment_report(*arguments, python_version=(3, 14, 0), package_version="0.1.0")
            second = environment_report(*arguments, python_version=(3, 14, 0), package_version="0.1.0")

        self.assertEqual(first, second)
        self.assertEqual(arguments, ("http://localhost:3000/", "5"))
        self.assertEqual(os.environ, environment_before)
        self.assertEqual(os.sys.path, path_before)


class DiagnosticsCliTests(unittest.TestCase):
    def run_cli(self, *arguments: str) -> tuple[int, dict]:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exit_code = main(arguments)
        return exit_code, json.loads(output.getvalue())

    def test_success_is_json_with_zero_exit_code(self) -> None:
        exit_code, payload = self.run_cli(
            "--base-url", "http://API.EXAMPLE.TEST/", "--timeout", "1.25"
        )

        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["diagnostics"]["base_url"]["value"], "http://api.example.test")

    def test_package_metadata_exposes_independent_console_script(self) -> None:
        scripts = {
            entry_point.name: entry_point.value
            for entry_point in metadata.entry_points(group="console_scripts")
            if entry_point.name.startswith("test-02")
        }

        self.assertEqual(scripts["test-02"], "test_02.cli:main")
        self.assertEqual(scripts["test-02-diagnostics"], "test_02.diagnostics_cli:main")

    def test_failure_is_json_with_nonzero_exit_code(self) -> None:
        exit_code, payload = self.run_cli("--base-url", "ftp://example.test", "--timeout", "0")

        self.assertEqual(exit_code, 1)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["diagnostics"]["base_url"]["code"], "invalid_base_url")
        self.assertEqual(payload["diagnostics"]["timeout"]["code"], "invalid_timeout")


if __name__ == "__main__":
    unittest.main()

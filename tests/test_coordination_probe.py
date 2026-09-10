import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from unittest.mock import patch

import requests

from test_02.cli import main


class CoordinationProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                cls.paths.append(self.path)
                self.send_response(cls.status)
                self.end_headers()
                self.wfile.write(cls.body)

            def log_message(self, *args):
                pass

        cls.server = HTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def setUp(self):
        type(self).paths = []
        type(self).status = 200
        self.set_payload({"protocol": "se-coordination-v2", "revision": 1})

    def set_payload(self, payload):
        type(self).body = json.dumps(payload).encode()

    def run_probe(self):
        output, errors = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            result = main(["--base-url", self.base_url + "/", "coordination-probe"])
        return result, output.getvalue(), errors.getvalue()

    def test_success_uses_exact_endpoint_and_prints_json(self):
        result, output, errors = self.run_probe()
        self.assertEqual(result, 0)
        self.assertEqual(json.loads(output), {"protocol": "se-coordination-v2", "revision": 1})
        self.assertEqual(errors, "")
        self.assertEqual(self.paths, ["/api/coordination-probe"])

    def test_rejects_mismatched_or_missing_protocol(self):
        for protocol in ("other", "SE-COORDINATION-V2", None, True, 1, [], {}):
            with self.subTest(protocol=protocol):
                self.set_payload({"protocol": protocol, "revision": 1})
                self.assert_failure("protocol mismatch")
        self.set_payload({"revision": 1})
        self.assert_failure("protocol mismatch")

    def test_rejects_unsupported_revision_and_type_confusion(self):
        for revision in (0, 2, -1, True, False, 1.0, "1", None, [], {}):
            with self.subTest(revision=revision):
                self.set_payload({"protocol": "se-coordination-v2", "revision": revision})
                self.assert_failure("unsupported revision")
        self.set_payload({"protocol": "se-coordination-v2"})
        self.assert_failure("unsupported revision")

    def test_rejects_malformed_json_and_non_objects(self):
        type(self).body = b"not json"
        self.assert_failure("invalid JSON")
        for payload in ([], None, "text", 1, True):
            with self.subTest(payload=payload):
                self.set_payload(payload)
                self.assert_failure("non-object JSON")

    def test_rejects_http_error_even_with_valid_contract_body(self):
        type(self).status = 503
        self.assert_failure("HTTP 503")

    def test_network_errors_are_nonzero_without_success_output(self):
        for error in (requests.ConnectionError("unreachable"), requests.Timeout("timed out")):
            with self.subTest(error=error), patch("requests.Session.get", side_effect=error):
                self.assert_failure("transport failed")
        self.assertEqual(self.paths, [])

    def assert_failure(self, message):
        result, output, errors = self.run_probe()
        self.assertEqual(result, 1)
        self.assertEqual(output, "")
        self.assertIn(message, errors)
        self.assertTrue(errors.startswith("error: "))

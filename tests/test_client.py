import unittest

from test_02.client import ApiClient


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


class FakeSession:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.calls: list[tuple[str, float]] = []

    def get(self, url: str, *, timeout: float) -> FakeResponse:
        self.calls.append((url, timeout))
        return self.response


class ApiClientTests(unittest.TestCase):
    def test_health_uses_the_configured_base_url(self) -> None:
        session = FakeSession(FakeResponse({"status": "ok"}))
        client = ApiClient("http://api.example.test/", session=session)  # type: ignore[arg-type]

        self.assertEqual(client.health(), {"status": "ok"})
        self.assertEqual(session.calls, [("http://api.example.test/health", 5.0)])

    def test_list_items_reads_the_static_data_field(self) -> None:
        session = FakeSession(FakeResponse({"data": [{"id": "item-1"}]}))
        client = ApiClient("http://api.example.test", session=session)  # type: ignore[arg-type]

        self.assertEqual(client.list_items(), [{"id": "item-1"}])


if __name__ == "__main__":
    unittest.main()

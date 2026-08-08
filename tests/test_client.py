import copy
import unittest
from typing import Any

import requests

from test_02.client import MAX_PAGE, ApiClient, ApiError


def collection_envelope(
    *,
    data: list[dict[str, Any]] | None = None,
    query: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "data": data if data is not None else [{"id": "item-1"}],
        "pagination": {"page": 1, "limit": 20, "total": 1, "totalPages": 1},
        "query": query
        if query is not None
        else {
            "status": None,
            "category": None,
            "label": None,
            "q": None,
            "sort": None,
            "order": None,
            "page": 1,
            "limit": 20,
        },
    }


class FakeResponse:
    def __init__(
        self,
        payload: Any,
        *,
        status_code: int = 200,
        json_error: ValueError | None = None,
    ) -> None:
        self.payload = payload
        self.status_code = status_code
        self.json_error = json_error

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self) -> Any:
        if self.json_error is not None:
            raise self.json_error
        return self.payload


class FakeSession:
    def __init__(
        self,
        response: FakeResponse | None = None,
        *,
        error: requests.RequestException | None = None,
    ) -> None:
        self.response = response
        self.error = error
        self.calls: list[tuple[str, float, dict[str, str | int] | None]] = []

    def get(
        self,
        url: str,
        *,
        timeout: float,
        params: dict[str, str | int] | None = None,
    ) -> FakeResponse:
        self.calls.append((url, timeout, params))
        if self.error is not None:
            raise self.error
        assert self.response is not None
        return self.response


class QueryString(str):
    pass


class UnhashableQueryString(str):
    __hash__ = None  # type: ignore[assignment]


class ApiClientTests(unittest.TestCase):
    def test_health_uses_the_configured_base_url(self) -> None:
        session = FakeSession(FakeResponse({"status": "ok"}))
        client = ApiClient("http://api.example.test/", session=session)  # type: ignore[arg-type]

        self.assertEqual(client.health(), {"status": "ok"})
        self.assertEqual(session.calls, [("http://api.example.test/health", 5.0, None)])

    def test_list_items_preserves_the_data_only_contract(self) -> None:
        session = FakeSession(FakeResponse({"data": [{"id": "item-1"}]}))
        client = ApiClient("http://api.example.test", session=session)  # type: ignore[arg-type]

        self.assertEqual(client.list_items(), [{"id": "item-1"}])
        self.assertEqual(
            session.calls,
            [("http://api.example.test/api/items", 5.0, None)],
        )

    def test_discover_items_transports_all_supported_query_controls(self) -> None:
        expected_query = {
            "status": "active",
            "category": "core-service",
            "label": "featured",
            "q": "first",
            "sort": "name",
            "order": "desc",
            "page": 1,
            "limit": 1,
        }
        response = collection_envelope(
            data=[
                {
                    "id": "item-1",
                    "name": "First item",
                    "status": "active",
                    "category": "core-service",
                    "labels": ["featured", "read-only"],
                }
            ],
            query=expected_query,
        )
        response["pagination"]["limit"] = 1
        session = FakeSession(FakeResponse(response))
        client = ApiClient("http://api.example.test", session=session)  # type: ignore[arg-type]

        self.assertEqual(
            client.discover_items(
                status="active",
                category="core-service",
                label="featured",
                q="\ufeff FIRST \ufeff",
                sort="name",
                order="desc",
                page=1,
                limit=1,
            ),
            response,
        )
        self.assertEqual(
            session.calls,
            [
                (
                    "http://api.example.test/api/items",
                    5.0,
                    {
                        "status": "active",
                        "category": "core-service",
                        "label": "featured",
                        "q": "\ufeff FIRST \ufeff",
                        "sort": "name",
                        "order": "desc",
                        "page": 1,
                        "limit": 1,
                    },
                )
            ],
        )

    def test_discover_items_requests_an_envelope_with_pagination_defaults(self) -> None:
        response = collection_envelope()
        session = FakeSession(FakeResponse(response))
        client = ApiClient("http://api.example.test", session=session)  # type: ignore[arg-type]

        self.assertEqual(client.discover_items(), response)
        self.assertEqual(
            session.calls,
            [("http://api.example.test/api/items", 5.0, {"page": 1, "limit": 20})],
        )

    def test_discover_items_normalizes_string_subclasses_to_json_strings(self) -> None:
        response = collection_envelope(
            data=[],
            query={
                "status": "active",
                "category": "core-service",
                "label": "featured",
                "q": "first",
                "sort": "name",
                "order": "desc",
                "page": 1,
                "limit": 20,
            },
        )
        response["pagination"].update(total=0, totalPages=0)
        session = FakeSession(FakeResponse(response))
        client = ApiClient("http://api.example.test", session=session)  # type: ignore[arg-type]

        self.assertEqual(
            client.discover_items(
                status=QueryString("active"),
                category=QueryString("core-service"),
                label=QueryString("featured"),
                q=QueryString("FIRST"),
                sort=UnhashableQueryString("name"),
                order=UnhashableQueryString("desc"),
            ),
            response,
        )
        sent_params = session.calls[0][2]
        assert sent_params is not None
        self.assertTrue(all(type(value) in {str, int} for value in sent_params.values()))

    def test_discover_items_accepts_provider_unicode_case_normalization(self) -> None:
        response = collection_envelope(
            data=[],
            query={
                "status": None,
                "category": None,
                "label": None,
                "q": "\u1c8a",
                "sort": None,
                "order": None,
                "page": 1,
                "limit": 20,
            },
        )
        response["pagination"].update(total=0, totalPages=0)
        session = FakeSession(FakeResponse(response))
        client = ApiClient("http://api.example.test", session=session)  # type: ignore[arg-type]

        self.assertEqual(client.discover_items(q="\u1c89"), response)

    def test_invalid_discovery_options_fail_before_a_request(self) -> None:
        invalid_options = (
            {"label": "  "},
            {"label": "\ufeff"},
            {"q": ""},
            {"sort": "created"},
            {"sort": []},
            {"order": "descending"},
            {"order": {}},
            {"order": "asc"},
            {"page": 0},
            {"page": True},
            {"page": MAX_PAGE + 1},
            {"limit": 101},
        )

        for options in invalid_options:
            with self.subTest(options=options):
                session = FakeSession(FakeResponse(collection_envelope()))
                client = ApiClient(
                    "http://api.example.test",
                    session=session,  # type: ignore[arg-type]
                )

                with self.assertRaisesRegex(ApiError, "invalid discovery option"):
                    client.discover_items(**options)  # type: ignore[arg-type]

                self.assertEqual(session.calls, [])

    def test_discover_items_rejects_incomplete_or_inconsistent_envelopes(self) -> None:
        invalid_envelopes = []

        missing_query = collection_envelope()
        del missing_query["query"]
        invalid_envelopes.append(missing_query)

        non_object_item = collection_envelope()
        non_object_item["data"] = ["item-1"]
        invalid_envelopes.append(non_object_item)

        drifted_query = collection_envelope()
        drifted_query["query"]["label"] = "unexpected"
        invalid_envelopes.append(drifted_query)

        boolean_page = collection_envelope()
        boolean_page["query"]["page"] = True
        invalid_envelopes.append(boolean_page)

        inconsistent_total = collection_envelope()
        inconsistent_total["pagination"]["totalPages"] = 2
        invalid_envelopes.append(inconsistent_total)

        for envelope in invalid_envelopes:
            with self.subTest(envelope=envelope):
                session = FakeSession(FakeResponse(copy.deepcopy(envelope)))
                client = ApiClient(
                    "http://api.example.test",
                    session=session,  # type: ignore[arg-type]
                )

                with self.assertRaisesRegex(ApiError, "GET /api/items returned"):
                    client.discover_items()

    def test_transport_http_json_and_top_level_shape_errors_are_distinct(self) -> None:
        cases = (
            (
                FakeSession(error=requests.ConnectionError("offline")),
                "GET /api/items transport failed",
            ),
            (
                FakeSession(FakeResponse({}, status_code=422)),
                "GET /api/items returned HTTP 422",
            ),
            (
                FakeSession(FakeResponse({}, json_error=ValueError("bad json"))),
                "GET /api/items returned invalid JSON",
            ),
            (
                FakeSession(FakeResponse([])),
                "GET /api/items returned a non-object JSON payload",
            ),
        )

        for session, message in cases:
            with self.subTest(message=message):
                client = ApiClient(
                    "http://api.example.test",
                    session=session,  # type: ignore[arg-type]
                )

                with self.assertRaisesRegex(ApiError, message):
                    client.discover_items()


if __name__ == "__main__":
    unittest.main()

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


def facet_envelope(
    *,
    total: int = 2,
    by_label: dict[str, int] | None = None,
    by_category: dict[str, int] | None = None,
    include_by_category: bool = False,
    filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = {
        "total": total,
        "byLabel": by_label
        if by_label is not None
        else {"featured": 1, "read-only": 2, "support": 1},
    }
    if include_by_category:
        data["byCategory"] = by_category
    return {
        "data": data,
        "filters": filters
        if filters is not None
        else {
            "status": None,
            "category": None,
            "label": None,
            "q": None,
        },
    }


def summary_envelope(
    *,
    total: int = 2,
    by_status: dict[str, int] | None = None,
    by_category: dict[str, int] | None = None,
    global_total: int = 2,
    matching: int | None = None,
    insight_by_status: dict[str, int] | None = None,
    filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    status_counts = by_status if by_status is not None else {"active": 2}
    category_counts = (
        by_category
        if by_category is not None
        else {"core-service": 1, "support-service": 1}
    )
    return {
        "data": {
            "total": total,
            "byStatus": status_counts,
            "byCategory": category_counts,
        },
        "insights": {
            "total": global_total,
            "matching": total if matching is None else matching,
            "byStatus": (
                copy.deepcopy(status_counts)
                if insight_by_status is None
                else insight_by_status
            ),
            "filters": filters
            if filters is not None
            else {
                "status": None,
                "category": None,
                "label": None,
                "q": None,
            },
        },
    }


def capability_manifest() -> dict[str, Any]:
    item_filter_controls = {
        "status": {
            "type": "string",
            "cardinality": "single",
            "nonBlank": True,
            "match": "exact",
        },
        "category": {
            "type": "string",
            "cardinality": "single",
            "nonBlank": True,
            "match": "exact",
        },
        "label": {
            "type": "string",
            "cardinality": "single",
            "nonBlank": True,
            "match": "exact-membership",
        },
        "q": {
            "type": "string",
            "cardinality": "single",
            "nonBlank": True,
            "match": "case-insensitive-substring",
            "normalize": ["trim", "lowercase"],
        },
    }
    return {
        "schemaVersion": 1,
        "capabilities": [
            {"id": "health", "method": "GET", "path": "/health"},
            {
                "id": "item-collection",
                "method": "GET",
                "path": "/api/items",
                "controls": {
                    **copy.deepcopy(item_filter_controls),
                    "sort": {
                        "type": "string",
                        "cardinality": "single",
                        "values": ["id", "name", "status"],
                    },
                    "order": {
                        "type": "string",
                        "cardinality": "single",
                        "values": ["asc", "desc"],
                        "default": "asc",
                        "requires": "sort",
                    },
                    "page": {
                        "type": "integer",
                        "cardinality": "single",
                        "minimum": 1,
                        "maximum": MAX_PAGE,
                        "default": 1,
                        "defaultWhen": "any-control",
                    },
                    "limit": {
                        "type": "integer",
                        "cardinality": "single",
                        "minimum": 1,
                        "maximum": 100,
                        "default": 20,
                        "defaultWhen": "any-control",
                    },
                },
            },
            {
                "id": "item-facets",
                "method": "GET",
                "path": "/api/items/facets",
                "controls": copy.deepcopy(item_filter_controls),
            },
            {
                "id": "item-summary",
                "method": "GET",
                "path": "/api/items/summary",
                "controls": copy.deepcopy(item_filter_controls),
            },
            {
                "id": "capability-discovery",
                "method": "GET",
                "path": "/api/capabilities",
            },
        ],
    }


def capability_entry(manifest: dict[str, Any], capability_id: str) -> dict[str, Any]:
    return next(
        capability
        for capability in manifest["capabilities"]
        if capability["id"] == capability_id
    )


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


class QueuedSession:
    def __init__(self, responses: list[FakeResponse | BaseException]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, float, dict[str, str | int] | None]] = []

    def get(
        self,
        url: str,
        *,
        timeout: float,
        params: dict[str, str | int] | None = None,
    ) -> FakeResponse:
        self.calls.append((url, timeout, params))
        if not self.responses:
            raise AssertionError("unexpected request")
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


def paged_collection_envelope(
    *,
    page: int,
    limit: int,
    total: int,
    total_pages: int,
    data: list[dict[str, Any]],
    query: dict[str, Any] | None = None,
) -> dict[str, Any]:
    response = collection_envelope(data=data, query=copy.deepcopy(query))
    response["pagination"] = {
        "page": page,
        "limit": limit,
        "total": total,
        "totalPages": total_pages,
    }
    response["query"].update(page=page, limit=limit)
    return response


class QueryString(str):
    pass


class UnhashableQueryString(str):
    __hash__ = None  # type: ignore[assignment]


class MisleadingQueryString(str):
    def strip(self, chars: str | None = None) -> str:
        return "not blank"


class ApiClientTests(unittest.TestCase):
    def test_health_uses_the_configured_base_url(self) -> None:
        session = FakeSession(FakeResponse({"status": "ok"}))
        client = ApiClient("http://api.example.test/", session=session)  # type: ignore[arg-type]

        self.assertEqual(client.health(), {"status": "ok"})
        self.assertEqual(session.calls, [("http://api.example.test/health", 5.0, None)])

    def test_capabilities_validates_required_semantics_and_preserves_additions(
        self,
    ) -> None:
        manifest = capability_manifest()
        manifest["provider"] = {"name": "test-01"}
        collection = capability_entry(manifest, "item-collection")
        collection["documentation"] = {"stability": "stable"}
        collection["controls"]["limit"]["unit"] = "items"
        collection["controls"]["cursor"] = {"type": "string"}
        summary = capability_entry(manifest, "item-summary")
        summary["documentation"] = {"stability": "stable"}
        summary["controls"]["future-filter"] = {"type": "string"}
        manifest["capabilities"].append(
            {
                "id": "future-read-surface",
                "futureField": {"nested": True},
            }
        )
        session = FakeSession(FakeResponse(manifest))
        client = ApiClient("http://api.example.test/", session=session)  # type: ignore[arg-type]

        self.assertIs(client.capabilities(), manifest)
        self.assertEqual(
            session.calls,
            [("http://api.example.test/api/capabilities", 5.0, None)],
        )

    def test_capabilities_accepts_additive_reordered_supported_values(self) -> None:
        manifest = capability_manifest()
        controls = capability_entry(manifest, "item-collection")["controls"]
        controls["sort"]["values"] = ["future-sort", "status", "id", "name"]
        controls["order"]["values"] = ["desc", "future-order", "asc"]
        client = ApiClient(
            "http://api.example.test",
            session=FakeSession(FakeResponse(manifest)),  # type: ignore[arg-type]
        )

        self.assertIs(client.capabilities(), manifest)

    def test_capabilities_rejects_supported_values_missing_required_choices(
        self,
    ) -> None:
        for control_name, values in (
            ("sort", ["name", "status", "future-sort"]),
            ("order", ["asc", "future-order"]),
        ):
            with self.subTest(control=control_name):
                manifest = capability_manifest()
                capability_entry(manifest, "item-collection")["controls"][
                    control_name
                ]["values"] = values
                client = ApiClient(
                    "http://api.example.test",
                    session=FakeSession(FakeResponse(manifest)),  # type: ignore[arg-type]
                )

                with self.assertRaisesRegex(ApiError, "missing required values"):
                    client.capabilities()

    def test_capabilities_accepts_provider_ranges_wider_than_consumer_ranges(
        self,
    ) -> None:
        manifest = capability_manifest()
        controls = capability_entry(manifest, "item-collection")["controls"]
        controls["page"]["minimum"] = 0
        controls["page"]["maximum"] = MAX_PAGE + 1
        controls["limit"]["minimum"] = 0
        controls["limit"]["maximum"] = 200
        client = ApiClient(
            "http://api.example.test",
            session=FakeSession(FakeResponse(manifest)),  # type: ignore[arg-type]
        )

        self.assertIs(client.capabilities(), manifest)

    def test_capabilities_rejects_unsupported_schema_versions(self) -> None:
        for schema_version in (None, True, "1", 2):
            with self.subTest(schema_version=schema_version):
                manifest = capability_manifest()
                if schema_version is None:
                    del manifest["schemaVersion"]
                else:
                    manifest["schemaVersion"] = schema_version
                client = ApiClient(
                    "http://api.example.test",
                    session=FakeSession(FakeResponse(manifest)),  # type: ignore[arg-type]
                )

                with self.assertRaisesRegex(ApiError, "unsupported schema version"):
                    client.capabilities()

    def test_capabilities_rejects_malformed_entries_and_duplicate_ids(self) -> None:
        for capabilities in (None, {}, "health"):
            with self.subTest(capabilities=capabilities):
                manifest = capability_manifest()
                manifest["capabilities"] = capabilities
                client = ApiClient(
                    "http://api.example.test",
                    session=FakeSession(FakeResponse(manifest)),  # type: ignore[arg-type]
                )

                with self.assertRaisesRegex(ApiError, "malformed field 'capabilities'"):
                    client.capabilities()

        malformed_cases: list[Any] = [None, "health", {}, {"id": ""}, {"id": " health "}]
        for malformed_entry in malformed_cases:
            with self.subTest(malformed_entry=malformed_entry):
                manifest = capability_manifest()
                manifest["capabilities"].append(malformed_entry)
                client = ApiClient(
                    "http://api.example.test",
                    session=FakeSession(FakeResponse(manifest)),  # type: ignore[arg-type]
                )

                with self.assertRaisesRegex(ApiError, "malformed capability entry"):
                    client.capabilities()

        manifest = capability_manifest()
        manifest["capabilities"].append({"id": "health"})
        client = ApiClient(
            "http://api.example.test",
            session=FakeSession(FakeResponse(manifest)),  # type: ignore[arg-type]
        )

        with self.assertRaisesRegex(ApiError, "duplicate capability id 'health'"):
            client.capabilities()

    def test_capabilities_rejects_missing_required_capabilities(self) -> None:
        required_ids = (
            "health",
            "item-collection",
            "item-facets",
            "item-summary",
            "capability-discovery",
        )
        for missing_id in required_ids:
            with self.subTest(missing_id=missing_id):
                manifest = capability_manifest()
                manifest["capabilities"] = [
                    capability
                    for capability in manifest["capabilities"]
                    if capability["id"] != missing_id
                ]
                client = ApiClient(
                    "http://api.example.test",
                    session=FakeSession(FakeResponse(manifest)),  # type: ignore[arg-type]
                )

                with self.assertRaisesRegex(
                    ApiError,
                    f"missing required capability '{missing_id}'",
                ):
                    client.capabilities()

    def test_capabilities_rejects_incompatible_required_semantics(self) -> None:
        cases: list[tuple[str, dict[str, Any]]] = []

        wrong_method = capability_manifest()
        capability_entry(wrong_method, "health")["method"] = "POST"
        cases.append(("method", wrong_method))

        wrong_path = capability_manifest()
        capability_entry(wrong_path, "item-summary")["path"] = "/api/summary"
        cases.append(("path", wrong_path))

        wrong_control = capability_manifest()
        capability_entry(wrong_control, "item-summary")["controls"]["label"][
            "match"
        ] = "exact"
        cases.append(("control", wrong_control))

        wrong_default = capability_manifest()
        capability_entry(wrong_default, "item-collection")["controls"]["order"][
            "default"
        ] = "desc"
        cases.append(("default", wrong_default))

        wrong_page_limit = capability_manifest()
        capability_entry(wrong_page_limit, "item-collection")["controls"]["page"][
            "maximum"
        ] = MAX_PAGE - 1
        cases.append(("page maximum", wrong_page_limit))

        wrong_result_limit = capability_manifest()
        capability_entry(wrong_result_limit, "item-collection")["controls"]["limit"][
            "maximum"
        ] = 99
        cases.append(("result limit", wrong_result_limit))

        wrong_page_minimum = capability_manifest()
        capability_entry(wrong_page_minimum, "item-collection")["controls"]["page"][
            "minimum"
        ] = 2
        cases.append(("page minimum", wrong_page_minimum))

        for name, manifest in cases:
            with self.subTest(name=name):
                client = ApiClient(
                    "http://api.example.test",
                    session=FakeSession(FakeResponse(manifest)),  # type: ignore[arg-type]
                )

                with self.assertRaisesRegex(ApiError, "returned incompatible capability"):
                    client.capabilities()

    def test_capabilities_never_uses_cached_or_stale_manifest_data(self) -> None:
        manifest = capability_manifest()
        session = FakeSession(FakeResponse(manifest))
        client = ApiClient("http://api.example.test", session=session)  # type: ignore[arg-type]

        self.assertIs(client.capabilities(), manifest)
        session.error = requests.ConnectionError("offline")

        with self.assertRaisesRegex(
            ApiError,
            "GET /api/capabilities transport failed",
        ):
            client.capabilities()

        self.assertEqual(len(session.calls), 2)

    def test_capabilities_preserves_transport_http_json_and_shape_errors(self) -> None:
        cases = (
            (
                FakeSession(error=requests.ConnectionError("offline")),
                "GET /api/capabilities transport failed",
            ),
            (
                FakeSession(FakeResponse({}, status_code=503)),
                "GET /api/capabilities returned HTTP 503",
            ),
            (
                FakeSession(FakeResponse({}, json_error=ValueError("bad json"))),
                "GET /api/capabilities returned invalid JSON",
            ),
            (
                FakeSession(FakeResponse([])),
                "GET /api/capabilities returned a non-object JSON payload",
            ),
        )

        for session, message in cases:
            with self.subTest(message=message):
                client = ApiClient(
                    "http://api.example.test",
                    session=session,  # type: ignore[arg-type]
                )

                with self.assertRaisesRegex(ApiError, message):
                    client.capabilities()

    def test_list_items_preserves_the_data_only_contract(self) -> None:
        session = FakeSession(FakeResponse({"data": [{"id": "item-1"}]}))
        client = ApiClient("http://api.example.test", session=session)  # type: ignore[arg-type]

        self.assertEqual(client.list_items(), [{"id": "item-1"}])
        self.assertEqual(
            session.calls,
            [("http://api.example.test/api/items", 5.0, None)],
        )

    def test_iter_items_is_lazy_and_fetches_validated_pages_in_order(self) -> None:
        query = {
            "status": "active",
            "category": "core-service",
            "label": "featured",
            "q": "first",
            "sort": "name",
            "order": "desc",
            "page": 1,
            "limit": 1,
        }
        session = QueuedSession(
            [
                FakeResponse(
                    paged_collection_envelope(
                        page=1,
                        limit=1,
                        total=2,
                        total_pages=2,
                        data=[{"id": "item-1", "name": "First item"}],
                        query=query,
                    )
                ),
                FakeResponse(
                    paged_collection_envelope(
                        page=2,
                        limit=1,
                        total=2,
                        total_pages=2,
                        data=[{"id": "item-2", "name": "Second item"}],
                        query=query,
                    )
                ),
            ]
        )
        client = ApiClient("http://api.example.test", session=session)  # type: ignore[arg-type]

        items = client.iter_items(
            status="active",
            category="core-service",
            label="featured",
            q=" FIRST ",
            sort="name",
            order="desc",
            page_size=1,
            max_pages=5,
        )
        self.assertEqual(session.calls, [])
        self.assertEqual(next(items), {"id": "item-1", "name": "First item"})
        self.assertEqual(next(items), {"id": "item-2", "name": "Second item"})
        with self.assertRaises(StopIteration):
            next(items)

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
                        "q": " FIRST ",
                        "sort": "name",
                        "order": "desc",
                        "page": 1,
                        "limit": 1,
                    },
                ),
                (
                    "http://api.example.test/api/items",
                    5.0,
                    {
                        "status": "active",
                        "category": "core-service",
                        "label": "featured",
                        "q": " FIRST ",
                        "sort": "name",
                        "order": "desc",
                        "page": 2,
                        "limit": 1,
                    },
                ),
            ],
        )

    def test_iter_items_requests_once_for_empty_results(self) -> None:
        session = QueuedSession(
            [
                FakeResponse(
                    paged_collection_envelope(
                        page=1,
                        limit=2,
                        total=0,
                        total_pages=0,
                        data=[],
                    )
                )
            ]
        )
        client = ApiClient("http://api.example.test", session=session)  # type: ignore[arg-type]

        self.assertEqual(list(client.iter_items(page_size=2)), [])
        self.assertEqual(
            session.calls,
            [("http://api.example.test/api/items", 5.0, {"page": 1, "limit": 2})],
        )

    def test_iter_items_rejects_reported_page_budget_before_yielding(self) -> None:
        session = QueuedSession(
            [
                FakeResponse(
                    paged_collection_envelope(
                        page=1,
                        limit=1,
                        total=2,
                        total_pages=2,
                        data=[{"id": "item-1"}],
                    )
                )
            ]
        )
        client = ApiClient("http://api.example.test", session=session)  # type: ignore[arg-type]
        items = client.iter_items(page_size=1, max_pages=1)

        with self.assertRaisesRegex(ApiError, "exceeding max_pages 1"):
            next(items)
        self.assertEqual(len(session.calls), 1)

    def test_iter_items_validates_bounds_and_existing_options_before_http(self) -> None:
        invalid_options = (
            {"page_size": 0},
            {"page_size": 101},
            {"page_size": True},
            {"max_pages": 0},
            {"max_pages": -1},
            {"max_pages": True},
            {"sort": "created"},
            {"order": "asc"},
            {"label": "  "},
        )

        for options in invalid_options:
            with self.subTest(options=options):
                session = QueuedSession([])
                client = ApiClient(
                    "http://api.example.test",
                    session=session,  # type: ignore[arg-type]
                )
                items = client.iter_items(**options)  # type: ignore[arg-type]

                with self.assertRaisesRegex(ApiError, "invalid"):
                    next(items)
                self.assertEqual(session.calls, [])

    def test_iter_items_rejects_ids_before_yielding_a_bad_page(self) -> None:
        invalid_data = [
            [{"id": ""}, {"id": "item-2"}],
            [{"id": "item-1"}, {"id": "item-1"}],
            [{"id": "item-1"}, {"id": 2}],
        ]

        for data in invalid_data:
            with self.subTest(data=data):
                session = QueuedSession(
                    [
                        FakeResponse(
                            paged_collection_envelope(
                                page=1,
                                limit=2,
                                total=2,
                                total_pages=1,
                                data=data,
                            )
                        )
                    ]
                )
                client = ApiClient(
                    "http://api.example.test",
                    session=session,  # type: ignore[arg-type]
                )

                with self.assertRaisesRegex(ApiError, "item id"):
                    next(client.iter_items(page_size=2))
                self.assertEqual(len(session.calls), 1)

    def test_iter_items_rejects_cross_page_drift_and_duplicates_before_new_yields(
        self,
    ) -> None:
        drift_session = QueuedSession(
            [
                FakeResponse(
                    paged_collection_envelope(
                        page=1,
                        limit=1,
                        total=2,
                        total_pages=2,
                        data=[{"id": "item-1"}],
                    )
                ),
                FakeResponse(
                    paged_collection_envelope(
                        page=2,
                        limit=1,
                        total=3,
                        total_pages=3,
                        data=[{"id": "item-2"}],
                    )
                ),
            ]
        )
        drift_client = ApiClient(
            "http://api.example.test",
            session=drift_session,  # type: ignore[arg-type]
        )
        drift_items = drift_client.iter_items(page_size=1)
        self.assertEqual(next(drift_items), {"id": "item-1"})
        with self.assertRaisesRegex(ApiError, "totals that changed"):
            next(drift_items)
        self.assertEqual(len(drift_session.calls), 2)

        duplicate_session = QueuedSession(
            [
                FakeResponse(
                    paged_collection_envelope(
                        page=1,
                        limit=1,
                        total=2,
                        total_pages=2,
                        data=[{"id": "item-1"}],
                    )
                ),
                FakeResponse(
                    paged_collection_envelope(
                        page=2,
                        limit=1,
                        total=2,
                        total_pages=2,
                        data=[{"id": "item-1"}],
                    )
                ),
            ]
        )
        duplicate_client = ApiClient(
            "http://api.example.test",
            session=duplicate_session,  # type: ignore[arg-type]
        )
        duplicate_items = duplicate_client.iter_items(page_size=1)
        self.assertEqual(next(duplicate_items), {"id": "item-1"})
        with self.assertRaisesRegex(ApiError, "duplicate item id"):
            next(duplicate_items)
        self.assertEqual(len(duplicate_session.calls), 2)

    def test_iter_items_propagates_later_transport_failures_without_extra_fetches(
        self,
    ) -> None:
        session = QueuedSession(
            [
                FakeResponse(
                    paged_collection_envelope(
                        page=1,
                        limit=1,
                        total=2,
                        total_pages=2,
                        data=[{"id": "item-1"}],
                    )
                ),
                requests.ConnectionError("offline"),
            ]
        )
        client = ApiClient("http://api.example.test", session=session)  # type: ignore[arg-type]
        items = client.iter_items(page_size=1)

        self.assertEqual(next(items), {"id": "item-1"})
        with self.assertRaisesRegex(ApiError, "GET /api/items transport failed"):
            next(items)
        self.assertEqual(len(session.calls), 2)

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

    def test_item_facets_transports_supported_filters_and_validates_metadata(self) -> None:
        response = facet_envelope(
            total=1,
            by_label={"featured": 1, "read-only": 1},
            filters={
                "status": "active",
                "category": "core-service",
                "label": "featured",
                "q": "first",
            },
        )
        session = FakeSession(FakeResponse(response))
        client = ApiClient("http://api.example.test", session=session)  # type: ignore[arg-type]

        self.assertEqual(
            client.item_facets(
                status="active",
                category="core-service",
                label="featured",
                q="\ufeff FIRST \ufeff",
            ),
            response,
        )
        self.assertEqual(
            session.calls,
            [
                (
                    "http://api.example.test/api/items/facets",
                    5.0,
                    {
                        "status": "active",
                        "category": "core-service",
                        "label": "featured",
                        "q": "\ufeff FIRST \ufeff",
                    },
                )
            ],
        )

    def test_item_facets_accepts_empty_and_multi_label_results(self) -> None:
        valid_responses = (
            facet_envelope(total=0, by_label={}),
            facet_envelope(
                total=2,
                by_label={"featured": 1, "read-only": 2, "support": 1},
            ),
            facet_envelope(
                total=2,
                by_label={"featured": 1, "read-only": 2, "support": 1},
                by_category={"core-service": 1, "support-service": 1},
                include_by_category=True,
            ),
        )

        for response in valid_responses:
            with self.subTest(response=response):
                session = FakeSession(FakeResponse(response))
                client = ApiClient(
                    "http://api.example.test",
                    session=session,  # type: ignore[arg-type]
                )

                self.assertEqual(client.item_facets(), response)
                self.assertEqual(
                    session.calls,
                    [("http://api.example.test/api/items/facets", 5.0, {})],
                )

    def test_item_facets_preserves_additive_envelope_fields(self) -> None:
        response = facet_envelope(
            by_category={"core-service": 1, "support-service": 1},
            include_by_category=True,
        )
        response["provider"] = {"version": 1}
        response["data"]["futureAggregate"] = {"core-service": 1}
        response["filters"]["futureFilter"] = None
        session = FakeSession(FakeResponse(response))
        client = ApiClient(
            "http://api.example.test",
            session=session,  # type: ignore[arg-type]
        )

        self.assertEqual(client.item_facets(), response)

    def test_item_summary_transports_supported_filters_and_validates_insights(
        self,
    ) -> None:
        response = summary_envelope(
            total=1,
            by_status={"active": 1},
            by_category={"core-service": 1},
            global_total=2,
            filters={
                "status": "active",
                "category": "core-service",
                "label": "featured",
                "q": "first",
            },
        )
        session = FakeSession(FakeResponse(response))
        client = ApiClient(
            "http://api.example.test",
            session=session,  # type: ignore[arg-type]
        )

        self.assertEqual(
            client.item_summary(
                status="active",
                category="core-service",
                label="featured",
                q="\ufeff FIRST \ufeff",
            ),
            response,
        )
        self.assertEqual(
            session.calls,
            [
                (
                    "http://api.example.test/api/items/summary",
                    5.0,
                    {
                        "status": "active",
                        "category": "core-service",
                        "label": "featured",
                        "q": "\ufeff FIRST \ufeff",
                    },
                )
            ],
        )

    def test_item_summary_accepts_full_empty_and_additive_envelopes(self) -> None:
        full = summary_envelope()
        full["provider"] = {"version": 1}
        full["data"]["futureAggregate"] = {"active": 2}
        full["insights"]["futureInsight"] = True
        full["insights"]["filters"]["futureFilter"] = None

        empty = summary_envelope(
            total=0,
            by_status={},
            by_category={},
            global_total=2,
            filters={
                "status": None,
                "category": None,
                "label": None,
                "q": "missing",
            },
        )

        for response, options in ((full, {}), (empty, {"q": "missing"})):
            with self.subTest(response=response):
                session = FakeSession(FakeResponse(response))
                client = ApiClient(
                    "http://api.example.test",
                    session=session,  # type: ignore[arg-type]
                )

                self.assertEqual(client.item_summary(**options), response)

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

    def test_discover_items_accepts_contextual_provider_case_normalization(self) -> None:
        response = collection_envelope(
            data=[],
            query={
                "status": None,
                "category": None,
                "label": None,
                "q": "\u1c8a\u03c2",
                "sort": None,
                "order": None,
                "page": 1,
                "limit": 20,
            },
        )
        response["pagination"].update(total=0, totalPages=0)
        session = FakeSession(FakeResponse(response))
        client = ApiClient("http://api.example.test", session=session)  # type: ignore[arg-type]

        self.assertEqual(client.discover_items(q="\u1c89\u03a3"), response)

    def test_discover_items_accepts_intermediate_provider_unicode_table(self) -> None:
        response = collection_envelope(
            data=[],
            query={
                "status": None,
                "category": None,
                "label": None,
                "q": "\u1c8a\U00016ea0",
                "sort": None,
                "order": None,
                "page": 1,
                "limit": 20,
            },
        )
        response["pagination"].update(total=0, totalPages=0)
        session = FakeSession(FakeResponse(response))
        client = ApiClient("http://api.example.test", session=session)  # type: ignore[arg-type]

        self.assertEqual(client.discover_items(q="\u1c89\U00016ea0"), response)

    def test_discover_items_preserves_provider_final_sigma_boundaries(self) -> None:
        response = collection_envelope(
            data=[],
            query={
                "status": None,
                "category": None,
                "label": None,
                "q": "\u1c8a \u03c3",
                "sort": None,
                "order": None,
                "page": 1,
                "limit": 20,
            },
        )
        response["pagination"].update(total=0, totalPages=0)
        session = FakeSession(FakeResponse(response))
        client = ApiClient("http://api.example.test", session=session)  # type: ignore[arg-type]

        self.assertEqual(client.discover_items(q="\u1c89 \u03a3"), response)

    def test_discover_items_tracks_provider_case_ignorable_additions(self) -> None:
        response = collection_envelope(
            data=[],
            query={
                "status": None,
                "category": None,
                "label": None,
                "q": "a\u0897\u03c2",
                "sort": None,
                "order": None,
                "page": 1,
                "limit": 20,
            },
        )
        response["pagination"].update(total=0, totalPages=0)
        session = FakeSession(FakeResponse(response))
        client = ApiClient("http://api.example.test", session=session)  # type: ignore[arg-type]

        self.assertEqual(client.discover_items(q="A\u0897\u03a3"), response)

    def test_discover_items_rejects_unrelated_unicode_query_metadata(self) -> None:
        response = collection_envelope(
            data=[],
            query={
                "status": None,
                "category": None,
                "label": None,
                "q": "wrong",
                "sort": None,
                "order": None,
                "page": 1,
                "limit": 20,
            },
        )
        response["pagination"].update(total=0, totalPages=0)
        session = FakeSession(FakeResponse(response))
        client = ApiClient("http://api.example.test", session=session)  # type: ignore[arg-type]

        with self.assertRaisesRegex(ApiError, "query metadata"):
            client.discover_items(q="\u00e9")

        response["query"]["q"] = "x"
        session = FakeSession(FakeResponse(response))
        client = ApiClient("http://api.example.test", session=session)  # type: ignore[arg-type]

        with self.assertRaisesRegex(ApiError, "query metadata"):
            client.discover_items(q="\u0378")

    def test_invalid_discovery_options_fail_before_a_request(self) -> None:
        invalid_options = (
            {"label": "  "},
            {"label": "\ufeff"},
            {"label": MisleadingQueryString(" ")},
            {"q": ""},
            {"q": "\ud800"},
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

    def test_invalid_and_unsupported_facet_options_fail_before_a_request(self) -> None:
        invalid_options = (
            {"status": ""},
            {"category": "  "},
            {"label": "\ufeff"},
            {"q": "\ud800"},
            {"status": 1},
        )

        for options in invalid_options:
            with self.subTest(options=options):
                session = FakeSession(FakeResponse(facet_envelope()))
                client = ApiClient(
                    "http://api.example.test",
                    session=session,  # type: ignore[arg-type]
                )

                with self.assertRaisesRegex(ApiError, "invalid facet option"):
                    client.item_facets(**options)  # type: ignore[arg-type]

                self.assertEqual(session.calls, [])

    def test_invalid_and_unsupported_summary_options_fail_before_a_request(
        self,
    ) -> None:
        invalid_options = (
            {"status": ""},
            {"category": "  "},
            {"label": "\ufeff"},
            {"q": "\ud800"},
            {"status": 1},
        )

        for options in invalid_options:
            with self.subTest(options=options):
                session = FakeSession(FakeResponse(summary_envelope()))
                client = ApiClient(
                    "http://api.example.test",
                    session=session,  # type: ignore[arg-type]
                )

                with self.assertRaisesRegex(ApiError, "invalid summary option"):
                    client.item_summary(**options)  # type: ignore[arg-type]

                self.assertEqual(session.calls, [])

        for options in ({"sort": "name"}, {"page": 1}, {"limit": 20}):
            with self.subTest(options=options):
                session = FakeSession(FakeResponse(summary_envelope()))
                client = ApiClient(
                    "http://api.example.test",
                    session=session,  # type: ignore[arg-type]
                )

                with self.assertRaises(TypeError):
                    client.item_summary(**options)  # type: ignore[arg-type]

                self.assertEqual(session.calls, [])

        for options in ({"sort": "name"}, {"page": 1}, {"limit": 20}):
            with self.subTest(options=options):
                session = FakeSession(FakeResponse(facet_envelope()))
                client = ApiClient(
                    "http://api.example.test",
                    session=session,  # type: ignore[arg-type]
                )

                with self.assertRaises(TypeError):
                    client.item_facets(**options)  # type: ignore[arg-type]

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

    def test_item_facets_rejects_incomplete_or_invalid_envelopes(self) -> None:
        invalid_envelopes = []

        missing_filters = facet_envelope()
        del missing_filters["filters"]
        invalid_envelopes.append(missing_filters)

        incomplete_data = facet_envelope()
        del incomplete_data["data"]["byLabel"]
        invalid_envelopes.append(incomplete_data)

        boolean_total = facet_envelope()
        boolean_total["data"]["total"] = True
        invalid_envelopes.append(boolean_total)

        invalid_count = facet_envelope()
        invalid_count["data"]["byLabel"]["featured"] = 0
        invalid_envelopes.append(invalid_count)

        boolean_count = facet_envelope()
        boolean_count["data"]["byLabel"]["featured"] = True
        invalid_envelopes.append(boolean_count)

        count_above_total = facet_envelope(
            total=1,
            by_label={"featured": 2},
        )
        invalid_envelopes.append(count_above_total)

        counts_below_total = facet_envelope(
            total=2,
            by_label={"featured": 1},
        )
        invalid_envelopes.append(counts_below_total)

        labels_for_zero_matches = facet_envelope(
            total=0,
            by_label={"featured": 1},
        )
        invalid_envelopes.append(labels_for_zero_matches)

        invalid_category_map = facet_envelope(
            by_category=None,
            include_by_category=True,
        )
        invalid_envelopes.append(invalid_category_map)

        blank_category = facet_envelope(
            by_category={" ": 2},
            include_by_category=True,
        )
        invalid_envelopes.append(blank_category)

        boolean_category_count = facet_envelope(
            by_category={"core-service": True},  # type: ignore[dict-item]
            include_by_category=True,
        )
        invalid_envelopes.append(boolean_category_count)

        zero_category_count = facet_envelope(
            by_category={"core-service": 0},
            include_by_category=True,
        )
        invalid_envelopes.append(zero_category_count)

        negative_category_count = facet_envelope(
            by_category={"core-service": -1},
            include_by_category=True,
        )
        invalid_envelopes.append(negative_category_count)

        category_counts_above_total = facet_envelope(
            total=1,
            by_label={"featured": 1},
            by_category={"core-service": 2},
            include_by_category=True,
        )
        invalid_envelopes.append(category_counts_above_total)

        category_counts_below_total = facet_envelope(
            by_category={"core-service": 1},
            include_by_category=True,
        )
        invalid_envelopes.append(category_counts_below_total)

        categories_for_zero_matches = facet_envelope(
            total=0,
            by_label={},
            by_category={"core-service": 1},
            include_by_category=True,
        )
        invalid_envelopes.append(categories_for_zero_matches)

        incomplete_filters = facet_envelope()
        del incomplete_filters["filters"]["category"]
        invalid_envelopes.append(incomplete_filters)

        drifted_filters = facet_envelope()
        drifted_filters["filters"]["label"] = "unexpected"
        invalid_envelopes.append(drifted_filters)

        for envelope in invalid_envelopes:
            with self.subTest(envelope=envelope):
                session = FakeSession(FakeResponse(copy.deepcopy(envelope)))
                client = ApiClient(
                    "http://api.example.test",
                    session=session,  # type: ignore[arg-type]
                )

                with self.assertRaisesRegex(ApiError, "GET /api/items/facets returned"):
                    client.item_facets()

        missing_requested_label = facet_envelope(
            total=1,
            by_label={"read-only": 1},
            filters={
                "status": None,
                "category": None,
                "label": "featured",
                "q": None,
            },
        )
        session = FakeSession(FakeResponse(missing_requested_label))
        client = ApiClient(
            "http://api.example.test",
            session=session,  # type: ignore[arg-type]
        )

        with self.assertRaisesRegex(ApiError, "inconsistent with the request"):
            client.item_facets(label="featured")

        category_mismatch = facet_envelope(
            by_category={"core-service": 1, "support-service": 1},
            include_by_category=True,
            filters={
                "status": None,
                "category": "core-service",
                "label": None,
                "q": None,
            },
        )
        session = FakeSession(FakeResponse(category_mismatch))
        client = ApiClient(
            "http://api.example.test",
            session=session,  # type: ignore[arg-type]
        )

        with self.assertRaisesRegex(ApiError, "inconsistent with the request"):
            client.item_facets(category="core-service")

    def test_item_facets_preserves_transport_http_json_and_shape_errors(self) -> None:
        cases = (
            (
                FakeSession(error=requests.ConnectionError("offline")),
                "GET /api/items/facets transport failed",
            ),
            (
                FakeSession(FakeResponse({}, status_code=422)),
                "GET /api/items/facets returned HTTP 422",
            ),
            (
                FakeSession(FakeResponse({}, json_error=ValueError("bad json"))),
                "GET /api/items/facets returned invalid JSON",
            ),
            (
                FakeSession(FakeResponse([])),
                "GET /api/items/facets returned a non-object JSON payload",
            ),
        )

        for session, message in cases:
            with self.subTest(message=message):
                client = ApiClient(
                    "http://api.example.test",
                    session=session,  # type: ignore[arg-type]
                )

                with self.assertRaisesRegex(ApiError, message):
                    client.item_facets()

    def test_item_summary_rejects_incomplete_or_inconsistent_envelopes(self) -> None:
        invalid_envelopes = []

        missing_insights = summary_envelope()
        del missing_insights["insights"]
        invalid_envelopes.append(missing_insights)

        incomplete_data = summary_envelope()
        del incomplete_data["data"]["byCategory"]
        invalid_envelopes.append(incomplete_data)

        boolean_total = summary_envelope()
        boolean_total["data"]["total"] = True
        invalid_envelopes.append(boolean_total)

        negative_count = summary_envelope()
        negative_count["data"]["byStatus"]["active"] = -1
        invalid_envelopes.append(negative_count)

        inconsistent_status_total = summary_envelope()
        inconsistent_status_total["data"]["byStatus"]["active"] = 1
        invalid_envelopes.append(inconsistent_status_total)

        inconsistent_category_total = summary_envelope()
        inconsistent_category_total["data"]["byCategory"] = {"core-service": 1}
        invalid_envelopes.append(inconsistent_category_total)

        inconsistent_matching = summary_envelope(matching=1)
        invalid_envelopes.append(inconsistent_matching)

        global_below_matching = summary_envelope(global_total=1)
        invalid_envelopes.append(global_below_matching)

        inconsistent_insight_status = summary_envelope(
            insight_by_status={"inactive": 2}
        )
        invalid_envelopes.append(inconsistent_insight_status)

        incomplete_filters = summary_envelope()
        del incomplete_filters["insights"]["filters"]["label"]
        invalid_envelopes.append(incomplete_filters)

        for envelope in invalid_envelopes:
            with self.subTest(envelope=envelope):
                session = FakeSession(FakeResponse(copy.deepcopy(envelope)))
                client = ApiClient(
                    "http://api.example.test",
                    session=session,  # type: ignore[arg-type]
                )

                with self.assertRaisesRegex(
                    ApiError,
                    "GET /api/items/summary returned",
                ):
                    client.item_summary()

        drifted_filters = summary_envelope(
            total=1,
            by_status={"active": 1},
            by_category={"core-service": 1},
            filters={
                "status": "unexpected",
                "category": None,
                "label": None,
                "q": None,
            },
        )
        session = FakeSession(FakeResponse(drifted_filters))
        client = ApiClient(
            "http://api.example.test",
            session=session,  # type: ignore[arg-type]
        )

        with self.assertRaisesRegex(ApiError, "does not match the request"):
            client.item_summary(status="active")

    def test_item_summary_preserves_transport_http_json_and_shape_errors(self) -> None:
        cases = (
            (
                FakeSession(error=requests.ConnectionError("offline")),
                "GET /api/items/summary transport failed",
            ),
            (
                FakeSession(FakeResponse({}, status_code=422)),
                "GET /api/items/summary returned HTTP 422",
            ),
            (
                FakeSession(FakeResponse({}, json_error=ValueError("bad json"))),
                "GET /api/items/summary returned invalid JSON",
            ),
            (
                FakeSession(FakeResponse([])),
                "GET /api/items/summary returned a non-object JSON payload",
            ),
        )

        for session, message in cases:
            with self.subTest(message=message):
                client = ApiClient(
                    "http://api.example.test",
                    session=session,  # type: ignore[arg-type]
                )

                with self.assertRaisesRegex(ApiError, message):
                    client.item_summary()

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

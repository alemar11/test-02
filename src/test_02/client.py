import math
from collections.abc import Iterator
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import requests

JsonObject = dict[str, Any]
QueryValue = str | int
MAX_PAGE = 9_007_199_254_740_991

_COLLECTION_KEYS = {"data", "pagination", "query"}
_PAGINATION_KEYS = {"page", "limit", "total", "totalPages"}
_QUERY_KEYS = {
    "status",
    "category",
    "label",
    "q",
    "sort",
    "order",
    "page",
    "limit",
}
_FACET_ENVELOPE_KEYS = {"data", "filters"}
_FACET_DATA_KEYS = {"total", "byLabel"}
_FACET_FILTER_KEYS = {"status", "category", "label", "q"}
_ITEM_DATA_KEYS = {"id", "name", "status", "category", "labels"}
_SUMMARY_ENVELOPE_KEYS = {"data", "insights"}
_SUMMARY_DATA_KEYS = {"total", "byStatus", "byCategory"}
_SUMMARY_INSIGHT_KEYS = {"total", "matching", "byStatus", "filters"}
_BATCH_ENVELOPE_KEYS = {"data", "missing"}
_SORT_FIELDS = {"id", "name", "status"}
_SORT_ORDERS = {"asc", "desc"}
MAX_BATCH_IDS = 50
_ITEM_ID_PATTERN = re.compile(r"[A-Za-z0-9_-]+")
_CAPABILITY_PATH = "GET /api/capabilities"
_SUPPORTED_CAPABILITY_SCHEMA_VERSION = 1
_ITEM_FILTER_CAPABILITY_CONTROLS: JsonObject = {
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
_REQUIRED_CAPABILITIES: dict[str, JsonObject] = {
    "health": {
        "method": "GET",
        "path": "/health",
    },
    "item-collection": {
        "method": "GET",
        "path": "/api/items",
        "controls": {
            **_ITEM_FILTER_CAPABILITY_CONTROLS,
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
    "item-facets": {
        "method": "GET",
        "path": "/api/items/facets",
        "controls": _ITEM_FILTER_CAPABILITY_CONTROLS,
    },
    "item-summary": {
        "method": "GET",
        "path": "/api/items/summary",
        "controls": _ITEM_FILTER_CAPABILITY_CONTROLS,
    },
    "capability-discovery": {
        "method": "GET",
        "path": "/api/capabilities",
    },
}
_OPTIONAL_CAPABILITIES: dict[str, JsonObject] = {
    "item-batch": {
        "method": "GET",
        "path": "/api/items/batch",
        "controls": {
            "ids": {
                "type": "string",
                "cardinality": "single",
                "nonBlank": True,
                "minimum": 1,
                "maximum": MAX_BATCH_IDS,
            },
        },
    },
}
_ECMASCRIPT_TRIM_CHARACTERS = (
    "\u0009\u000a\u000b\u000c\u000d\u0020\u00a0\u1680"
    "\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a"
    "\u2028\u2029\u202f\u205f\u3000\ufeff"
)


def _characters_in(*ranges: tuple[int, int]) -> frozenset[str]:
    return frozenset(
        chr(codepoint)
        for start, end in ranges
        for codepoint in range(start, end + 1)
    )


_UNICODE_16_LOWERCASE = {
    "\u1c89": "\u1c8a",
    "\ua7cb": "\u0264",
    "\ua7cc": "\ua7cd",
    "\ua7da": "\ua7db",
    "\ua7dc": "\u019b",
    **{
        chr(codepoint): chr(codepoint + 0x20)
        for codepoint in range(0x10D50, 0x10D66)
    },
}
_UNICODE_17_LOWERCASE = {
    **_UNICODE_16_LOWERCASE,
    "\ua7ce": "\ua7cf",
    "\ua7d2": "\ua7d3",
    "\ua7d4": "\ua7d5",
    **{
        chr(codepoint): chr(codepoint + 0x1B)
        for codepoint in range(0x16EA0, 0x16EB9)
    },
}
_UNICODE_16_CASED_ADDITIONS = _characters_in(
    (0x1C89, 0x1C8A),
    (0xA7CB, 0xA7CD),
    (0xA7DA, 0xA7DC),
    (0x10D50, 0x10D65),
    (0x10D70, 0x10D85),
)
_UNICODE_16_CASE_IGNORABLE_ADDITIONS = _characters_in(
    (0x0897, 0x0897),
    (0x10D4E, 0x10D4E),
    (0x10D69, 0x10D6D),
    (0x10D6F, 0x10D6F),
    (0x10EFC, 0x10EFC),
    (0x113BB, 0x113C0),
    (0x113CE, 0x113CE),
    (0x113D0, 0x113D0),
    (0x113D2, 0x113D2),
    (0x113E1, 0x113E2),
    (0x11F5A, 0x11F5A),
    (0x1611E, 0x16129),
    (0x1612D, 0x1612F),
    (0x16D40, 0x16D42),
    (0x16D6B, 0x16D6C),
    (0x1E5EE, 0x1E5EF),
)
_UNICODE_17_CASED_ADDITIONS = _characters_in(
    (0x1C89, 0x1C8A),
    (0xA7CB, 0xA7CF),
    (0xA7D2, 0xA7D2),
    (0xA7D4, 0xA7D4),
    (0xA7DA, 0xA7DC),
    (0x10D50, 0x10D65),
    (0x10D70, 0x10D85),
    (0x16EA0, 0x16EB8),
    (0x16EBB, 0x16ED3),
)
_UNICODE_17_CASE_IGNORABLE_ADDITIONS = _characters_in(
    (0x0897, 0x0897),
    (0x1ACF, 0x1ADD),
    (0x1AE0, 0x1AEB),
    (0xA7F1, 0xA7F1),
    (0x10D4E, 0x10D4E),
    (0x10D69, 0x10D6D),
    (0x10D6F, 0x10D6F),
    (0x10EC5, 0x10EC5),
    (0x10EFA, 0x10EFC),
    (0x113BB, 0x113C0),
    (0x113CE, 0x113CE),
    (0x113D0, 0x113D0),
    (0x113D2, 0x113D2),
    (0x113E1, 0x113E2),
    (0x11B60, 0x11B60),
    (0x11B62, 0x11B64),
    (0x11B66, 0x11B66),
    (0x11DD9, 0x11DD9),
    (0x11F5A, 0x11F5A),
    (0x1611E, 0x16129),
    (0x1612D, 0x1612F),
    (0x16D40, 0x16D42),
    (0x16D6B, 0x16D6C),
    (0x16FF2, 0x16FF3),
    (0x1E5EE, 0x1E5EF),
    (0x1E6E3, 0x1E6E3),
    (0x1E6E6, 0x1E6E6),
    (0x1E6EE, 0x1E6EF),
    (0x1E6F5, 0x1E6F5),
    (0x1E6FF, 0x1E6FF),
)
_PROVIDER_UNICODE_TABLES = (
    (
        _UNICODE_16_LOWERCASE,
        _UNICODE_16_CASED_ADDITIONS,
        _UNICODE_16_CASE_IGNORABLE_ADDITIONS,
        frozenset("\U0001171e"),
    ),
    (
        _UNICODE_17_LOWERCASE,
        _UNICODE_17_CASED_ADDITIONS,
        _UNICODE_17_CASE_IGNORABLE_ADDITIONS,
        frozenset("\u0295\U0001171e"),
    ),
)


class ApiError(RuntimeError):
    """Raised when the API cannot return a valid response."""


def _validate_timeout(timeout: Any) -> None:
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
        raise ApiError("timeout must be a finite positive number")
    if isinstance(timeout, float) and not math.isfinite(timeout):
        raise ApiError("timeout must be a finite positive number")
    if timeout <= 0:
        raise ApiError("timeout must be a finite positive number")


@dataclass
class ApiClient:
    base_url: str
    timeout: int | float = 5.0
    session: requests.Session | None = None

    def __post_init__(self) -> None:
        _validate_timeout(self.timeout)
        self.base_url = self.base_url.rstrip("/")
        if self.session is None:
            self.session = requests.Session()

    def health(self) -> JsonObject:
        return self._get("/health")

    def capabilities(self) -> JsonObject:
        """Return the provider manifest after validating required compatibility."""
        payload = self._get("/api/capabilities")
        _validate_capability_manifest(payload)
        return payload

    def list_items(self) -> list[JsonObject]:
        payload = self._get("/api/items")
        data = payload.get("data")
        if not isinstance(data, list):
            raise ApiError("API response field 'data' must be a list")
        return data

    def get_item(self, item_id: str) -> JsonObject:
        """Return the validated item identified by one exact path-segment ID."""
        item_id = _item_id(item_id)
        encoded_item_id = _item_path_segment(item_id)
        payload = self._get(
            f"/api/items/{encoded_item_id}",
            preserve_path_encoding=item_id in {".", ".."},
        )
        _validate_item_envelope(payload, item_id, encoded_item_id)
        return payload["data"]

    def get_items(self, ids: list[str]) -> JsonObject:
        """Return found items and missing IDs for one validated batch request."""
        requested_ids = _validate_batch_ids(ids)
        payload = self._get(
            "/api/items/batch",
            params={"ids": ",".join(requested_ids)},
        )
        _validate_batch_envelope(payload, requested_ids)
        return payload

    def discover_items(
        self,
        *,
        status: str | None = None,
        category: str | None = None,
        label: str | None = None,
        q: str | None = None,
        sort: str | None = None,
        order: str | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> JsonObject:
        """Return a validated collection envelope for an item discovery query."""
        params, expected_query, normalized_queries = _discovery_query(
            status=status,
            category=category,
            label=label,
            q=q,
            sort=sort,
            order=order,
            page=page,
            limit=limit,
        )
        payload = self._get("/api/items", params=params)
        _validate_collection_envelope(payload, expected_query, normalized_queries)
        return payload

    def item_facets(
        self,
        *,
        status: str | None = None,
        category: str | None = None,
        label: str | None = None,
        q: str | None = None,
    ) -> JsonObject:
        """Return validated label facets for the complete matching item set."""
        params, expected_filters, normalized_queries = _facet_query(
            status=status,
            category=category,
            label=label,
            q=q,
        )
        payload = self._get("/api/items/facets", params=params)
        _validate_facet_envelope(payload, expected_filters, normalized_queries)
        return payload

    def item_summary(
        self,
        *,
        status: str | None = None,
        category: str | None = None,
        label: str | None = None,
        q: str | None = None,
    ) -> JsonObject:
        """Return validated provider-owned aggregates for matching items."""
        params, expected_filters, normalized_queries = _summary_query(
            status=status,
            category=category,
            label=label,
            q=q,
        )
        payload = self._get("/api/items/summary", params=params)
        _validate_summary_envelope(payload, expected_filters, normalized_queries)
        return payload

    def iter_items(
        self,
        *,
        status: str | None = None,
        category: str | None = None,
        label: str | None = None,
        q: str | None = None,
        sort: str | None = None,
        order: str | None = None,
        page_size: int = 100,
        max_pages: int = 1000,
    ) -> Iterator[JsonObject]:
        """Lazily yield every item from the matching catalog pages.

        Each page is validated before any of its items are yielded. An
        ``ApiError`` from a later page can therefore occur after earlier items
        have already been yielded.
        """
        if type(page_size) is not int or not 1 <= page_size <= 100:
            raise ApiError(
                "invalid iteration option 'page_size': "
                "expected an integer from 1 to 100"
            )
        if type(max_pages) is not int or max_pages < 1:
            raise ApiError(
                "invalid iteration option 'max_pages': "
                "expected a positive integer"
            )

        first_page = self.discover_items(
            status=status,
            category=category,
            label=label,
            q=q,
            sort=sort,
            order=order,
            page=1,
            limit=page_size,
        )
        first_pagination = first_page["pagination"]
        expected_total = first_pagination["total"]
        expected_total_pages = first_pagination["totalPages"]
        if expected_total_pages > max_pages:
            raise ApiError(
                "GET /api/items reported "
                f"{expected_total_pages} pages, exceeding max_pages {max_pages}"
            )

        seen_ids: set[str] = set()
        page = first_page
        for page_number in range(1, expected_total_pages + 1):
            if page_number > 1:
                page = self.discover_items(
                    status=status,
                    category=category,
                    label=label,
                    q=q,
                    sort=sort,
                    order=order,
                    page=page_number,
                    limit=page_size,
                )

                pagination = page["pagination"]
                if (
                    pagination["total"] != expected_total
                    or pagination["totalPages"] != expected_total_pages
                ):
                    raise ApiError(
                        "GET /api/items returned pagination totals that changed "
                        "during iteration"
                    )

            page_items = page["data"]
            page_ids: set[str] = set()
            for item in page_items:
                item_id = item.get("id")
                if type(item_id) is not str or not _ecmascript_trim(item_id):
                    raise ApiError(
                        "GET /api/items returned an item with an invalid item id; "
                        "expected a non-blank string"
                    )
                if item_id in page_ids or item_id in seen_ids:
                    raise ApiError(
                        f"GET /api/items returned duplicate item id {item_id!r}"
                    )
                page_ids.add(item_id)

            seen_ids.update(page_ids)
            yield from page_items

    def _get(
        self,
        path: str,
        *,
        params: dict[str, QueryValue] | None = None,
        preserve_path_encoding: bool = False,
    ) -> JsonObject:
        assert self.session is not None

        try:
            request_options: dict[str, Any] = {"timeout": self.timeout}
            if params is not None:
                request_options["params"] = params
            url = f"{self.base_url}{path}"
            if preserve_path_encoding and isinstance(self.session, requests.Session):
                # requests' URL preparation decodes percent-encoded unreserved
                # characters, including the dots in %2E and %2E%2E. Prepare the
                # request for normal session configuration, then restore the
                # exact encoded URL before the adapter sends it.
                prepared = self.session.prepare_request(
                    requests.Request("GET", url, params=params)
                )
                prepared.url = url
                response = self.session.send(prepared, timeout=self.timeout)
            else:
                response = self.session.get(url, **request_options)
        except requests.RequestException as error:
            raise ApiError(f"GET {path} transport failed: {error}") from error

        try:
            response.raise_for_status()
        except requests.HTTPError as error:
            raise ApiError(f"GET {path} returned HTTP {response.status_code}") from error
        except requests.RequestException as error:
            raise ApiError(f"GET {path} transport failed: {error}") from error

        try:
            payload = response.json()
        except ValueError as error:
            raise ApiError(f"GET {path} returned invalid JSON") from error

        if not isinstance(payload, dict):
            raise ApiError(f"GET {path} returned a non-object JSON payload")
        return payload


def _validate_capability_manifest(payload: JsonObject) -> None:
    schema_version = payload.get("schemaVersion")
    if (
        type(schema_version) is not int
        or schema_version != _SUPPORTED_CAPABILITY_SCHEMA_VERSION
    ):
        raise ApiError(
            f"{_CAPABILITY_PATH} returned unsupported schema version "
            f"{schema_version!r}; expected {_SUPPORTED_CAPABILITY_SCHEMA_VERSION}"
        )

    capabilities = payload.get("capabilities")
    if not isinstance(capabilities, list):
        raise ApiError(
            f"{_CAPABILITY_PATH} returned malformed field 'capabilities'; "
            "expected a list"
        )

    capabilities_by_id: dict[str, JsonObject] = {}
    for index, capability in enumerate(capabilities):
        if not isinstance(capability, dict):
            raise ApiError(
                f"{_CAPABILITY_PATH} returned malformed capability entry at "
                f"index {index}; expected an object"
            )

        capability_id = capability.get("id")
        if (
            type(capability_id) is not str
            or not capability_id
            or capability_id.strip() != capability_id
        ):
            raise ApiError(
                f"{_CAPABILITY_PATH} returned malformed capability entry at "
                f"index {index}; field 'id' must be a non-blank trimmed string"
            )
        if capability_id in capabilities_by_id:
            raise ApiError(
                f"{_CAPABILITY_PATH} returned duplicate capability id "
                f"{capability_id!r}"
            )
        capabilities_by_id[capability_id] = capability

    for capability_id, required_fields in _REQUIRED_CAPABILITIES.items():
        capability = capabilities_by_id.get(capability_id)
        if capability is None:
            raise ApiError(
                f"{_CAPABILITY_PATH} is missing required capability "
                f"{capability_id!r}"
            )
        _validate_required_capability_subset(
            capability,
            required_fields,
            location=f"capability {capability_id!r}",
        )

    for capability_id, optional_fields in _OPTIONAL_CAPABILITIES.items():
        capability = capabilities_by_id.get(capability_id)
        if capability is not None:
            _validate_required_capability_subset(
                capability,
                optional_fields,
                location=f"capability {capability_id!r}",
            )


def _validate_required_capability_subset(
    actual: Any,
    required: Any,
    *,
    location: str,
) -> None:
    if isinstance(required, dict):
        if not isinstance(actual, dict):
            raise ApiError(
                f"{_CAPABILITY_PATH} returned incompatible {location}; "
                "expected an object"
            )
        for name, required_value in required.items():
            if name not in actual:
                raise ApiError(
                    f"{_CAPABILITY_PATH} returned incompatible {location}; "
                    f"missing required field {name!r}"
                )
            _validate_required_capability_subset(
                actual[name],
                required_value,
                location=f"{location}.{name}",
            )
        return

    if isinstance(required, list):
        if not isinstance(actual, list):
            raise ApiError(
                f"{_CAPABILITY_PATH} returned incompatible {location}; "
                f"expected {required!r}"
            )

        if location.endswith(".values"):
            missing_values = [
                required_value
                for required_value in required
                if not any(
                    type(actual_value) is type(required_value)
                    and actual_value == required_value
                    for actual_value in actual
                )
            ]
            if missing_values:
                raise ApiError(
                    f"{_CAPABILITY_PATH} returned incompatible {location}; "
                    f"missing required values {missing_values!r}"
                )
            return

        if len(actual) != len(required):
            raise ApiError(
                f"{_CAPABILITY_PATH} returned incompatible {location}; "
                f"expected {required!r}"
            )
        for index, (actual_value, required_value) in enumerate(zip(actual, required)):
            _validate_required_capability_subset(
                actual_value,
                required_value,
                location=f"{location}[{index}]",
            )
        return

    if location.endswith(".minimum"):
        if (
            type(actual) not in (int, float)
            or (type(actual) is float and not math.isfinite(actual))
            or actual > required
        ):
            raise ApiError(
                f"{_CAPABILITY_PATH} returned incompatible {location}; "
                f"expected a value no greater than {required!r}"
            )
        return

    if location.endswith(".maximum"):
        if (
            type(actual) not in (int, float)
            or (type(actual) is float and not math.isfinite(actual))
            or actual < required
        ):
            raise ApiError(
                f"{_CAPABILITY_PATH} returned incompatible {location}; "
                f"expected a value no less than {required!r}"
            )
        return

    if type(actual) is not type(required) or actual != required:
        raise ApiError(
            f"{_CAPABILITY_PATH} returned incompatible {location}; "
            f"expected {required!r}"
        )


def _discovery_query(
    *,
    status: str | None,
    category: str | None,
    label: str | None,
    q: str | None,
    sort: str | None,
    order: str | None,
    page: int,
    limit: int,
) -> tuple[dict[str, QueryValue], JsonObject, frozenset[str] | None]:
    filter_values: dict[str, str | None] = {}
    for name, value in (
        ("status", status),
        ("category", category),
        ("label", label),
        ("q", q),
    ):
        canonical_value = _canonical_query_string(name, value)
        if canonical_value is not None and not _ecmascript_trim(canonical_value):
            raise ApiError(f"invalid discovery option '{name}': expected a non-blank string")
        filter_values[name] = canonical_value

    status = filter_values["status"]
    category = filter_values["category"]
    label = filter_values["label"]
    q = filter_values["q"]
    sort = _canonical_query_string("sort", sort)
    order = _canonical_query_string("order", order)

    if sort is not None and sort not in _SORT_FIELDS:
        raise ApiError("invalid discovery option 'sort': expected id, name, or status")
    if order is not None and order not in _SORT_ORDERS:
        raise ApiError("invalid discovery option 'order': expected asc or desc")
    if order is not None and sort is None:
        raise ApiError("invalid discovery option 'order': requires 'sort'")
    if type(page) is not int or not 1 <= page <= MAX_PAGE:
        raise ApiError(
            f"invalid discovery option 'page': expected an integer from 1 to {MAX_PAGE}"
        )
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ApiError("invalid discovery option 'limit': expected an integer from 1 to 100")

    params: dict[str, QueryValue] = {}
    for name, value in (
        ("status", status),
        ("category", category),
        ("label", label),
        ("q", q),
        ("sort", sort),
        ("order", order),
    ):
        if value is not None:
            params[name] = value
    params["page"] = page
    params["limit"] = limit

    normalized_queries = (
        _compatible_query_normalizations(q) if q is not None else None
    )
    expected_query: JsonObject = {
        "status": status,
        "category": category,
        "label": label,
        "q": _ecmascript_trim(q).lower() if q is not None else None,
        "sort": sort,
        "order": (order or "asc") if sort is not None else None,
        "page": page,
        "limit": limit,
    }
    return params, expected_query, normalized_queries


def _facet_query(
    *,
    status: str | None,
    category: str | None,
    label: str | None,
    q: str | None,
) -> tuple[dict[str, QueryValue], JsonObject, frozenset[str] | None]:
    return _filtered_query(
        status=status,
        category=category,
        label=label,
        q=q,
        option_group="facet",
    )


def _summary_query(
    *,
    status: str | None,
    category: str | None,
    label: str | None,
    q: str | None,
) -> tuple[dict[str, QueryValue], JsonObject, frozenset[str] | None]:
    return _filtered_query(
        status=status,
        category=category,
        label=label,
        q=q,
        option_group="summary",
    )


def _filtered_query(
    *,
    status: str | None,
    category: str | None,
    label: str | None,
    q: str | None,
    option_group: str,
) -> tuple[dict[str, QueryValue], JsonObject, frozenset[str] | None]:
    filter_values: dict[str, str | None] = {}
    for name, value in (
        ("status", status),
        ("category", category),
        ("label", label),
        ("q", q),
    ):
        canonical_value = _canonical_query_string(
            name,
            value,
            option_group=option_group,
        )
        if canonical_value is not None and not _ecmascript_trim(canonical_value):
            raise ApiError(
                f"invalid {option_group} option '{name}': "
                "expected a non-blank string"
            )
        filter_values[name] = canonical_value

    status = filter_values["status"]
    category = filter_values["category"]
    label = filter_values["label"]
    q = filter_values["q"]
    params = {
        name: value
        for name, value in filter_values.items()
        if value is not None
    }
    normalized_queries = (
        _compatible_query_normalizations(q) if q is not None else None
    )
    expected_filters: JsonObject = {
        "status": status,
        "category": category,
        "label": label,
        "q": _ecmascript_trim(q).lower() if q is not None else None,
    }
    return params, expected_filters, normalized_queries


def _item_id(item_id: Any) -> str:
    if not isinstance(item_id, str):
        raise ApiError("invalid item id: expected a string")
    try:
        # Calling the base implementation rejects surrogate code points before
        # requests encodes the path and keeps the exact ID text unchanged.
        item_id = str.encode(item_id, "utf-8", "strict").decode("utf-8")
    except UnicodeError as error:
        raise ApiError("invalid item id: expected a valid Unicode string") from error
    if not _ecmascript_trim(item_id):
        raise ApiError("invalid item id: expected a non-blank string")
    return item_id


def _item_path_segment(item_id: str) -> str:
    encoded_item_id = quote(item_id, safe="")
    if item_id == ".":
        return "%2E"
    if item_id == "..":
        return "%2E%2E"
    return encoded_item_id

def _validate_batch_ids(ids: Any) -> list[str]:
    if type(ids) is not list:
        raise ApiError("invalid batch ids: expected a list")
    if not 1 <= len(ids) <= MAX_BATCH_IDS:
        raise ApiError(
            "invalid batch ids: expected between 1 and "
            f"{MAX_BATCH_IDS} ids"
        )

    normalized_ids: list[str] = []
    seen_ids: set[str] = set()
    for index, item_id in enumerate(ids):
        if not isinstance(item_id, str):
            raise ApiError(
                f"invalid batch id at index {index}: expected a string"
            )
        try:
            normalized_id = str.encode(item_id, "utf-8", "strict").decode("utf-8")
        except UnicodeError as error:
            raise ApiError(
                f"invalid batch id at index {index}: expected a valid Unicode string"
            ) from error
        if _ITEM_ID_PATTERN.fullmatch(normalized_id) is None:
            raise ApiError(
                f"invalid batch id at index {index}: expected only letters, "
                "digits, underscores, or hyphens"
            )
        if normalized_id in seen_ids:
            raise ApiError(f"invalid batch ids: duplicate id {normalized_id!r}")
        seen_ids.add(normalized_id)
        normalized_ids.append(normalized_id)

    return normalized_ids


def _canonical_query_string(
    name: str,
    value: Any,
    *,
    option_group: str = "discovery",
) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ApiError(f"invalid {option_group} option '{name}': expected a string")
    try:
        # Calling the base implementation avoids overridden methods on a str
        # subclass and rejects surrogate code points before requests encodes them.
        return str.encode(value, "utf-8", "strict").decode("utf-8")
    except UnicodeError as error:
        raise ApiError(
            f"invalid {option_group} option '{name}': expected a valid Unicode string"
        ) from error


def _ecmascript_trim(value: str) -> str:
    return value.strip(_ECMASCRIPT_TRIM_CHARACTERS)


def _compatible_query_normalizations(value: str) -> frozenset[str]:
    trimmed_value = _ecmascript_trim(value)
    normalizations = {trimmed_value.lower()}
    for table in _PROVIDER_UNICODE_TABLES:
        normalizations.add(
            _provider_unicode_lower(trimmed_value, *table)
        )
    return frozenset(normalizations)


def _provider_unicode_lower(
    value: str,
    lowercase_mappings: dict[str, str],
    cased_additions: frozenset[str],
    case_ignorable_additions: frozenset[str],
    context_removals: frozenset[str],
) -> str:
    # Python and supported provider runtimes ship different Unicode tables. A
    # same-length shadow keeps ECMAScript's context-sensitive final-sigma
    # behavior aligned with each finite mapping table.
    shadow = "".join(
        character
        if character == "\u03a3"
        else "A"
        if _is_cased(character, cased_additions, context_removals)
        else "\u0301"
        if _is_case_ignorable(
            character,
            cased_additions,
            case_ignorable_additions,
            context_removals,
        )
        else "!"
        for character in value
    ).lower()
    return "".join(
        shadow[index]
        if character == "\u03a3"
        else lowercase_mappings.get(character, character.lower())
        for index, character in enumerate(value)
    )


def _is_cased(
    character: str,
    cased_additions: frozenset[str],
    context_removals: frozenset[str],
) -> bool:
    if character in context_removals:
        return False
    if character in cased_additions:
        return True
    return ("A\u03a3" + character + "!").lower().startswith("a\u03c3")


def _is_case_ignorable(
    character: str,
    cased_additions: frozenset[str],
    case_ignorable_additions: frozenset[str],
    context_removals: frozenset[str],
) -> bool:
    if character in context_removals:
        return False
    if character in case_ignorable_additions:
        return True
    if _is_cased(character, cased_additions, context_removals):
        return False
    return ("A" + character + "\u03a3").lower().endswith("\u03c2")


def _validate_batch_envelope(
    payload: JsonObject,
    requested_ids: list[str],
) -> None:
    path = "GET /api/items/batch"
    if set(payload) != _BATCH_ENVELOPE_KEYS:
        raise ApiError(f"{path} returned an invalid batch envelope")

    data = payload["data"]
    missing = payload["missing"]
    if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
        raise ApiError(f"{path} returned invalid batch data")
    if not isinstance(missing, list) or not all(type(item_id) is str for item_id in missing):
        raise ApiError(f"{path} returned invalid missing IDs")

    found_ids: list[str] = []
    for item in data:
        item_id = item.get("id")
        if type(item_id) is not str or _ITEM_ID_PATTERN.fullmatch(item_id) is None:
            raise ApiError(f"{path} returned an item with an invalid ID")
        if item_id in found_ids:
            raise ApiError(f"{path} returned duplicate found item IDs")
        if item_id not in requested_ids:
            raise ApiError(f"{path} returned an item ID that was not requested")
        found_ids.append(item_id)

    missing_ids = list(missing)
    if len(set(missing_ids)) != len(missing_ids):
        raise ApiError(f"{path} returned duplicate missing IDs")
    if any(item_id not in requested_ids for item_id in missing_ids):
        raise ApiError(f"{path} returned a missing ID that was not requested")
    if set(found_ids).intersection(missing_ids):
        raise ApiError(f"{path} returned an ID in both partitions")

    expected_found_ids = [
        item_id for item_id in requested_ids if item_id not in missing_ids
    ]
    expected_missing_ids = [
        item_id for item_id in requested_ids if item_id not in found_ids
    ]
    if found_ids != expected_found_ids:
        raise ApiError(f"{path} returned found items in the wrong order or partition")
    if missing_ids != expected_missing_ids:
        raise ApiError(f"{path} returned missing IDs in the wrong order or partition")


def _validate_collection_envelope(
    payload: JsonObject,
    expected_query: JsonObject,
    normalized_queries: frozenset[str] | None,
) -> None:
    if set(payload) != _COLLECTION_KEYS:
        raise ApiError("GET /api/items returned an invalid collection envelope")

    data = payload["data"]
    pagination = payload["pagination"]
    query = payload["query"]
    if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
        raise ApiError("GET /api/items returned invalid collection data")
    if not isinstance(pagination, dict) or set(pagination) != _PAGINATION_KEYS:
        raise ApiError("GET /api/items returned invalid pagination metadata")
    if not isinstance(query, dict) or set(query) != _QUERY_KEYS:
        raise ApiError("GET /api/items returned invalid query metadata")
    for name, expected_value in expected_query.items():
        actual_value = query[name]
        if not _matches_query_value(
            name,
            actual_value,
            expected_value,
            normalized_queries,
        ):
            raise ApiError(
                "GET /api/items returned query metadata that does not match the request"
            )

    for name in _PAGINATION_KEYS:
        value = pagination[name]
        minimum = 1 if name in {"page", "limit"} else 0
        if type(value) is not int or value < minimum:
            raise ApiError(f"GET /api/items returned invalid pagination field '{name}'")

    page = pagination["page"]
    limit = pagination["limit"]
    total = pagination["total"]
    total_pages = pagination["totalPages"]
    if page != expected_query["page"] or limit != expected_query["limit"]:
        raise ApiError(
            "GET /api/items returned pagination metadata that does not match the request"
        )
    if total_pages != (total + limit - 1) // limit:
        raise ApiError("GET /api/items returned inconsistent pagination totals")
    expected_data_count = max(0, min(limit, total - ((page - 1) * limit)))
    if len(data) != expected_data_count:
        raise ApiError("GET /api/items returned data inconsistent with pagination metadata")


def _validate_item_envelope(
    payload: JsonObject,
    expected_id: str,
    encoded_id: str,
) -> None:
    path = f"GET /api/items/{encoded_id}"
    if "data" not in payload:
        raise ApiError(f"{path} returned an invalid item envelope")

    data = payload["data"]
    if not isinstance(data, dict) or not _ITEM_DATA_KEYS.issubset(data):
        raise ApiError(f"{path} returned invalid item data")
    if type(data["id"]) is not str or data["id"] != expected_id:
        raise ApiError(f"{path} returned item data with an unexpected id")
    if any(type(data[name]) is not str for name in ("name", "status", "category")):
        raise ApiError(f"{path} returned invalid item data")
    labels = data["labels"]
    if not isinstance(labels, list) or not all(type(label) is str for label in labels):
        raise ApiError(f"{path} returned invalid item labels")


def _validate_facet_envelope(
    payload: JsonObject,
    expected_filters: JsonObject,
    normalized_queries: frozenset[str] | None,
) -> None:
    path = "GET /api/items/facets"
    if not _FACET_ENVELOPE_KEYS.issubset(payload):
        raise ApiError(f"{path} returned an invalid facet envelope")

    data = payload["data"]
    filters = payload["filters"]
    if not isinstance(data, dict) or not _FACET_DATA_KEYS.issubset(data):
        raise ApiError(f"{path} returned invalid facet data")
    if not isinstance(filters, dict) or not _FACET_FILTER_KEYS.issubset(filters):
        raise ApiError(f"{path} returned invalid filter metadata")

    total = data["total"]
    by_label = data["byLabel"]
    if type(total) is not int or total < 0:
        raise ApiError(f"{path} returned invalid facet total")
    if not isinstance(by_label, dict):
        raise ApiError(f"{path} returned invalid label counts")
    if not all(
        type(name) is str and type(count) is int and count > 0
        for name, count in by_label.items()
    ):
        raise ApiError(f"{path} returned invalid label counts")
    counts = tuple(by_label.values())
    if any(count > total for count in counts) or sum(counts) < total:
        raise ApiError(f"{path} returned label counts inconsistent with the total")

    if "byCategory" in data:
        by_category = data["byCategory"]
        if not isinstance(by_category, dict) or not all(
            type(name) is str
            and bool(_ecmascript_trim(name))
            and type(count) is int
            and count > 0
            for name, count in by_category.items()
        ):
            raise ApiError(f"{path} returned invalid category counts")
        if sum(by_category.values()) != total:
            raise ApiError(f"{path} returned category counts inconsistent with the total")

        requested_category = expected_filters["category"]
        if (
            requested_category is not None
            and total > 0
            and by_category != {requested_category: total}
        ):
            raise ApiError(f"{path} returned category counts inconsistent with the request")

    requested_label = expected_filters["label"]
    if (
        requested_label is not None
        and total > 0
        and by_label.get(requested_label) != total
    ):
        raise ApiError(f"{path} returned label counts inconsistent with the request")

    for name, expected_value in expected_filters.items():
        if not _matches_query_value(
            name,
            filters[name],
            expected_value,
            normalized_queries,
        ):
            raise ApiError(
                f"{path} returned filter metadata that does not match the request"
            )


def _validate_summary_envelope(
    payload: JsonObject,
    expected_filters: JsonObject,
    normalized_queries: frozenset[str] | None,
) -> None:
    path = "GET /api/items/summary"
    if not _SUMMARY_ENVELOPE_KEYS.issubset(payload):
        raise ApiError(f"{path} returned an invalid summary envelope")

    data = payload["data"]
    insights = payload["insights"]
    if not isinstance(data, dict) or not _SUMMARY_DATA_KEYS.issubset(data):
        raise ApiError(f"{path} returned invalid summary data")
    if not isinstance(insights, dict) or not _SUMMARY_INSIGHT_KEYS.issubset(insights):
        raise ApiError(f"{path} returned invalid summary insights")

    matching_total = data["total"]
    global_total = insights["total"]
    insight_matching = insights["matching"]
    if type(matching_total) is not int or matching_total < 0:
        raise ApiError(f"{path} returned invalid matching total")
    if type(global_total) is not int or global_total < 0:
        raise ApiError(f"{path} returned invalid global total")
    if type(insight_matching) is not int or insight_matching < 0:
        raise ApiError(f"{path} returned invalid insight matching total")
    if insight_matching != matching_total or global_total < matching_total:
        raise ApiError(f"{path} returned inconsistent summary totals")
    if not any(expected_filters.values()) and global_total != matching_total:
        raise ApiError(f"{path} returned inconsistent unfiltered totals")

    grouping_maps = {
        "status counts": data["byStatus"],
        "category counts": data["byCategory"],
        "insight status counts": insights["byStatus"],
    }
    for name, counts in grouping_maps.items():
        if not isinstance(counts, dict) or not all(
            type(group) is str
            and bool(group)
            and type(count) is int
            and count >= 0
            for group, count in counts.items()
        ):
            raise ApiError(f"{path} returned invalid {name}")
        if sum(counts.values()) != matching_total:
            raise ApiError(f"{path} returned {name} inconsistent with the total")

    by_status = data["byStatus"]
    by_category = data["byCategory"]
    if insights["byStatus"] != by_status:
        raise ApiError(f"{path} returned inconsistent status insights")

    requested_status = expected_filters["status"]
    if (
        requested_status is not None
        and matching_total > 0
        and by_status != {requested_status: matching_total}
    ):
        raise ApiError(f"{path} returned status counts inconsistent with the request")
    requested_category = expected_filters["category"]
    if (
        requested_category is not None
        and matching_total > 0
        and by_category != {requested_category: matching_total}
    ):
        raise ApiError(f"{path} returned category counts inconsistent with the request")

    filters = insights["filters"]
    if not isinstance(filters, dict) or not _FACET_FILTER_KEYS.issubset(filters):
        raise ApiError(f"{path} returned invalid filter metadata")
    for name, expected_value in expected_filters.items():
        if not _matches_query_value(
            name,
            filters[name],
            expected_value,
            normalized_queries,
        ):
            raise ApiError(
                f"{path} returned filter metadata that does not match the request"
            )


def _matches_query_value(
    name: str,
    actual: Any,
    expected: Any,
    normalized_queries: frozenset[str] | None,
) -> bool:
    if name == "q" and normalized_queries is not None:
        return type(actual) is str and actual in normalized_queries
    return type(actual) is type(expected) and actual == expected

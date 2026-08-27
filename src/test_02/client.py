from dataclasses import dataclass
from typing import Any

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
_SORT_FIELDS = {"id", "name", "status"}
_SORT_ORDERS = {"asc", "desc"}
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
    "capability-discovery": {
        "method": "GET",
        "path": "/api/capabilities",
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


@dataclass
class ApiClient:
    base_url: str
    timeout: float = 5.0
    session: requests.Session | None = None

    def __post_init__(self) -> None:
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

    def _get(
        self,
        path: str,
        *,
        params: dict[str, QueryValue] | None = None,
    ) -> JsonObject:
        assert self.session is not None

        try:
            request_options: dict[str, Any] = {"timeout": self.timeout}
            if params is not None:
                request_options["params"] = params
            response = self.session.get(f"{self.base_url}{path}", **request_options)
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
        if not isinstance(actual, list) or len(actual) != len(required):
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
            option_group="facet",
        )
        if canonical_value is not None and not _ecmascript_trim(canonical_value):
            raise ApiError(f"invalid facet option '{name}': expected a non-blank string")
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


def _validate_facet_envelope(
    payload: JsonObject,
    expected_filters: JsonObject,
    normalized_queries: frozenset[str] | None,
) -> None:
    path = "GET /api/items/facets"
    if set(payload) != _FACET_ENVELOPE_KEYS:
        raise ApiError(f"{path} returned an invalid facet envelope")

    data = payload["data"]
    filters = payload["filters"]
    if not isinstance(data, dict) or set(data) != _FACET_DATA_KEYS:
        raise ApiError(f"{path} returned invalid facet data")
    if not isinstance(filters, dict) or set(filters) != _FACET_FILTER_KEYS:
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


def _matches_query_value(
    name: str,
    actual: Any,
    expected: Any,
    normalized_queries: frozenset[str] | None,
) -> bool:
    if name == "q" and normalized_queries is not None:
        return type(actual) is str and actual in normalized_queries
    return type(actual) is type(expected) and actual == expected

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
_SORT_FIELDS = {"id", "name", "status"}
_SORT_ORDERS = {"asc", "desc"}
_ECMASCRIPT_TRIM_CHARACTERS = (
    "\u0009\u000a\u000b\u000c\u000d\u0020\u00a0\u1680"
    "\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a"
    "\u2028\u2029\u202f\u205f\u3000\ufeff"
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
        params, expected_query = _discovery_query(
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
        _validate_collection_envelope(payload, expected_query)
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
) -> tuple[dict[str, QueryValue], JsonObject]:
    for name, value in (
        ("status", status),
        ("category", category),
        ("label", label),
        ("q", q),
    ):
        if value is not None and (
            not isinstance(value, str) or not _ecmascript_trim(value)
        ):
            raise ApiError(f"invalid discovery option '{name}': expected a non-blank string")

    status = str(status) if status is not None else None
    category = str(category) if category is not None else None
    label = str(label) if label is not None else None
    q = str(q) if q is not None else None
    sort = str(sort) if isinstance(sort, str) else sort
    order = str(order) if isinstance(order, str) else order

    if sort is not None and (not isinstance(sort, str) or sort not in _SORT_FIELDS):
        raise ApiError("invalid discovery option 'sort': expected id, name, or status")
    if order is not None and (
        not isinstance(order, str) or order not in _SORT_ORDERS
    ):
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
    return params, expected_query


def _ecmascript_trim(value: str) -> str:
    return value.strip(_ECMASCRIPT_TRIM_CHARACTERS)


def _validate_collection_envelope(payload: JsonObject, expected_query: JsonObject) -> None:
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
        if not _matches_query_value(name, actual_value, expected_value):
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


def _matches_query_value(name: str, actual: Any, expected: Any) -> bool:
    if name != "q" or not isinstance(expected, str) or expected.isascii():
        return type(actual) is type(expected) and actual == expected

    # The provider owns non-ASCII case normalization because its Unicode table
    # can be newer than Python's. Validate the JSON primitive and stable parts
    # of the normalized representation without predicting that table.
    return (
        type(actual) is str
        and bool(actual)
        and actual == _ecmascript_trim(actual)
        and not any("A" <= character <= "Z" for character in actual)
    )

from dataclasses import dataclass
from typing import Any

import requests

JsonObject = dict[str, Any]


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

    def _get(self, path: str) -> JsonObject:
        assert self.session is not None

        try:
            response = self.session.get(
                f"{self.base_url}{path}",
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as error:
            raise ApiError(f"GET {path} failed: {error}") from error
        except ValueError as error:
            raise ApiError(f"GET {path} returned invalid JSON") from error

        if not isinstance(payload, dict):
            raise ApiError(f"GET {path} returned a non-object JSON payload")
        return payload

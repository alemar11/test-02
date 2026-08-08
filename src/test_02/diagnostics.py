"""Deterministic, offline diagnostics for the test-02 client environment."""

from __future__ import annotations

import math
import sys
from importlib import metadata
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from requests import PreparedRequest, RequestException

PACKAGE_NAME = "test-02"
MINIMUM_PYTHON = (3, 13)
DEFAULT_BASE_URL = "http://127.0.0.1:3000"
DEFAULT_TIMEOUT = 5.0

JsonObject = dict[str, Any]


def _failure(code: str, message: str) -> JsonObject:
    return {"status": "fail", "code": code, "message": message}


def diagnose_base_url(value: str) -> JsonObject:
    """Validate and normalize an HTTP(S) base URL without contacting it."""
    if not isinstance(value, str) or not value or any(character.isspace() for character in value):
        return _failure("invalid_base_url", "base URL must be a non-empty URL without whitespace")

    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError:
        return _failure("invalid_base_url", "base URL is malformed")

    if parsed.scheme.lower() not in {"http", "https"} or not hostname:
        return _failure("invalid_base_url", "base URL must use http or https and include a host")
    if parsed.username is not None or parsed.password is not None:
        return _failure("invalid_base_url", "base URL must not include credentials")
    if parsed.query or parsed.fragment:
        return _failure("invalid_base_url", "base URL must not include a query or fragment")

    if parsed.netloc.endswith(":") or port == 0:
        return _failure("invalid_base_url", "base URL has an invalid host or port")

    try:
        prepared = PreparedRequest()
        prepared.prepare_url(value, None)
        if prepared.url is None:
            raise ValueError("prepared URL is unavailable")
        prepared_url = urlsplit(prepared.url)
    except (RequestException, ValueError):
        return _failure("invalid_base_url", "base URL is not supported by the HTTP client")

    path = prepared_url.path.rstrip("/")
    normalized = urlunsplit(
        (prepared_url.scheme, prepared_url.netloc, path, prepared_url.query, prepared_url.fragment)
    )
    return {"status": "pass", "value": normalized}


def diagnose_timeout(value: object) -> JsonObject:
    """Validate a finite, positive request timeout."""
    try:
        timeout = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return _failure("invalid_timeout", "timeout must be a finite positive number")

    if isinstance(value, bool) or not math.isfinite(timeout) or timeout <= 0:
        return _failure("invalid_timeout", "timeout must be a finite positive number")
    return {"status": "pass", "value": timeout}


def diagnose_python(version_info: tuple[int, int, int] | None = None) -> JsonObject:
    """Report whether the current Python runtime meets package requirements."""
    current = version_info or sys.version_info[:3]
    value = ".".join(str(part) for part in current)
    required = f">={MINIMUM_PYTHON[0]}.{MINIMUM_PYTHON[1]}"
    if current[:2] < MINIMUM_PYTHON:
        result = _failure("unsupported_python", f"Python {required} is required")
        result.update({"value": value, "required": required})
        return result
    return {"status": "pass", "value": value, "required": required}


def diagnose_package(package_version: str | None = None) -> JsonObject:
    """Report the installed client distribution identity."""
    try:
        version = package_version if package_version is not None else metadata.version(PACKAGE_NAME)
    except metadata.PackageNotFoundError:
        result = _failure("package_not_installed", f"{PACKAGE_NAME} package metadata is unavailable")
        result["name"] = PACKAGE_NAME
        return result
    return {"status": "pass", "name": PACKAGE_NAME, "version": version}


def environment_report(
    base_url: str = DEFAULT_BASE_URL,
    timeout: object = DEFAULT_TIMEOUT,
    *,
    python_version: tuple[int, int, int] | None = None,
    package_version: str | None = None,
) -> JsonObject:
    """Build a structured environment report using local information only."""
    diagnostics = {
        "base_url": diagnose_base_url(base_url),
        "timeout": diagnose_timeout(timeout),
        "python": diagnose_python(python_version),
        "package": diagnose_package(package_version),
    }
    return {
        "schema_version": 1,
        "ok": all(item["status"] == "pass" for item in diagnostics.values()),
        "diagnostics": diagnostics,
        "network_calls": 0,
    }

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from .config import AgentsSettings


class AgentsApiError(RuntimeError):
    pass


def call_agents_api(
    settings: AgentsSettings,
    method: str,
    path: str,
    *,
    query: str = "",
) -> dict[str, Any]:
    if not settings.secret:
        raise AgentsApiError("AGENTS_SECRET is not configured")

    url = f"{settings.api_base}{path}"
    if query:
        url = f"{url}?{query}"

    request = urllib.request.Request(url, method=method, headers={"X-Agents-Secret": settings.secret})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise AgentsApiError(f"HTTP {exc.code} {path}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise AgentsApiError(f"API unreachable at {settings.api_base}: {exc.reason}") from exc


def call_health(settings: AgentsSettings) -> dict[str, Any]:
    url = f"{settings.api_base}/health"
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise AgentsApiError(f"Health check failed: {exc}") from exc

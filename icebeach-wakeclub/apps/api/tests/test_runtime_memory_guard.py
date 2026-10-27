from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]


def test_api_process_recycles_and_receives_allocator_guard() -> None:
    dockerfile = (REPO_ROOT / "icebeach-wakeclub" / "Dockerfile").read_text(encoding="utf-8")
    compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "exec python -m uvicorn" in dockerfile
    assert "--limit-max-requests ${API_MAX_REQUESTS:-20000}" in dockerfile
    assert 'MALLOC_ARENA_MAX: "${MALLOC_ARENA_MAX:-2}"' in compose
    assert 'API_MAX_REQUESTS: "${API_MAX_REQUESTS:-20000}"' in compose
    assert "restart: unless-stopped" in compose

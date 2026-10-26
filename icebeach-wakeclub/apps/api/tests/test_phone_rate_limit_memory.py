from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from apps.api.app.models import LoginCodeRequest
from apps.api.app.services import phone_rate_limit


def _settings(*, attempts: int = 5) -> SimpleNamespace:
    return SimpleNamespace(
        auth_code_rate_limit_window_seconds=600,
        auth_code_rate_limit_max_attempts=attempts,
    )


def test_phone_rate_limit_bucket_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(phone_rate_limit, "_MAX_KEYS_PER_SCOPE", 128)

    settings = _settings()

    def submit(index: int) -> None:
        phone_rate_limit.enforce_phone_rate_limit(
            f"7{index:010d}",
            settings,
            scope="public-booking-request",
        )

    with ThreadPoolExecutor(max_workers=16) as executor:
        list(executor.map(submit, range(2_000)))

    bucket = phone_rate_limit._BUCKETS["public-booking-request"]
    assert len(bucket) == 128


def test_phone_rate_limit_still_rejects_repeated_number() -> None:
    settings = _settings(attempts=2)

    phone_rate_limit.enforce_phone_rate_limit(
        "+7 999 111-22-33",
        settings,
        scope="auth-request-code",
    )
    phone_rate_limit.enforce_phone_rate_limit(
        "8 (999) 111-22-33",
        settings,
        scope="auth-request-code",
    )

    with pytest.raises(HTTPException) as exc_info:
        phone_rate_limit.enforce_phone_rate_limit(
            "79991112233",
            settings,
            scope="auth-request-code",
        )

    assert exc_info.value.status_code == 429


def test_public_phone_input_has_a_safe_maximum_length() -> None:
    with pytest.raises(ValidationError):
        LoginCodeRequest(phone="7" * 65)

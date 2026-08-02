"""Tests for application configuration."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from apiguard.config import Settings


def test_settings_use_frozen_budget_defaults() -> None:
    settings = Settings()

    assert settings.openapi_fetch_timeout_seconds == 10
    assert settings.max_openapi_fetch_attempts == 2
    assert settings.llm_call_timeout_seconds == 45
    assert settings.max_llm_calls_per_preparation == 3
    assert settings.max_llm_transient_retries == 1
    assert settings.max_llm_format_repairs == 1
    assert settings.max_plan_steps == 3
    assert settings.max_http_sends_per_attempt == 3
    assert settings.target_http_request_timeout_seconds == 20
    assert settings.validation_attempt_budget_seconds == 90
    assert settings.max_openapi_document_bytes == 2 * 1024 * 1024
    assert settings.max_json_request_body_bytes == 256 * 1024
    assert settings.max_saved_response_body_bytes == 1024 * 1024
    assert settings.max_inline_report_body_bytes == 64 * 1024
    assert settings.max_model_output_bytes == 128 * 1024


def test_settings_allow_non_secret_environment_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APIGUARD_TARGET_HTTP_REQUEST_TIMEOUT_SECONDS", "30")

    settings = Settings()

    assert settings.target_http_request_timeout_seconds == 30


def test_settings_use_and_override_database_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert Settings().database_path == Path("data/apiguard.db")

    monkeypatch.setenv("APIGUARD_DATABASE_PATH", "test-data/apiguard.db")

    assert Settings().database_path == Path("test-data/apiguard.db")


@pytest.mark.parametrize(
    "environment_variable",
    [
        "APIGUARD_OPENAPI_FETCH_TIMEOUT_SECONDS",
        "APIGUARD_MAX_HTTP_SENDS_PER_ATTEMPT",
        "APIGUARD_MAX_MODEL_OUTPUT_BYTES",
    ],
)
@pytest.mark.parametrize("invalid_value", ["0", "-1"])
def test_settings_reject_non_positive_budgets(
    monkeypatch: pytest.MonkeyPatch,
    environment_variable: str,
    invalid_value: str,
) -> None:
    monkeypatch.setenv(environment_variable, invalid_value)

    with pytest.raises(ValidationError):
        Settings()

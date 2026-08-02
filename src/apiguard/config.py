"""Application configuration and frozen V0 safety budgets."""

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class Settings(BaseSettings):
    """Load non-secret settings from the environment with validated budgets."""

    model_config = SettingsConfigDict(env_prefix="APIGUARD_", extra="ignore")

    app_title: str = "ApiGuard"
    log_level: LogLevel = "INFO"
    database_path: Path = Path("data/apiguard.db")

    openapi_fetch_timeout_seconds: int = Field(default=10, gt=0)
    max_openapi_fetch_attempts: int = Field(default=2, gt=0)
    llm_call_timeout_seconds: int = Field(default=45, gt=0)
    max_llm_calls_per_preparation: int = Field(default=3, gt=0)
    max_llm_transient_retries: int = Field(default=1, gt=0)
    max_llm_format_repairs: int = Field(default=1, gt=0)
    max_plan_steps: int = Field(default=3, gt=0)
    max_http_sends_per_attempt: int = Field(default=3, gt=0)
    target_http_request_timeout_seconds: int = Field(default=20, gt=0)
    validation_attempt_budget_seconds: int = Field(default=90, gt=0)
    max_openapi_document_bytes: int = Field(default=2 * 1024 * 1024, gt=0)
    max_json_request_body_bytes: int = Field(default=256 * 1024, gt=0)
    max_saved_response_body_bytes: int = Field(default=1024 * 1024, gt=0)
    max_inline_report_body_bytes: int = Field(default=64 * 1024, gt=0)
    max_model_output_bytes: int = Field(default=128 * 1024, gt=0)

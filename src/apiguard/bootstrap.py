"""Minimal FastAPI application assembly for milestone M1-02."""

from fastapi import FastAPI

from apiguard.config import Settings
from apiguard.logging_config import configure_logging


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create the process shell without initializing external dependencies."""

    application_settings = settings if settings is not None else Settings()
    configure_logging(application_settings)

    application = FastAPI(title=application_settings.app_title)

    def health() -> dict[str, str]:
        """Report only that the process can serve HTTP requests."""

        return {"status": "ok"}

    application.add_api_route(
        "/health", health, methods=["GET"], include_in_schema=False
    )

    return application

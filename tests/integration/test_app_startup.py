"""Integration tests for the minimal FastAPI application shell."""

from typing import cast

from fastapi.testclient import TestClient
from httpx import Response

from apiguard.bootstrap import create_app
from apiguard.config import Settings


def test_health_reports_process_availability() -> None:
    client = TestClient(create_app(Settings()))

    response = cast(
        Response,
        client.get("/health"),  # pyright: ignore[reportUnknownMemberType]
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_application_title_is_apiguard() -> None:
    app = create_app(Settings())

    assert app.title == "ApiGuard"

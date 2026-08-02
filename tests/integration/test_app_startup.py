"""Integration tests for the minimal FastAPI application shell."""

from pathlib import Path
from typing import cast

from fastapi.testclient import TestClient
from httpx import Response

from apiguard.bootstrap import create_app
from apiguard.config import Settings


def test_health_reports_process_availability(tmp_path: Path) -> None:
    database_path = tmp_path / "unavailable-parent" / "apiguard.db"
    client = TestClient(create_app(Settings(database_path=database_path)))

    response = cast(
        Response,
        client.get("/health"),  # pyright: ignore[reportUnknownMemberType]
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert not database_path.exists()


def test_application_title_is_apiguard(tmp_path: Path) -> None:
    app = create_app(Settings(database_path=tmp_path / "apiguard.db"))

    assert app.title == "ApiGuard"

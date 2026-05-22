from __future__ import annotations

import pytest

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("multipart")

from fastapi.testclient import TestClient

from main import create_app


def test_root_health_returns_ok(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("STRUCTFORGE_DB_PATH", str(tmp_path / "structforge.db"))
    app = create_app()
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_unknown_job_returns_404(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("STRUCTFORGE_DB_PATH", str(tmp_path / "structforge.db"))
    app = create_app()
    client = TestClient(app)

    response = client.get("/api/v1/analyze/missing-job")

    assert response.status_code == 404


def test_non_video_upload_returns_400(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("STRUCTFORGE_DB_PATH", str(tmp_path / "structforge.db"))
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/api/v1/analyze",
        files={"video": ("notes.txt", b"not a video", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Only video files are supported"

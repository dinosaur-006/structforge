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


def test_capabilities_expose_readiness_without_credentials(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("STRUCTFORGE_DB_PATH", str(tmp_path / "structforge.db"))
    monkeypatch.setenv("STRUCTFORGE_DOUBAO_LLM_ENDPOINT", "https://example.invalid/llm")
    monkeypatch.setenv("STRUCTFORGE_DOUBAO_LLM_API_KEY", "do-not-return-this-key")
    monkeypatch.delenv("STRUCTFORGE_DOUBAO_VISION_ENDPOINT", raising=False)
    monkeypatch.delenv("STRUCTFORGE_DOUBAO_VISION_API_KEY", raising=False)
    monkeypatch.setenv("STRUCTFORGE_CELERY_TASK_ALWAYS_EAGER", "true")
    client = TestClient(create_app())

    response = client.get("/api/v1/capabilities")

    assert response.status_code == 200
    payload = response.json()
    assert payload["llm"]["state"] == "configured"
    assert payload["llm"]["detail"] == "已提供 LLM 配置；首次真实生成时验证授权可用性"
    assert payload["vision"]["state"] == "configured"
    assert "多模态" in payload["vision"]["detail"]
    assert payload["taskExecution"]["state"] == "inline"
    assert "do-not-return-this-key" not in response.text

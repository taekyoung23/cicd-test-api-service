import os

os.environ["APP_ENV"] = "ci"
os.environ["INPUT_BUCKET"] = "ci-placeholder-input-bucket"
os.environ["RESULT_BUCKET"] = "ci-placeholder-result-bucket"

from fastapi.testclient import TestClient

from app.main import app


def test_api_health() -> None:
    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"

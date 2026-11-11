from fastapi.testclient import TestClient
from jobsift.main import app

client = TestClient(app)


def test_health_endpoint_reports_liveness() -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "JobSift API",
        "version": "0.1.0",
    }


def test_health_endpoint_is_in_openapi_contract() -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/api/v1/health" in response.json()["paths"]

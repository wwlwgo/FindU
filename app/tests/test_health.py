from fastapi.testclient import TestClient

from app.main import create_app


def client() -> TestClient:
    return TestClient(create_app(), raise_server_exceptions=False)


def test_health_check_returns_ok() -> None:
    response = client().get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["x-request-id"]


def test_api_health_check_returns_ok() -> None:
    response = client().get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_unknown_api_route_returns_error_envelope() -> None:
    response = client().get("/api/v1/not-found")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
    assert response.json()["error"]["requestId"]


def test_validation_errors_return_error_envelope() -> None:
    response = client().get("/api/v1/health?verbose=not-a-boolean")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert response.json()["error"]["requestId"]

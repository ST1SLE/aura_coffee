from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"


def test_health_includes_yukassa_backend(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert "yukassa_backend" in response.json()

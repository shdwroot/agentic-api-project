from conftest import load_example_request
from fastapi.testclient import TestClient

from agentic_api.main import app

client = TestClient(app)


def test_health_and_capabilities():
    assert client.get("/health").json() == {"status": "ok"}
    response = client.get("/v1/capabilities")
    assert response.status_code == 200
    assert "pytest" in response.json()["artifact_types"]


def test_generate_and_fetch_round_trip():
    response = client.post(
        "/v1/generations",
        json=load_example_request().model_dump(mode="json"),
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["scenarios"]
    fetched = client.get(f"/v1/generations/{payload['run_id']}")
    assert fetched.status_code == 200
    assert fetched.json()["run_id"] == payload["run_id"]


def test_generate_rejects_empty_context():
    response = client.post("/v1/generations", json={})

    assert response.status_code == 422


def test_unknown_run_is_404():
    assert client.get("/v1/generations/not-a-run").status_code == 404

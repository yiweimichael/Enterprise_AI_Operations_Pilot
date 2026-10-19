from starlette.testclient import TestClient

from server import mcp


def test_healthz_returns_ok():
    client = TestClient(mcp.streamable_http_app())

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

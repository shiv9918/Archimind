import io
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

FIXTURE = Path(__file__).parent / "fixtures" / "sample_repo"


def _zip_fixture() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for path in FIXTURE.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(FIXTURE.parent))
    return buf.getvalue()


def test_zip_import_runs_full_pipeline_end_to_end():
    client = TestClient(app)
    zip_bytes = _zip_fixture()

    response = client.post(
        "/api/repos/import/zip",
        files={"file": ("sample_repo.zip", zip_bytes, "application/zip")},
    )
    assert response.status_code == 201, response.text
    repo_id = response.json()["repository"]["id"]

    try:
        dashboard = client.get(f"/api/repos/{repo_id}/dashboard").json()
        assert dashboard["ready"] is True, dashboard
        assert dashboard["overview"]["languages"].get("Python", 0) > 0
        assert 0 <= dashboard["health"]["documentation_score"] <= 100
        assert dashboard["architecture"]["primary_pattern"]
        assert dashboard["recommendations"]

        graph = client.get(f"/api/repos/{repo_id}/graph").json()
        assert len(graph["nodes"]) > 0
        assert len(graph["edges"]) > 0

        stats = client.get(f"/api/repos/{repo_id}/graph/stats").json()
        assert stats["total_nodes"] > 0

        # No XAI_API_KEY configured in the test environment -- must fail gracefully, not crash.
        chat_response = client.post(f"/api/repos/{repo_id}/chat", json={"message": "What does UserService do?"})
        assert chat_response.status_code == 400
        assert "XAI_API_KEY" in chat_response.json()["detail"]
    finally:
        client.delete(f"/api/repos/{repo_id}")


def test_zip_import_rejects_non_zip():
    client = TestClient(app)
    response = client.post(
        "/api/repos/import/zip",
        files={"file": ("not_a_zip.zip", b"not a zip file", "application/zip")},
    )
    assert response.status_code == 400


def test_github_import_rejects_non_github_url():
    client = TestClient(app)
    response = client.post("/api/repos/import/github", json={"url": "https://evil.example.com/repo.git"})
    assert response.status_code == 400


def test_github_import_rejects_local_file_scheme():
    client = TestClient(app)
    response = client.post("/api/repos/import/github", json={"url": "file:///etc/passwd"})
    assert response.status_code == 400


def test_dashboard_for_unknown_repo_404s():
    client = TestClient(app)
    response = client.get("/api/repos/does-not-exist/dashboard")
    assert response.status_code == 404


def test_health_endpoint():
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

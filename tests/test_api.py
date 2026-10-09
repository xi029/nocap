from fastapi.testclient import TestClient

from nocap.app import create_app
from nocap.config import Settings


def client(tmp_path):
    return TestClient(create_app(Settings(data_dir=tmp_path, provider="demo")))


def test_full_flow_and_replay_preserve_original(tmp_path):
    c = client(tmp_path)
    assert c.get("/").status_code == 200
    assert c.get("/health").json()["status"] == "ok"
    c.post("/api/samples")
    result = c.post("/api/query", json={"question": "How do I request a refund?"}).json()
    assert result["action"] == "answer"
    assert result["claims"] and not result["generator_called"]
    assert result["input_state"]["excerpts"][0]["text"] == result["evidence"][0]["text"]
    replay = c.post(
        f"/api/traces/{result['id']}/replay",
        json={"policy": {"support_threshold": 0.95, "conflict_threshold": 0.35}},
    ).json()
    assert replay["action"] == "retrieve_more" and replay["inference_calls"] == 0
    assert c.get(f"/api/traces/{result['id']}").json()["action"] == "answer"
    export = c.get(f"/api/traces/{result['id']}/export")
    assert export.json() == result
    assert "attachment" in export.headers["content-disposition"]


def test_no_evidence_never_calls_generator(tmp_path):
    c = client(tmp_path)
    result = c.post(
        "/api/query",
        json={"question": "Who won lunar chess?", "provider": "ollama", "generator": "ollama"},
    ).json()
    assert result["action"] == "abstain"
    assert not result["generator_called"]
    assert result["decision"]["model"] == "skipped-no-evidence"


def test_conflict_blocks_generation(tmp_path):
    c = client(tmp_path)
    c.post("/api/samples/conflict")
    result = c.post(
        "/api/query", json={"question": "How many days to request a refund?", "generator": "ollama"}
    ).json()
    assert result["action"] == "review_conflict"
    assert not result["claims"] and not result["generator_called"]


def test_missing_detail_routes_to_more_evidence(tmp_path):
    c = client(tmp_path)
    c.post("/api/samples")
    result = c.post("/api/query", json={"question": "What is the exact team plan pricing?"}).json()
    assert result["action"] == "retrieve_more"


def test_upload_validation_and_deduplication(tmp_path):
    c = client(tmp_path)
    for _ in range(2):
        result = c.post(
            "/api/upload", files={"file": ("../../notes.md", b"Local notes on refunds.")}
        )
        assert result.status_code == 201 and result.json()["name"] == "notes.md"
    assert len(c.get("/api/documents").json()) == 1
    assert c.post("/api/upload", files={"file": ("notes.pdf", b"fake")}).status_code == 422
    assert c.post("/api/upload", files={"file": ("notes.md", b"\xff")}).status_code == 422
    assert c.post("/api/upload", files={"file": ("notes.md", b"x" * 200_001)}).status_code == 413
    assert c.post("/api/upload", files={"file": ("notes.md", b"   ")}).status_code == 422


def test_origin_keys_and_input_validation(tmp_path):
    c = client(tmp_path)
    assert c.post("/api/samples", headers={"origin": "https://example.com"}).status_code == 403
    assert c.post("/api/samples", headers={"origin": "http://testserver"}).status_code == 200
    assert c.get("/health", headers={"host": "evil.example"}).status_code == 400
    assert "api_key" not in c.get("/api/config").text
    assert c.post("/api/query", json={"question": "   "}).status_code == 422
    assert (
        c.post(
            "/api/query", json={"question": "A normal question", "provider": "bogus"}
        ).status_code
        == 422
    )
    assert c.get("/api/traces/missing").status_code == 404


def test_document_deletion_keeps_saved_trace(tmp_path):
    c = client(tmp_path)
    document = c.post(
        "/api/documents", json={"name": "note.md", "text": "Refunds take 5 days."}
    ).json()
    trace = c.post("/api/query", json={"question": "How many days for refunds?"}).json()
    c.delete("/api/documents/" + document["id"])
    assert c.get("/api/documents").json() == []
    assert c.get("/api/traces/" + trace["id"]).json()["evidence"]

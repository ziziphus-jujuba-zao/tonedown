import json

import pytest
from fastapi.testclient import TestClient
from tonedown_server.main import create_app
from tonedown_server.settings import Settings


@pytest.fixture
def client(tmp_path):
    settings = Settings(
        backend="lexicon",
        api_keys={"k-a": "tenant-a"},
        open_access=False,
        feedback_path=str(tmp_path / "feedback.jsonl"),
        tenants={"tenant-a": {"policy": "strict"}},
    )
    return TestClient(create_app(settings)), settings


def test_requires_key(client):
    c, _ = client
    assert c.post("/v1/grade", json={"items": [{"text": "hi"}]}).status_code == 401
    assert c.post("/v1/grade", json={"items": [{"text": "hi"}]}, headers={"X-API-Key": "nope"}).status_code == 401


def test_grade_uses_tenant_policy_and_lexicon(client):
    c, _ = client
    r = c.post(
        "/v1/grade",
        json={"items": [{"id": "a", "text": "楼主nmsl"}, {"id": "b", "text": "这集节奏太好了"}]},
        headers={"X-API-Key": "k-a"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["policy"] == "strict" and body["backend"] == "lexicon"
    a, b = body["results"]
    assert a["id"] == "a" and a["action"] == "block" and a["lang"] == "zh"
    assert b["action"] == "pass"
    assert body["usage"]["items"] == 2


def test_request_policy_overrides_tenant(client):
    c, _ = client
    r = c.post(
        "/v1/grade",
        json={"items": [{"text": "楼主nmsl"}], "policy": "relaxed"},
        headers={"Authorization": "Bearer k-a"},
    )
    assert r.status_code == 200 and r.json()["results"][0]["action"] != "block"
    assert (
        c.post("/v1/grade", json={"items": [{"text": "x"}], "policy": "nope"}, headers={"X-API-Key": "k-a"}).status_code
        == 400
    )


def test_policies_and_health(client):
    c, _ = client
    assert {p["name"] for p in c.get("/v1/policies").json()["policies"]} >= {"balanced", "strict", "relaxed"}
    assert c.get("/healthz").json()["status"] == "ok"


def test_feedback_is_appended(client):
    c, settings = client
    r = c.post(
        "/v1/feedback",
        json={"text_hash": "abc", "human_action": "pass", "note": "false positive"},
        headers={"X-API-Key": "k-a"},
    )
    assert r.status_code == 202
    lines = open(settings.feedback_path, encoding="utf-8").read().splitlines()
    assert len(lines) == 1 and json.loads(lines[0])["tenant"] == "tenant-a"

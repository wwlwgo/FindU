from typing import Any

from fastapi.testclient import TestClient


def create_participant(client: TestClient, name: str = "Alice") -> dict[str, Any]:
    response = client.post("/api/v1/participants", json={"activityId": "act_demo", "displayName": name})
    assert response.status_code == 201
    return response.json()


def auth_headers(created: dict[str, Any]) -> dict[str, str]:
    return {"Authorization": f"Bearer {created['accessToken']}"}


def test_create_participant_and_read_empty_profile(client: TestClient) -> None:
    created = create_participant(client)
    participant_id = created["participant"]["id"]
    response = client.get(f"/api/v1/participants/{participant_id}/profile", headers=auth_headers(created))
    assert response.status_code == 200
    assert response.json()["transcriptStatus"] == "pending"
    assert response.json()["items"] == []


def test_profile_draft_and_confirmation_filter_private_fields(client: TestClient) -> None:
    created = create_participant(client)
    participant_id = created["participant"]["id"]
    headers = auth_headers(created)
    draft_response = client.post(
        f"/api/v1/participants/{participant_id}/profile-draft",
        headers=headers,
        json={"transcript": "我擅长前端交互，希望找后端伙伴，也担心项目范围太大。"},
    )
    assert draft_response.status_code == 200
    items = draft_response.json()["draft"]["items"]
    items[0]["confirmed"] = True
    items[0]["visibility"] = "public"
    items[-1]["confirmed"] = True
    items[-1]["visibility"] = "private"
    save_response = client.put(
        f"/api/v1/participants/{participant_id}/profile",
        headers=headers,
        json={"displayName": "Alice", "items": items},
    )
    assert save_response.status_code == 200
    assert "项目范围" not in save_response.json()["broadcast"]
    profile_response = client.get(f"/api/v1/participants/{participant_id}/profile", headers=headers)
    assert profile_response.status_code == 200
    assert {item["visibility"] for item in profile_response.json()["items"]} == {"public", "private"}


def test_participant_token_cannot_read_another_profile(client: TestClient) -> None:
    alice = create_participant(client, "Alice")
    bob = create_participant(client, "Bob")
    bob_id = bob["participant"]["id"]
    response = client.get(f"/api/v1/participants/{bob_id}/profile", headers=auth_headers(alice))
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_invalid_token_uses_error_envelope(client: TestClient) -> None:
    response = client.get("/api/v1/participants/p_missing/profile", headers={"Authorization": "Bearer not-a-valid-token"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"

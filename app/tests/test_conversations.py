from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.errors import ApiError
from app.models import Agent, AgentDecision, Conversation, Message, Participant
from app.services.conversations import AgentAction, apply_action, create_contact


def _create_confirmed_participant(client: TestClient, name: str) -> dict[str, Any]:
    created = client.post(
        "/api/v1/participants", json={"activityId": "act_demo", "displayName": name}
    ).json()
    participant_id = created["participant"]["id"]
    headers = {"Authorization": f"Bearer {created['accessToken']}"}
    item = {
        "id": f"offer_{name.lower()}",
        "kind": "offer",
        "text": f"{name} can help with prototype work",
        "evidence": None,
        "confirmed": True,
        "visibility": "public",
    }
    response = client.put(
        f"/api/v1/participants/{participant_id}/profile",
        headers=headers,
        json={"displayName": name, "items": [item]},
    )
    assert response.status_code == 200
    return created


def _agent_for(client: TestClient, participant_id: str) -> Agent:
    with client.app.state.database.session_factory() as db:
        agent = db.scalar(select(Agent).where(Agent.participant_id == participant_id))
        assert agent is not None
        db.expunge(agent)
        return agent


def _contact(recipient_id: str) -> AgentAction:
    return AgentAction(
        action="CONTACT",
        recipient_agent_id=recipient_id,
        public_message="Would it be useful to exchange implementation and product ideas?",
        decision_before="uncertain",
        decision_after="uncertain",
        missing_information=["collaboration preference"],
        new_information=[],
        private_reason="The owner values an early product discussion.",
    )


def _response(action: str, recipient_id: str) -> AgentAction:
    return AgentAction(
        action=action,
        recipient_agent_id=recipient_id,
        public_message="I can discuss the prototype and how to validate the scope.",
        decision_before="uncertain",
        decision_after="interested" if action == "ACCEPT" else "uncertain",
        missing_information=[],
        new_information=["willing to discuss scope"],
        private_reason="This is private owner-side reasoning.",
    )


def test_contact_is_atomic_and_private_reason_is_not_a_message(client: TestClient) -> None:
    alice = _create_confirmed_participant(client, "Alice")
    bob = _create_confirmed_participant(client, "Bob")
    alice_agent = _agent_for(client, alice["participant"]["id"])
    bob_agent = _agent_for(client, bob["participant"]["id"])
    with client.app.state.database.session_factory() as db:
        conversation = create_contact(
            db,
            activity_id="act_demo",
            initiator=db.get(Agent, alice_agent.id),
            recipient=db.get(Agent, bob_agent.id),
            action=_contact(bob_agent.id),
        )
        assert conversation.status == "PENDING_RESPONSE"
        assert conversation.next_actor_agent_id == bob_agent.id
    with client.app.state.database.session_factory() as db:
        alice_row = db.get(Agent, alice_agent.id)
        bob_row = db.get(Participant, bob["participant"]["id"])
        message = db.scalar(select(Message).where(Message.conversation_id == conversation.id))
        decision = db.scalar(select(AgentDecision).where(AgentDecision.conversation_id == conversation.id))
        assert alice_row is not None and alice_row.outbound_contact_count == 1
        assert bob_row is not None and bob_row.inbound_contact_count == 1
        assert message is not None and "private" not in message.public_message.lower()
        assert decision is not None and decision.private_reason == "The owner values an early product discussion."


def test_duplicate_pair_and_busy_target_are_rejected(client: TestClient) -> None:
    alice = _create_confirmed_participant(client, "Alice")
    bob = _create_confirmed_participant(client, "Bob")
    alice_agent = _agent_for(client, alice["participant"]["id"])
    bob_agent = _agent_for(client, bob["participant"]["id"])
    with client.app.state.database.session_factory() as db:
        create_contact(
            db,
            activity_id="act_demo",
            initiator=db.get(Agent, alice_agent.id),
            recipient=db.get(Agent, bob_agent.id),
            action=_contact(bob_agent.id),
        )
    with client.app.state.database.session_factory() as db:
        with pytest.raises(ApiError, match="already exists") as duplicate:
            create_contact(
                db,
                activity_id="act_demo",
                initiator=db.get(Agent, alice_agent.id),
                recipient=db.get(Agent, bob_agent.id),
                action=_contact(bob_agent.id),
            )
        assert duplicate.value.code == "INVALID_STATE"
        target = db.get(Participant, bob["participant"]["id"])
        assert target is not None
        target.max_inbound_contacts = target.inbound_contact_count
        db.commit()
    carol = _create_confirmed_participant(client, "Carol")
    carol_agent = _agent_for(client, carol["participant"]["id"])
    with client.app.state.database.session_factory() as db:
        with pytest.raises(ApiError) as busy:
            create_contact(
                db,
                activity_id="act_demo",
                initiator=db.get(Agent, carol_agent.id),
                recipient=db.get(Agent, bob_agent.id),
                action=_contact(bob_agent.id),
            )
        assert busy.value.code == "TARGET_BUSY"


def test_three_completed_rounds_cannot_start_a_fourth(client: TestClient) -> None:
    alice = _create_confirmed_participant(client, "Alice")
    bob = _create_confirmed_participant(client, "Bob")
    alice_agent = _agent_for(client, alice["participant"]["id"])
    bob_agent = _agent_for(client, bob["participant"]["id"])
    with client.app.state.database.session_factory() as db:
        conversation = create_contact(
            db,
            activity_id="act_demo",
            initiator=db.get(Agent, alice_agent.id),
            recipient=db.get(Agent, bob_agent.id),
            action=_contact(bob_agent.id),
        )
        conversation = apply_action(
            db, conversation=conversation, actor=db.get(Agent, bob_agent.id), action=_response("ANSWER", alice_agent.id)
        )
        conversation = apply_action(
            db, conversation=conversation, actor=db.get(Agent, bob_agent.id), action=_response("QUESTION", alice_agent.id)
        )
        conversation = apply_action(
            db, conversation=conversation, actor=db.get(Agent, alice_agent.id), action=_response("ANSWER", bob_agent.id)
        )
        conversation = apply_action(
            db, conversation=conversation, actor=db.get(Agent, alice_agent.id), action=_response("QUESTION", bob_agent.id)
        )
        conversation = apply_action(
            db, conversation=conversation, actor=db.get(Agent, bob_agent.id), action=_response("ANSWER", alice_agent.id)
        )
        assert conversation.turn_count == 3
        with pytest.raises(ApiError) as turn_limit:
            apply_action(
                db, conversation=conversation, actor=db.get(Agent, bob_agent.id), action=_response("QUESTION", alice_agent.id)
            )
        assert turn_limit.value.code == "TURN_LIMIT_REACHED"


def test_humans_confirm_mutual_agent_intent_through_api(client: TestClient) -> None:
    alice = _create_confirmed_participant(client, "Alice")
    bob = _create_confirmed_participant(client, "Bob")
    alice_agent = _agent_for(client, alice["participant"]["id"])
    bob_agent = _agent_for(client, bob["participant"]["id"])
    with client.app.state.database.session_factory() as db:
        conversation = create_contact(
            db,
            activity_id="act_demo",
            initiator=db.get(Agent, alice_agent.id),
            recipient=db.get(Agent, bob_agent.id),
            action=_contact(bob_agent.id),
        )
        conversation = apply_action(
            db, conversation=conversation, actor=db.get(Agent, bob_agent.id), action=_response("ANSWER", alice_agent.id)
        )
        conversation = apply_action(
            db, conversation=conversation, actor=db.get(Agent, bob_agent.id), action=_response("PROPOSE", alice_agent.id)
        )
        conversation = apply_action(
            db, conversation=conversation, actor=db.get(Agent, alice_agent.id), action=_response("ACCEPT", bob_agent.id)
        )
        assert conversation.status == "MUTUAL_AGENT_INTENT"

    alice_headers = {"Authorization": f"Bearer {alice['accessToken']}"}
    bob_headers = {"Authorization": f"Bearer {bob['accessToken']}"}
    view = client.get(f"/api/v1/conversations/{conversation.id}", headers=alice_headers)
    assert view.status_code == 200
    assert "privateReason" not in view.text
    assert len(view.json()["messages"]) == 4
    first_confirmation = client.post(
        f"/api/v1/conversations/{conversation.id}/human-confirmations",
        headers=alice_headers,
        json={"decision": "ACCEPT"},
    )
    assert first_confirmation.status_code == 200
    assert first_confirmation.json()["status"] == "MUTUAL_AGENT_INTENT"
    second_confirmation = client.post(
        f"/api/v1/conversations/{conversation.id}/human-confirmations",
        headers=bob_headers,
        json={"decision": "ACCEPT"},
    )
    assert second_confirmation.status_code == 200
    assert second_confirmation.json()["status"] == "CONNECTED"
    intents = client.get(
        f"/api/v1/participants/{alice['participant']['id']}/candidate-intents", headers=alice_headers
    )
    assert intents.status_code == 200
    assert intents.json()["items"][0]["status"] == "connected"


def test_replay_run_emits_a_three_round_mutual_intent(client: TestClient) -> None:
    alice = _create_confirmed_participant(client, "Alice")
    headers = {"Authorization": f"Bearer {alice['accessToken']}"}
    broadcasts = client.get("/api/v1/activities/act_demo/broadcasts", headers=headers)
    assert broadcasts.status_code == 200
    assert any(item["agentId"] == "agent_bob" for item in broadcasts.json()["items"])
    for _ in range(6):
        response = client.post(
            "/api/v1/activities/act_demo/runs",
            headers=headers,
            json={"mode": "replay", "replayTrackId": "alice_bob_mutual_intent", "maxSteps": 1},
        )
        assert response.status_code == 202
    conversations = client.get("/api/v1/me/conversations", headers=headers)
    assert conversations.status_code == 200
    view = conversations.json()[0]
    assert view["status"] == "MUTUAL_AGENT_INTENT"
    assert view["turnCount"] == 3
    assert len(view["messages"]) == 6
    event_payloads = [event.data for event in client.app.state.event_bus._events]
    assert all("privateReason" not in str(payload) for payload in event_payloads)
    assert any("newInformation" in str(payload) and payload["newInformation"] for payload in event_payloads)

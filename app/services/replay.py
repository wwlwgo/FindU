import json
from pathlib import Path
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.models import Agent, Conversation, Message
from app.services.conversations import AgentAction, _record_action, create_contact


def _track_path(track_id: str) -> Path:
    if not track_id.replace("_", "").isalnum():
        raise ApiError("VALIDATION_ERROR", "Invalid replay track", 422)
    return Path(__file__).resolve().parents[2] / "mock" / "replay_tracks" / f"{track_id}.json"


def load_track(track_id: str) -> dict[str, object]:
    path = _track_path(track_id)
    if not path.exists():
        raise ApiError("NOT_FOUND", "Replay track not found", 404)
    return json.loads(path.read_text(encoding="utf-8"))


def run_next_replay_step(db: Session, *, activity_id: str, actor: Agent, track_id: str) -> tuple[Conversation, AgentAction]:
    track = load_track(track_id)
    participants = track.get("participants", [])
    self_alias = "agent_alice" if "agent_alice" in participants else actor.id
    counterpart_id = track.get("counterpartAgentId")
    if counterpart_id is None:
        counterpart_id = next((item for item in participants if item != self_alias), None)
    counterpart = db.get(Agent, counterpart_id) if counterpart_id else None
    if counterpart is None:
        raise ApiError("PROVIDER_UNAVAILABLE", "Replay counterpart is unavailable", 503)
    conversation = db.scalar(select(Conversation).where(
        Conversation.activity_id == activity_id,
        Conversation.agent_pair_key == ":".join(sorted((actor.id, counterpart.id))),
    ))
    events = track["events"]
    event_index = 0 if conversation is None else db.scalar(
        select(func.count()).select_from(Message).where(Message.conversation_id == conversation.id)
    )
    if event_index >= len(events):
        raise ApiError("INVALID_STATE", "Replay track is complete", 409)
    event = events[event_index]
    event_actor = actor if event.get("actor") == "self" or event.get("senderAgentId") == self_alias else counterpart
    recipient = counterpart if event_actor.id == actor.id else actor
    action = AgentAction(
        action=event["action"], recipient_agent_id=recipient.id, public_message=event["publicMessage"],
        decision_before=event["decisionBefore"], decision_after=event["decisionAfter"],
        missing_information=event["missingInformation"], new_information=event["newInformation"],
        private_reason="Replay provider decision trace",
    )
    if conversation is None:
        if event_actor.id != actor.id or action.action != "CONTACT":
            raise ApiError("INVALID_STATE", "Replay track must begin with this agent contacting", 409)
        # Reads above opened a SQLite transaction; create_contact upgrades through BEGIN IMMEDIATE.
        db.rollback()
        db.refresh(actor)
        db.refresh(counterpart)
        conversation = create_contact(db, activity_id=activity_id, initiator=actor, recipient=counterpart, action=action)
        return conversation, action

    round_number = event_index // 2 + 1
    _record_action(db, conversation, event_actor, action, round_number)
    if action.action == "DECLINE":
        conversation.turn_count = round_number
        conversation.status = "DECLINED"
        conversation.next_actor_agent_id = None
    elif action.action == "ACCEPT":
        conversation.turn_count = round_number
        conversation.status = "MUTUAL_AGENT_INTENT"
        conversation.next_actor_agent_id = None
    elif event_index % 2 == 1:
        conversation.turn_count = round_number
        conversation.status = "ACTIVE"
        conversation.next_actor_agent_id = actor.id
    else:
        conversation.status = "PROPOSED" if action.action == "PROPOSE" else "PENDING_RESPONSE"
        conversation.next_actor_agent_id = recipient.id
    db.commit()
    db.refresh(conversation)
    return conversation, action

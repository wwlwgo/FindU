from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.models import Agent, AgentDecision, Conversation, Message, Participant, Profile

INITIATING_ACTIONS = {"CONTACT", "QUESTION", "CLARIFY", "PROPOSE"}
RESPONDING_ACTIONS = {"ANSWER", "CLARIFY", "ACCEPT", "DECLINE"}
TERMINAL_STATUSES = {"DECLINED", "EXPIRED", "HUMAN_REJECTED", "CONNECTED"}


@dataclass(frozen=True)
class AgentAction:
    action: str
    recipient_agent_id: str
    public_message: str
    decision_before: str
    decision_after: str
    missing_information: list[str]
    new_information: list[str]
    private_reason: str


def _pair_key(first_agent_id: str, second_agent_id: str) -> str:
    return ":".join(sorted((first_agent_id, second_agent_id)))


def _require_confirmed_profile(db: Session, participant_id: str) -> None:
    profile = db.get(Profile, participant_id)
    if profile is None or profile.transcript_status != "confirmed":
        raise ApiError("PROFILE_NOT_CONFIRMED", "Profile must be confirmed before contacting", 422)


def _record_action(db: Session, conversation: Conversation, actor: Agent, action: AgentAction, round_number: int) -> None:
    db.add(
        Message(
            id=f"msg_{uuid4().hex}",
            conversation_id=conversation.id,
            sender_agent_id=actor.id,
            action=action.action,
            public_message=action.public_message,
            round_number=round_number,
        )
    )
    db.add(
        AgentDecision(
            id=f"dec_{uuid4().hex}",
            agent_id=actor.id,
            conversation_id=conversation.id,
            decision_before=action.decision_before,
            decision_after=action.decision_after,
            missing_information_json=action.missing_information,
            new_information_json=action.new_information,
            private_reason=action.private_reason,
        )
    )


def create_contact(
    db: Session, *, activity_id: str, initiator: Agent, recipient: Agent, action: AgentAction
) -> Conversation:
    if action.action != "CONTACT" or action.recipient_agent_id != recipient.id:
        raise ApiError("INVALID_ACTION", "A new conversation must begin with CONTACT", 409)
    if initiator.id == recipient.id:
        raise ApiError("INVALID_ACTION", "An agent cannot contact itself", 409)
    try:
        # SQLite has no row-level locks. Acquiring its write lock before checking counters
        # keeps the pair check and the increments in one serializable transaction.
        db.execute(text("BEGIN IMMEDIATE"))
        _require_confirmed_profile(db, initiator.participant_id)
        _require_confirmed_profile(db, recipient.participant_id)
        db.refresh(initiator)
        db.refresh(recipient)
        if initiator.outbound_contact_count >= initiator.max_outbound_contacts:
            raise ApiError("OUTBOUND_LIMIT_REACHED", "Outbound contact limit reached", 409)
        recipient_participant = db.get(Participant, recipient.participant_id)
        if recipient_participant is None:
            raise ApiError("NOT_FOUND", "Resource not found", 404)
        if recipient_participant.inbound_contact_count >= recipient_participant.max_inbound_contacts:
            raise ApiError("TARGET_BUSY", "Target is currently busy", 409)
        pair_key = _pair_key(initiator.id, recipient.id)
        existing = db.scalar(
            select(Conversation.id).where(
                Conversation.activity_id == activity_id, Conversation.agent_pair_key == pair_key
            )
        )
        if existing is not None:
            raise ApiError("INVALID_STATE", "Conversation already exists for this pair", 409)

        conversation = Conversation(
            id=f"conv_{uuid4().hex}",
            activity_id=activity_id,
            initiator_agent_id=initiator.id,
            recipient_agent_id=recipient.id,
            agent_pair_key=pair_key,
            status="PENDING_RESPONSE",
            next_actor_agent_id=recipient.id,
        )
        initiator.outbound_contact_count += 1
        recipient_participant.inbound_contact_count += 1
        db.add(conversation)
        _record_action(db, conversation, initiator, action, round_number=1)
        db.commit()
        db.refresh(conversation)
        return conversation
    except ApiError:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        raise ApiError("INVALID_STATE", "Conversation already exists for this pair", 409)


def apply_action(db: Session, *, conversation: Conversation, actor: Agent, action: AgentAction) -> Conversation:
    if conversation.status in TERMINAL_STATUSES or conversation.status == "MUTUAL_AGENT_INTENT":
        raise ApiError("INVALID_STATE", "Conversation is no longer active", 409)
    if conversation.next_actor_agent_id != actor.id or action.recipient_agent_id not in {
        conversation.initiator_agent_id,
        conversation.recipient_agent_id,
    }:
        raise ApiError("INVALID_STATE", "Action is not expected from this agent", 409)
    if action.recipient_agent_id == actor.id or not action.public_message.strip() or not action.private_reason.strip():
        raise ApiError("INVALID_ACTION", "Action payload is incomplete", 422)

    is_response = conversation.status in {"PENDING_RESPONSE", "PROPOSED"}
    if is_response and action.action not in RESPONDING_ACTIONS:
        raise ApiError("INVALID_STATE", "Conversation requires a response", 409)
    if not is_response and action.action not in INITIATING_ACTIONS | {"DECLINE"}:
        raise ApiError("INVALID_STATE", "Conversation requires an initiating action", 409)
    if conversation.status == "PROPOSED" and action.action not in {"ACCEPT", "DECLINE"}:
        raise ApiError("INVALID_STATE", "A proposal requires acceptance or decline", 409)
    if not is_response and conversation.turn_count >= conversation.max_turns:
        raise ApiError("TURN_LIMIT_REACHED", "Turn limit reached", 409)

    round_number = conversation.turn_count + 1
    _record_action(db, conversation, actor, action, round_number)
    counterpart_id = (
        conversation.recipient_agent_id
        if actor.id == conversation.initiator_agent_id
        else conversation.initiator_agent_id
    )
    if action.action == "DECLINE":
        conversation.turn_count = round_number
        conversation.status = "DECLINED"
        conversation.next_actor_agent_id = None
    elif action.action == "ACCEPT":
        conversation.turn_count = round_number
        conversation.status = "MUTUAL_AGENT_INTENT"
        conversation.next_actor_agent_id = None
    elif is_response:
        conversation.turn_count = round_number
        conversation.status = "ACTIVE"
        conversation.next_actor_agent_id = actor.id
    else:
        conversation.status = "PROPOSED" if action.action == "PROPOSE" else "PENDING_RESPONSE"
        conversation.next_actor_agent_id = counterpart_id
    db.commit()
    db.refresh(conversation)
    return conversation

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.models import Agent, Conversation, HumanConfirmation


def participant_agent_for_conversation(
    db: Session, *, participant_id: str, conversation: Conversation
) -> Agent:
    agent = db.scalar(
        select(Agent).where(
            Agent.participant_id == participant_id,
            Agent.id.in_([conversation.initiator_agent_id, conversation.recipient_agent_id]),
        )
    )
    if agent is None:
        raise ApiError("NOT_FOUND", "Resource not found", 404)
    return agent


def confirmation_status(
    db: Session, *, participant_id: str, conversation: Conversation) -> tuple[str | None, str | None]:
    actor = participant_agent_for_conversation(db, participant_id=participant_id, conversation=conversation)
    counterpart_agent_id = (
        conversation.recipient_agent_id
        if actor.id == conversation.initiator_agent_id
        else conversation.initiator_agent_id
    )
    counterpart = db.scalar(select(Agent).where(Agent.id == counterpart_agent_id))
    if counterpart is None:
        raise ApiError("NOT_FOUND", "Resource not found", 404)
    records = {
        item.participant_id: item.decision
        for item in db.scalars(
            select(HumanConfirmation).where(HumanConfirmation.conversation_id == conversation.id)
        )
    }
    return records.get(actor.participant_id), records.get(counterpart.participant_id)


def submit_confirmation(
    db: Session, *, participant_id: str, conversation: Conversation, decision: str
) -> Conversation:
    if conversation.status != "MUTUAL_AGENT_INTENT":
        raise ApiError("INVALID_STATE", "Human confirmation is not available", 409)
    actor = participant_agent_for_conversation(db, participant_id=participant_id, conversation=conversation)
    record = db.scalar(
        select(HumanConfirmation).where(
            HumanConfirmation.conversation_id == conversation.id,
            HumanConfirmation.participant_id == actor.participant_id,
        )
    )
    if record is None:
        record = HumanConfirmation(
            id=f"hcf_{uuid4().hex}",
            conversation_id=conversation.id,
            participant_id=actor.participant_id,
            decision=decision,
        )
        db.add(record)
    else:
        record.decision = decision
    db.flush()
    my_decision, counterpart_decision = confirmation_status(
        db, participant_id=participant_id, conversation=conversation
    )
    if my_decision == "REJECT" or counterpart_decision == "REJECT":
        conversation.status = "HUMAN_REJECTED"
        conversation.next_actor_agent_id = None
    elif my_decision == "ACCEPT" and counterpart_decision == "ACCEPT":
        conversation.status = "CONNECTED"
        conversation.next_actor_agent_id = None
    db.commit()
    db.refresh(conversation)
    return conversation

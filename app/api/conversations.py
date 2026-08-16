from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_participant, get_db, require_owned_participant
from app.core.errors import ApiError
from app.models import Agent, AgentDecision, Conversation, Message, Participant, Profile
from app.schemas.participants import (
    CandidateIntent,
    CandidateIntentListResponse,
    ConfirmationStatusResponse,
    ConversationMessage,
    ConversationResponse,
    Counterpart,
    HumanConfirmationRequest,
    MyDecision,
    MyDecisionResponse,
    VisibleDecision,
)
from app.services.confirmations import confirmation_status, participant_agent_for_conversation, submit_confirmation

router = APIRouter(prefix="/api/v1", tags=["conversations"])


def _visible_conversation(db: Session, participant: Participant, conversation_id: str) -> Conversation:
    conversation = db.get(Conversation, conversation_id)
    if conversation is None:
        raise ApiError("NOT_FOUND", "Resource not found", 404)
    participant_agent_for_conversation(db, participant_id=participant.id, conversation=conversation)
    return conversation


def _conversation_response(db: Session, conversation: Conversation) -> ConversationResponse:
    agents = {agent.id: agent for agent in db.scalars(select(Agent).where(Agent.id.in_([
        conversation.initiator_agent_id, conversation.recipient_agent_id
    ])))}
    participants = {item.id: item for item in db.scalars(select(Participant).where(Participant.id.in_([
        agent.participant_id for agent in agents.values()
    ])))}
    messages = [
        ConversationMessage(
            round_number=message.round_number,
            sender_name=f"{participants[agents[message.sender_agent_id].participant_id].display_name} Agent",
            action=message.action,
            text=message.public_message,
        )
        for message in db.scalars(
            select(Message).where(Message.conversation_id == conversation.id).order_by(Message.created_at, Message.id)
        )
    ]
    decisions = [
        VisibleDecision(
            actor=f"{participants[agents[decision.agent_id].participant_id].display_name} Agent",
            before=decision.decision_before,
            after=decision.decision_after,
            new_information=decision.new_information_json,
        )
        for decision in db.scalars(
            select(AgentDecision)
            .where(AgentDecision.conversation_id == conversation.id)
            .order_by(AgentDecision.created_at, AgentDecision.id)
        )
    ]
    return ConversationResponse(
        id=conversation.id,
        status=conversation.status,
        turn_count=conversation.turn_count,
        max_turns=conversation.max_turns,
        next_actor_agent_id=conversation.next_actor_agent_id,
        messages=messages,
        visible_decisions=decisions,
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
def get_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    participant: Participant = Depends(get_current_participant),
) -> ConversationResponse:
    return _conversation_response(db, _visible_conversation(db, participant, conversation_id))


@router.get("/conversations/{conversation_id}/my-decision", response_model=MyDecisionResponse)
def get_my_decision(
    conversation_id: str,
    db: Session = Depends(get_db),
    participant: Participant = Depends(get_current_participant),
) -> MyDecisionResponse:
    conversation = _visible_conversation(db, participant, conversation_id)
    agent = participant_agent_for_conversation(db, participant_id=participant.id, conversation=conversation)
    decisions = db.scalars(
        select(AgentDecision)
        .where(AgentDecision.conversation_id == conversation.id, AgentDecision.agent_id == agent.id)
        .order_by(AgentDecision.created_at, AgentDecision.id)
    )
    return MyDecisionResponse(decisions=[
        MyDecision(
            before=decision.decision_before,
            after=decision.decision_after,
            missing_information=decision.missing_information_json,
            new_information=decision.new_information_json,
            private_reason=decision.private_reason,
        )
        for decision in decisions
    ])


@router.get("/me/conversations", response_model=list[ConversationResponse])
def list_my_conversations(
    db: Session = Depends(get_db), participant: Participant = Depends(get_current_participant)
) -> list[ConversationResponse]:
    agent = db.scalar(select(Agent).where(Agent.participant_id == participant.id))
    if agent is None:
        return []
    conversations = db.scalars(
        select(Conversation)
        .where((Conversation.initiator_agent_id == agent.id) | (Conversation.recipient_agent_id == agent.id))
        .order_by(Conversation.updated_at.desc())
    )
    return [_conversation_response(db, conversation) for conversation in conversations]


@router.post("/conversations/{conversation_id}/human-confirmations", response_model=ConfirmationStatusResponse)
def create_human_confirmation(
    conversation_id: str,
    payload: HumanConfirmationRequest,
    db: Session = Depends(get_db),
    participant: Participant = Depends(get_current_participant),
) -> ConfirmationStatusResponse:
    conversation = _visible_conversation(db, participant, conversation_id)
    conversation = submit_confirmation(
        db, participant_id=participant.id, conversation=conversation, decision=payload.decision
    )
    my_decision, counterpart_decision = confirmation_status(
        db, participant_id=participant.id, conversation=conversation
    )
    return ConfirmationStatusResponse(
        my_decision=my_decision, counterpart_decision=counterpart_decision, status=conversation.status
    )


@router.get("/conversations/{conversation_id}/confirmation-status", response_model=ConfirmationStatusResponse)
def get_confirmation_status(
    conversation_id: str,
    db: Session = Depends(get_db),
    participant: Participant = Depends(get_current_participant),
) -> ConfirmationStatusResponse:
    conversation = _visible_conversation(db, participant, conversation_id)
    my_decision, counterpart_decision = confirmation_status(
        db, participant_id=participant.id, conversation=conversation
    )
    return ConfirmationStatusResponse(
        my_decision=my_decision, counterpart_decision=counterpart_decision, status=conversation.status
    )


@router.get("/participants/{participant_id}/candidate-intents", response_model=CandidateIntentListResponse)
def candidate_intents(
    participant_id: str,
    db: Session = Depends(get_db),
    participant: Participant = Depends(require_owned_participant),
) -> CandidateIntentListResponse:
    agent = db.scalar(select(Agent).where(Agent.participant_id == participant.id))
    if agent is None:
        return CandidateIntentListResponse(items=[])
    conversations = list(db.scalars(select(Conversation).where(
        ((Conversation.initiator_agent_id == agent.id) | (Conversation.recipient_agent_id == agent.id))
        & Conversation.status.in_(["MUTUAL_AGENT_INTENT", "CONNECTED", "HUMAN_REJECTED"])
    )))
    items: list[CandidateIntent] = []
    for conversation in conversations[:5]:
        counterpart_id = conversation.recipient_agent_id if conversation.initiator_agent_id == agent.id else conversation.initiator_agent_id
        counterpart_agent = db.get(Agent, counterpart_id)
        if counterpart_agent is None:
            continue
        counterpart_participant = db.get(Participant, counterpart_agent.participant_id)
        profile = db.get(Profile, counterpart_agent.participant_id)
        public_items = [item for item in (profile.confirmed_profile_json if profile else []) if item["visibility"] == "public"]
        my_decision, counterpart_decision = confirmation_status(db, participant_id=participant.id, conversation=conversation)
        status = "connected" if conversation.status == "CONNECTED" else "rejected" if conversation.status == "HUMAN_REJECTED" else "awaiting_my_confirmation" if my_decision is None else "waiting_for_counterpart"
        decisions = db.scalars(select(AgentDecision).where(AgentDecision.conversation_id == conversation.id))
        new_information = [text for decision in decisions for text in decision.new_information_json]
        items.append(CandidateIntent(
            conversation_id=conversation.id,
            counterpart=Counterpart(
                display_name=counterpart_participant.display_name if counterpart_participant else "Unknown",
                public_offer=[item["text"] for item in public_items if item["kind"] == "offer"],
                public_need=[item["text"] for item in public_items if item["kind"] in {"explicit_need", "inferred_need"}],
            ),
            newly_confirmed=list(dict.fromkeys(new_information)),
            open_questions=["是否约定线下见面时间"],
            status=status,
        ))
    return CandidateIntentListResponse(items=items)

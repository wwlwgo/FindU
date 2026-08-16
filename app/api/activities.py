from uuid import uuid4

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_participant, get_db
from app.core.errors import ApiError
from app.models import Activity, Agent, Conversation, Participant, Profile
from app.schemas.participants import Broadcast, BroadcastListResponse, RunRequest, RunResponse
from app.services.events import EventBus, encode_sse
from app.services.replay import run_next_replay_step

router = APIRouter(prefix="/api/v1", tags=["activities"])


def _require_activity_participant(db: Session, activity_id: str, participant: Participant) -> None:
    if participant.activity_id != activity_id or db.get(Activity, activity_id) is None:
        raise ApiError("NOT_FOUND", "Resource not found", 404)


@router.get("/activities/{activity_id}/broadcasts", response_model=BroadcastListResponse)
def broadcasts(
    activity_id: str,
    db: Session = Depends(get_db),
    participant: Participant = Depends(get_current_participant),
) -> BroadcastListResponse:
    _require_activity_participant(db, activity_id, participant)
    current_agent = db.scalar(select(Agent).where(Agent.participant_id == participant.id))
    if current_agent is None:
        raise ApiError("PROFILE_NOT_CONFIRMED", "Profile must be confirmed before discovery", 422)
    rows = db.execute(
        select(Agent, Participant, Profile)
        .join(Participant, Participant.id == Agent.participant_id)
        .join(Profile, Profile.participant_id == Participant.id)
        .where(Participant.activity_id == activity_id, Agent.id != current_agent.id)
        .order_by(Participant.display_name)
    )
    return BroadcastListResponse(
        items=[
            Broadcast(
                agent_id=agent.id,
                display_name=other.display_name,
                message=profile.public_broadcast or "",
                contact_status="busy" if other.inbound_contact_count >= other.max_inbound_contacts else "available",
            )
            for agent, other, profile in rows
        ],
        outbound_contact_count=current_agent.outbound_contact_count,
        max_outbound_contacts=current_agent.max_outbound_contacts,
    )


@router.post("/activities/{activity_id}/runs", response_model=RunResponse, status_code=202)
def run_agent(
    activity_id: str,
    payload: RunRequest,
    request: Request,
    db: Session = Depends(get_db),
    participant: Participant = Depends(get_current_participant),
) -> RunResponse:
    _require_activity_participant(db, activity_id, participant)
    if payload.mode != "replay" or not payload.replay_track_id:
        raise ApiError("PROVIDER_UNAVAILABLE", "Live provider is not configured; use replay mode", 503)
    agent = db.scalar(select(Agent).where(Agent.participant_id == participant.id))
    if agent is None:
        raise ApiError("PROFILE_NOT_CONFIRMED", "Profile must be confirmed before running an agent", 422)
    conversation, action = run_next_replay_step(
        db, activity_id=activity_id, actor=agent, track_id=payload.replay_track_id
    )
    counterpart_id = conversation.recipient_agent_id if agent.id == conversation.initiator_agent_id else conversation.initiator_agent_id
    counterpart = db.get(Agent, counterpart_id)
    if counterpart is None:
        raise ApiError("NOT_FOUND", "Resource not found", 404)
    bus: EventBus = request.app.state.event_bus
    visible_to = {agent.participant_id, counterpart.participant_id}
    round_number = conversation.turn_count + (0 if action.action in {"ANSWER", "ACCEPT", "DECLINE"} else 1)
    sender_agent = agent if action.recipient_agent_id == counterpart.id else counterpart
    sender = db.get(Participant, sender_agent.participant_id)
    bus.publish(
        event_type="agent.message.created", conversation_id=conversation.id,
        data={"senderName": f"{sender.display_name if sender else 'Agent'} Agent", "action": action.action,
              "text": action.public_message, "roundNumber": round_number}, visible_to=visible_to,
    )
    bus.publish(
        event_type="agent.decision.updated", conversation_id=conversation.id,
        data={"actor": f"{sender.display_name if sender else 'Agent'} Agent", "before": action.decision_before,
              "after": action.decision_after, "newInformation": action.new_information, "roundNumber": round_number}, visible_to=visible_to,
    )
    bus.publish(
        event_type="conversation.status.changed", conversation_id=conversation.id,
        data={"status": conversation.status, "turnCount": conversation.turn_count,
              "nextActorAgentId": conversation.next_actor_agent_id}, visible_to=visible_to,
    )
    if conversation.status == "MUTUAL_AGENT_INTENT":
        bus.publish(event_type="candidate.intent.created", conversation_id=conversation.id, data={"conversationId": conversation.id}, visible_to=visible_to)
    return RunResponse(run_id=f"run_{uuid4().hex}", status="queued")


@router.get("/activities/{activity_id}/events")
def events(
    activity_id: str,
    request: Request,
    last_event_id: str | None = Header(default=None),
    db: Session = Depends(get_db),
    participant: Participant = Depends(get_current_participant),
) -> StreamingResponse:
    _require_activity_participant(db, activity_id, participant)
    try:
        after_id = int(last_event_id) if last_event_id else None
    except ValueError as error:
        raise ApiError("VALIDATION_ERROR", "Last-Event-ID must be numeric", 422) from error
    bus: EventBus = request.app.state.event_bus
    return StreamingResponse((encode_sse(event) for event in bus.stream(participant.id, after_id)), media_type="text/event-stream")

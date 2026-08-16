import hashlib
import secrets

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, require_owned_participant
from app.core.errors import ApiError
from app.models import Activity, Participant, ParticipantSession, Profile
from app.schemas.participants import (
    CreateParticipantRequest,
    CreateParticipantResponse,
    CreateProfileDraftRequest,
    CreateProfileDraftResponse,
    ParticipantSummary,
    ProfileItem,
    ProfileResponse,
    UpdateProfileRequest,
    UpdateProfileResponse,
)
from app.services.profile import create_draft, save_confirmed_profile
from app.providers.base import ProviderUnavailable
from app.providers.fallbacks import transcribe_or_raise

router = APIRouter(prefix="/api/v1", tags=["participants"])


@router.post("/participants/{participant_id}/recording")
async def upload_recording(
    participant_id: str,
    request: Request,
    _: Participant = Depends(require_owned_participant),
) -> None:
    audio = await request.body()
    try:
        transcribe_or_raise(audio, request.headers.get("content-type", "application/octet-stream"))
    except ProviderUnavailable as error:
        raise ApiError(
            "PROVIDER_UNAVAILABLE",
            "Speech provider unavailable; use the preset transcript fallback",
            503,
        ) from error


@router.post("/participants", response_model=CreateParticipantResponse, status_code=status.HTTP_201_CREATED)
def create_participant(payload: CreateParticipantRequest, db: Session = Depends(get_db)) -> CreateParticipantResponse:
    activity = db.get(Activity, payload.activity_id)
    if activity is None:
        raise ApiError(code="ACTIVITY_NOT_FOUND", message="Activity not found", status_code=404)
    participant = Participant(id=f"p_{secrets.token_urlsafe(12)}", activity_id=activity.id, display_name=payload.display_name)
    raw_token = secrets.token_urlsafe(32)
    db.add(participant)
    db.add(ParticipantSession(token_hash=hashlib.sha256(raw_token.encode("utf-8")).hexdigest(), participant_id=participant.id))
    db.commit()
    return CreateParticipantResponse(participant=ParticipantSummary(id=participant.id, activity_id=participant.activity_id), access_token=raw_token)


@router.post("/participants/{participant_id}/profile-draft", response_model=CreateProfileDraftResponse)
def create_profile_draft(
    participant_id: str,
    payload: CreateProfileDraftRequest,
    _: Participant = Depends(require_owned_participant),
) -> CreateProfileDraftResponse:
    return CreateProfileDraftResponse(draft={"transcript": payload.transcript, "items": create_draft(payload.transcript)})


@router.put("/participants/{participant_id}/profile", response_model=UpdateProfileResponse)
def update_profile(
    participant_id: str,
    payload: UpdateProfileRequest,
    db: Session = Depends(get_db),
    participant: Participant = Depends(require_owned_participant),
) -> UpdateProfileResponse:
    agent, profile = save_confirmed_profile(db, participant, payload.display_name, payload.items)
    return UpdateProfileResponse(agent={"id": agent.id, "status": "ready"}, broadcast=profile.public_broadcast or "")


@router.get("/participants/{participant_id}/profile", response_model=ProfileResponse)
def get_profile(
    participant_id: str,
    db: Session = Depends(get_db),
    participant: Participant = Depends(require_owned_participant),
) -> ProfileResponse:
    profile = db.get(Profile, participant.id)
    if profile is None:
        return ProfileResponse(display_name=participant.display_name, transcript_status="pending", items=[], broadcast=None)
    return ProfileResponse(
        display_name=participant.display_name,
        transcript_status=profile.transcript_status,
        items=[ProfileItem.model_validate(item) for item in profile.confirmed_profile_json],
        broadcast=profile.public_broadcast,
    )

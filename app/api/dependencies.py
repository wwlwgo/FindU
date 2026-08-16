import hashlib
from collections.abc import Generator

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import Database
from app.core.errors import ApiError
from app.models import Participant, ParticipantSession

bearer_scheme = HTTPBearer(auto_error=False)


def get_db(request: Request) -> Generator[Session, None, None]:
    database: Database = request.app.state.database
    yield from database.session()


def get_current_participant(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Participant:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise ApiError(code="UNAUTHORIZED", message="Authentication is required", status_code=401)
    token_hash = hashlib.sha256(credentials.credentials.encode("utf-8")).hexdigest()
    token_session = db.get(ParticipantSession, token_hash)
    if token_session is None:
        raise ApiError(code="UNAUTHORIZED", message="Invalid access token", status_code=401)
    participant = db.get(Participant, token_session.participant_id)
    if participant is None:
        raise ApiError(code="UNAUTHORIZED", message="Invalid access token", status_code=401)
    return participant


def require_owned_participant(
    participant_id: str,
    current_participant: Participant = Depends(get_current_participant),
) -> Participant:
    if current_participant.id != participant_id:
        raise ApiError(code="NOT_FOUND", message="Resource not found", status_code=404)
    return current_participant

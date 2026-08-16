from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Activity(Base):
    __tablename__ = "activities"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="OPEN")
    matching_window_id: Mapped[str] = mapped_column(String(64), nullable=False, default="window_demo")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Participant(Base):
    __tablename__ = "participants"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    activity_id: Mapped[str] = mapped_column(ForeignKey("activities.id"), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    inbound_contact_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_inbound_contacts: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Profile(Base):
    __tablename__ = "profiles"

    participant_id: Mapped[str] = mapped_column(ForeignKey("participants.id"), primary_key=True)
    transcript_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    confirmed_profile_json: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False, default=list)
    public_broadcast: Mapped[str | None] = mapped_column(Text, nullable=True)
    private_preferences_json: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False, default=list)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    participant_id: Mapped[str] = mapped_column(ForeignKey("participants.id"), unique=True, nullable=False)
    provider_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="LIVE")
    max_outbound_contacts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    outbound_contact_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_candidate_intents: Mapped[int] = mapped_column(Integer, nullable=False, default=5)


class ParticipantSession(Base):
    __tablename__ = "participant_sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    participant_id: Mapped[str] = mapped_column(ForeignKey("participants.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

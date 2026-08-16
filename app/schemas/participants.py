from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


def to_camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


class CamelModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)


Visibility = Literal["public", "private", "disabled"]
ProfileItemKind = Literal["fact", "offer", "explicit_need", "inferred_need", "preference"]


class CreateParticipantRequest(CamelModel):
    activity_id: str = Field(min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=80)


class ParticipantSummary(CamelModel):
    id: str
    activity_id: str


class CreateParticipantResponse(CamelModel):
    participant: ParticipantSummary
    access_token: str


class ProfileItem(CamelModel):
    id: str = Field(min_length=1, max_length=96)
    kind: ProfileItemKind
    text: str = Field(min_length=1, max_length=500)
    evidence: str | None = Field(default=None, max_length=1000)
    confirmed: bool
    visibility: Visibility


class CreateProfileDraftRequest(CamelModel):
    transcript: str = Field(min_length=1, max_length=6000)


class ProfileDraft(CamelModel):
    transcript: str
    items: list[ProfileItem]


class CreateProfileDraftResponse(CamelModel):
    draft: ProfileDraft


class UpdateProfileRequest(CamelModel):
    display_name: str = Field(min_length=1, max_length=80)
    items: list[ProfileItem] = Field(min_length=1, max_length=40)


class AgentSummary(CamelModel):
    id: str
    status: str


class UpdateProfileResponse(CamelModel):
    agent: AgentSummary
    broadcast: str


class ProfileResponse(CamelModel):
    display_name: str
    transcript_status: str
    items: list[ProfileItem]
    broadcast: str | None


ConfirmationDecision = Literal["ACCEPT", "REJECT"]


class HumanConfirmationRequest(CamelModel):
    decision: ConfirmationDecision


class ConfirmationStatusResponse(CamelModel):
    my_decision: ConfirmationDecision | None
    counterpart_decision: ConfirmationDecision | None
    status: str


class ConversationMessage(CamelModel):
    round_number: int
    sender_name: str
    action: str
    text: str


class VisibleDecision(CamelModel):
    actor: str
    before: str
    after: str
    new_information: list[str]


class ConversationResponse(CamelModel):
    id: str
    status: str
    turn_count: int
    max_turns: int
    next_actor_agent_id: str | None
    messages: list[ConversationMessage]
    visible_decisions: list[VisibleDecision]


class Counterpart(CamelModel):
    display_name: str
    public_offer: list[str]
    public_need: list[str]


class CandidateIntent(CamelModel):
    conversation_id: str
    counterpart: Counterpart
    newly_confirmed: list[str]
    open_questions: list[str]
    status: str


class CandidateIntentListResponse(CamelModel):
    items: list[CandidateIntent]

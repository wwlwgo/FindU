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

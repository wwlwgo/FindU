from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import Agent, Participant, Profile
from app.schemas.participants import ProfileItem


def create_draft(transcript: str) -> list[ProfileItem]:
    normalized = transcript.lower()
    items: list[ProfileItem] = []
    if any(keyword in normalized for keyword in ("前端", "frontend", "交互", "react")):
        items.append(ProfileItem(id="fact_frontend", kind="fact", text="具备前端与交互实现经验", evidence=transcript, confirmed=False, visibility="public"))
    if any(keyword in normalized for keyword in ("后端", "backend", "python", "模型", "ai")):
        items.append(ProfileItem(id="need_technical_partner", kind="explicit_need", text="希望认识能共同完成技术原型的人", evidence=transcript, confirmed=False, visibility="public"))
    items.append(ProfileItem(id="inferred_need_scope", kind="inferred_need", text="可能希望有人一起缩小项目范围并快速验证方向", evidence="根据自我介绍中对项目方向和协作需求的表达推断", confirmed=False, visibility="private"))
    return items


def build_broadcast(items: list[dict[str, object]], display_name: str) -> str:
    public_texts = [str(item["text"]) for item in items if item["visibility"] == "public"]
    return f"我是 {display_name}，{'；'.join(public_texts[:2]) or '希望认识值得交流的黑客松参与者'}。"


def save_confirmed_profile(db: Session, participant: Participant, display_name: str, items: list[ProfileItem]) -> tuple[Agent, Profile]:
    active_items = [item.model_dump() for item in items if item.confirmed and item.visibility != "disabled"]
    private_items = [item for item in active_items if item["visibility"] == "private"]
    participant.display_name = display_name
    profile = db.get(Profile, participant.id)
    if profile is None:
        profile = Profile(participant_id=participant.id)
        db.add(profile)
    profile.transcript_status = "confirmed"
    profile.confirmed_profile_json = active_items
    profile.private_preferences_json = private_items
    profile.public_broadcast = build_broadcast(active_items, display_name)
    profile.confirmed_at = datetime.now(timezone.utc)
    agent = db.query(Agent).filter(Agent.participant_id == participant.id).one_or_none()
    if agent is None:
        agent = Agent(id=f"agent_{participant.id.removeprefix('p_')}", participant_id=participant.id)
        db.add(agent)
    db.commit()
    db.refresh(profile)
    db.refresh(agent)
    return agent, profile

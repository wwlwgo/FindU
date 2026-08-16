import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import Activity, Agent, Participant, Profile


def ensure_demo_activity(db: Session) -> None:
    try:
        if db.get(Activity, "act_demo") is None:
            db.add(Activity(id="act_demo", name="FindU Demo", status="OPEN", matching_window_id="window_demo"))
            db.commit()
    finally:
        db.close()


def ensure_mock_agents(db: Session) -> None:
    fixture_path = Path(__file__).resolve().parents[2] / "mock" / "agents.json"
    if not fixture_path.exists():
        return
    try:
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        for item in fixture["agents"]:
            participant_id = item["participantId"]
            if db.get(Participant, participant_id) is not None:
                continue
            public_profile = item["publicProfile"]
            kind_names = {"facts": "fact", "offers": "offer", "needs": "explicit_need"}
            profile_items = [
                {"id": f"{kind}_{index}", "kind": kind_names[kind], "text": text,
                 "evidence": None, "confirmed": True, "visibility": "public"}
                for kind in ("facts", "offers", "needs")
                for index, text in enumerate(public_profile.get(kind, []), start=1)
            ]
            db.add(Participant(
                id=participant_id, activity_id=fixture["activityId"], display_name=item["displayName"]
            ))
            db.add(Profile(
                participant_id=participant_id,
                transcript_status="confirmed",
                confirmed_profile_json=profile_items,
                public_broadcast=item["broadcast"],
                private_preferences_json=item["privatePreferences"],
            ))
            db.add(Agent(
                id=item["agentId"], participant_id=participant_id, provider_mode=item["providerMode"],
                max_outbound_contacts=item["limits"]["maxOutboundContacts"],
                max_candidate_intents=item["limits"]["maxCandidateIntents"],
            ))
        db.commit()
    finally:
        db.close()

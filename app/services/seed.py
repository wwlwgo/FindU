from sqlalchemy.orm import Session

from app.models import Activity


def ensure_demo_activity(db: Session) -> None:
    try:
        if db.get(Activity, "act_demo") is None:
            db.add(Activity(id="act_demo", name="FindU Demo", status="OPEN", matching_window_id="window_demo"))
            db.commit()
    finally:
        db.close()

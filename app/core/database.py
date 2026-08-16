from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.base import Base


class Database:
    def __init__(self, database_url: str) -> None:
        if database_url.startswith("sqlite:///"):
            Path(database_url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)

        connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        self.engine = create_engine(database_url, connect_args=connect_args)
        self.session_factory = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)

    def initialize(self) -> None:
        Base.metadata.create_all(bind=self.engine)

    def dispose(self) -> None:
        self.engine.dispose()

    def session(self) -> Generator[Session, None, None]:
        db = self.session_factory()
        try:
            yield db
        finally:
            db.close()

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def client(tmp_path) -> Generator[TestClient, None, None]:
    database_path = tmp_path / "findu-test.db"
    settings = Settings(database_url=f"sqlite:///{database_path}")
    with TestClient(create_app(settings)) as test_client:
        yield test_client

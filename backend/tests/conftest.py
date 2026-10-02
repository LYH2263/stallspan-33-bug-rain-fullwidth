import os

# 必须在导入 app.* 之前：app.database 会在导入时按 DATABASE_URL 建引擎。
os.environ.setdefault("DATABASE_URL", "sqlite://")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.services.seed import seed_if_empty


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = testing_session_local()
    seed_if_empty(db)
    yield db
    db.close()
    engine.dispose()


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = _override_get_db
    from fastapi.testclient import TestClient
    # 不使用 with：跳过 lifespan，避免它去连配置里的真实 Postgres（表已由本 fixture 建好）。
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()

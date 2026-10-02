from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from app.api.router import api_router
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.services.seed import seed_if_empty


# 轻量幂等迁移：create_all 不会给已存在的表补列，老库启动时在此补齐雨天字段。
def _ensure_columns() -> None:
    inspector = inspect(engine)
    if "market_days" not in inspector.get_table_names():
        return
    existing = {c["name"] for c in inspector.get_columns("market_days")}
    dialect = engine.dialect.name
    with engine.begin() as conn:
        if "rainy" not in existing:
            default = "0" if dialect == "sqlite" else "false"
            conn.execute(text(
                f"ALTER TABLE market_days ADD COLUMN rainy BOOLEAN NOT NULL DEFAULT {default}"
            ))
        if "rain_width_factor" not in existing:
            type_sql = "FLOAT" if dialect == "sqlite" else "DOUBLE PRECISION"
            conn.execute(text(
                f"ALTER TABLE market_days ADD COLUMN rain_width_factor {type_sql}"
            ))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    _ensure_columns()
    if settings.seed_on_empty:
        db = SessionLocal()
        try:
            seed_if_empty(db)
        finally:
            db.close()
    yield


app = FastAPI(title="StallSpan", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix="/api")

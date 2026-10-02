from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import MarketDay
from app.services.effective_width import is_valid_factor
router = APIRouter(prefix="/days", tags=["days"])

class DayRainUpdate(BaseModel):
    rainy: bool
    # 0..1；雨天为真时必填且合法。前端在关雨时可传 None 或原值（后端忽略）。
    rain_width_factor: float | None = None

def _serialize(r: MarketDay) -> dict:
    return {
        "id": r.id, "name": r.name, "day": r.day.isoformat(),
        "rainy": bool(r.rainy),
        "rain_width_factor": (round(float(r.rain_width_factor), 3)
                              if r.rain_width_factor is not None else None),
    }

@router.get("")
def list_days(db: Session = Depends(get_db)):
    return [_serialize(r) for r in db.scalars(select(MarketDay).order_by(MarketDay.id)).all()]

@router.put("/{day_id}")
def update_day(day_id: int, body: DayRainUpdate, db: Session = Depends(get_db)):
    day = db.get(MarketDay, day_id)
    if not day:
        raise HTTPException(404, "集日不存在")
    # 雨天为真但未填系数 / 系数越界：拒绝保存，库内保持改前状态，
    # 集日页、主图、放不下都不会进入半截缩短。
    if body.rainy and not is_valid_factor(body.rain_width_factor):
        raise HTTPException(400, "雨天为真时必须登记 0 到 1 之间的有效宽度系数")
    day.rainy = body.rainy
    # 非雨天忽略系数：晴天不显示、不生效；仅在雨天合法时落库，避免脏值。
    day.rain_width_factor = float(body.rain_width_factor) if body.rainy else None
    db.commit()
    db.refresh(day)
    return _serialize(day)

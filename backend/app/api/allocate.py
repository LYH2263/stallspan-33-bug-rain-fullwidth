import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import AllocationRun, MarketDay, Pillar, Segment, Vendor
from app.services.effective_width import InvalidRainFactorError, effective_width
from app.services.first_fit_engine import allocate_first_fit, result_to_dict
router = APIRouter(prefix="/allocate", tags=["allocate"])

def _compute(seg: Segment, day: MarketDay | None, db: Session) -> dict:
    """按集日当前雨天设置算一次分配。有效宽度是全函数唯一宽度来源。"""
    try:
        eff_width = effective_width(seg.width_m, day)
    except InvalidRainFactorError as exc:
        # 正常保存接口已拦住；这里见到脏数据直接 400，绝不按晴天全长出图。
        raise HTTPException(400, str(exc))
    pillars = [{"id": p.id, "position_m": p.position_m, "thickness_m": p.thickness_m,
                "label": p.label}
               for p in db.scalars(select(Pillar).where(Pillar.segment_id == seg.id)).all()]
    vendors = [{"id": v.id, "name": v.name, "stall_width_m": v.stall_width_m, "priority": v.priority}
               for v in db.scalars(select(Vendor).where(Vendor.market_day_id == seg.market_day_id)).all()]
    result = result_to_dict(allocate_first_fit(eff_width, vendors, pillars))
    rainy = bool(day.rainy) if day else False
    factor = (round(float(day.rain_width_factor), 3)
              if day is not None and day.rain_width_factor is not None else None)
    # 宽度快照：主图右端、放不下、运行抽屉都消费这里，四处同源。
    result["segment"] = {
        "id": seg.id, "name": seg.name,
        "registered_width_m": seg.width_m,   # 登记（晴天全长）
        "effective_width_m": eff_width,       # 实际参与切空/出图的右端
        "rainy": rainy,
        "rain_width_factor": factor,
    }
    # 兼容旧字段名：width_m 即本次有效右端（不再是晴天全长）
    result["segment"]["width_m"] = eff_width
    return result

@router.post("/run")
def run_allocate(segment_id: int = 1, db: Session = Depends(get_db)):
    seg = db.get(Segment, segment_id)
    if not seg: raise HTTPException(404, "街段不存在")
    day = db.get(MarketDay, seg.market_day_id)
    result = _compute(seg, day, db)
    run = AllocationRun(segment_id=segment_id, created_at=datetime.utcnow(),
                        result_json=json.dumps(result, ensure_ascii=False))
    db.add(run); db.commit(); db.refresh(run)
    return {"id": run.id, **result}

@router.get("/latest")
def latest(segment_id: int = 1, db: Session = Depends(get_db)):
    run = db.scalars(select(AllocationRun).where(AllocationRun.segment_id == segment_id)
                     .order_by(AllocationRun.id.desc())).first()
    if not run:
        return run_allocate(segment_id=segment_id, db=db)
    # 直接回放快照：旧运行的右端不被新系数回刷。
    return {"id": run.id, **json.loads(run.result_json)}

@router.get("/runs")
def list_runs(segment_id: int = 1, db: Session = Depends(get_db)):
    """运行抽屉：每次再分都是一条不可变快照，宽度/雨天随当次记录。"""
    rows = db.scalars(select(AllocationRun).where(AllocationRun.segment_id == segment_id)
                      .order_by(AllocationRun.id.desc())).all()
    out = []
    for run in rows:
        data = json.loads(run.result_json)
        seg = data.get("segment", {})
        out.append({
            "id": run.id,
            "created_at": run.created_at.isoformat(),
            "segment_name": seg.get("name"),
            "effective_width_m": seg.get("effective_width_m", seg.get("width_m")),
            "registered_width_m": seg.get("registered_width_m"),
            "rainy": seg.get("rainy", False),
            "rain_width_factor": seg.get("rain_width_factor"),
            "placed": len(data.get("placements", [])),
            "rejected": len(data.get("rejected", [])),
        })
    return out

@router.get("/runs/{run_id}")
def get_run(run_id: int, db: Session = Depends(get_db)):
    run = db.get(AllocationRun, run_id)
    if not run: raise HTTPException(404, "运行不存在")
    return {"id": run.id, "created_at": run.created_at.isoformat(),
            **json.loads(run.result_json)}

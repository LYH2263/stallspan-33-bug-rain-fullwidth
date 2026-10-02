"""1D First-Fit stall placement along a street segment; stalls cannot cross pillars.

雨天缩宽后挡柱与新右端的关系统一只用 clip_pillars_to_width() 一个函数，
切空引擎、出图、放不下、运行抽屉都消费它的产物，禁止各处自行解释。
钉死策略：挡柱米标(position_m)超出有效右端 → 整根柱作废，不参与切空、不出图；
米标在界内的柱，其遮挡区间只做边界裁切（lo≥0、hi≤width）。
"""
from __future__ import annotations
from dataclasses import asdict, dataclass

@dataclass
class Placement:
    vendor_id: int
    vendor_name: str
    start_m: float
    end_m: float
    width_m: float

@dataclass
class Rejected:
    vendor_id: int
    vendor_name: str
    width_m: float
    reason: str

@dataclass
class AllocResult:
    placements: list[Placement]
    rejected: list[Rejected]
    free_spans: list[tuple[float, float]]
    pillars: list[dict] = None       # 参与切空的柱（含裁后 start_m/end_m 几何）
    voided_pillars: list[dict] = None  # 米标超出右端、整根作废的柱

def clip_pillars_to_width(width_m: float, pillars: list[dict]) -> tuple[list[dict], list[dict]]:
    """把挡柱裁到有效宽度内。

    返回 (kept, voided)：
    - kept: 米标在 [0, width] 内的柱，带 start_m/end_m（已夹到 [0,width]），供切空与出图；
    - voided: 米标超出右端（或在 0 左侧）的整根柱，不参与切空、主图不按全长绘制。
    """
    kept: list[dict] = []
    voided: list[dict] = []
    for p in pillars:
        half = p.get("thickness_m", 0.4) / 2.0
        pos = p["position_m"]
        if pos > width_m + 1e-9 or pos < -1e-9:
            voided.append({**p, "reason": f"米标 {round(pos, 3)}m 超出有效右端 {round(width_m, 3)}m，整根柱作废"})
            continue
        lo = max(0.0, pos - half)
        hi = min(width_m, pos + half)
        if hi > lo:
            kept.append({**p, "start_m": round(lo, 3), "end_m": round(hi, 3)})
    kept.sort(key=lambda p: p["start_m"])
    voided.sort(key=lambda p: p["position_m"])
    return kept, voided

def free_spans_from_pillars(width_m: float, pillars: list[dict]) -> list[tuple[float, float]]:
    """pillars: position_m, thickness_m — treated as blocked intervals.

    米标超界的柱整根作废；界内柱的遮挡区间裁到 [0, width_m]。
    """
    kept, _ = clip_pillars_to_width(width_m, pillars)
    blocked = sorted((p["start_m"], p["end_m"]) for p in kept)
    merged = []
    for lo, hi in blocked:
        if not merged or lo > merged[-1][1]:
            merged.append([lo, hi])
        else:
            merged[-1][1] = max(merged[-1][1], hi)
    spans = []
    cursor = 0.0
    for lo, hi in merged:
        if lo > cursor:
            spans.append((cursor, lo))
        cursor = hi
    if cursor < width_m:
        spans.append((cursor, width_m))
    return [(round(a, 3), round(b, 3)) for a, b in spans if b - a > 1e-6]

def allocate_first_fit(width_m: float, vendors: list[dict], pillars: list[dict]) -> AllocResult:
    """vendors sorted by priority ascending then id; each needs stall_width_m contiguous in one free span (no pillar cross).

    width_m 必须是调用方按雨天系数算好的有效宽度（见 app.services.effective_width），
    引擎本身不认识"晴天全长"，只对传入的有效宽度负责。
    """
    kept_pillars, voided_pillars = clip_pillars_to_width(width_m, pillars)
    blocked = sorted((p["start_m"], p["end_m"]) for p in kept_pillars)
    # free spans from (already clipped) blocked intervals
    merged: list[list[float]] = []
    for lo, hi in blocked:
        if not merged or lo > merged[-1][1]:
            merged.append([lo, hi])
        else:
            merged[-1][1] = max(merged[-1][1], hi)
    spans: list[list[float]] = []
    cursor = 0.0
    for lo, hi in merged:
        if lo > cursor:
            spans.append([cursor, lo])
        cursor = hi
    if cursor < width_m:
        spans.append([cursor, width_m])
    remain = [[a, b] for a, b in spans]
    ordered = sorted(vendors, key=lambda v: (v.get("priority", 1), v["id"]))
    placements: list[Placement] = []
    rejected: list[Rejected] = []
    for v in ordered:
        need = float(v["stall_width_m"])
        placed = False
        for span in remain:
            avail = span[1] - span[0]
            if avail + 1e-9 >= need:
                start = span[0]
                end = start + need
                placements.append(Placement(v["id"], v["name"], round(start, 3), round(end, 3), need))
                span[0] = end
                placed = True
                break
        if not placed:
            rejected.append(Rejected(v["id"], v["name"], need, "无连续空档可放下且不跨越挡柱"))
    free = [(round(a, 3), round(b, 3)) for a, b in remain if b - a > 1e-6]
    return AllocResult(placements, rejected, free, kept_pillars, voided_pillars)

def result_to_dict(r: AllocResult) -> dict:
    return {
        "placements": [asdict(p) for p in r.placements],
        "rejected": [asdict(x) for x in r.rejected],
        "free_spans": [{"start_m": a, "end_m": b} for a, b in r.free_spans],
        "pillars": r.pillars or [],
        "voided_pillars": r.voided_pillars or [],
    }

from app.services.first_fit_engine import (
    allocate_first_fit, clip_pillars_to_width, free_spans_from_pillars,
)

def test_free_spans_with_pillars():
    spans = free_spans_from_pillars(30.0, [{"position_m": 10.0, "thickness_m": 0.5}, {"position_m": 20.0, "thickness_m": 0.5}])
    assert len(spans) == 3
    assert spans[0][0] == 0.0

def test_first_fit_no_cross_pillar():
    vendors = [
        {"id": 1, "name": "A", "stall_width_m": 4.0, "priority": 1},
        {"id": 2, "name": "B", "stall_width_m": 12.0, "priority": 1},
    ]
    pillars = [{"position_m": 10.0, "thickness_m": 0.5}]
    r = allocate_first_fit(30.0, vendors, pillars)
    assert any(p.vendor_name == "A" for p in r.placements)
    # 12m may fit in a free span after first placement depending on remainders
    assert len(r.placements) + len(r.rejected) == 2

def test_reject_oversized():
    vendors = [{"id": 1, "name": "Huge", "stall_width_m": 25.0, "priority": 1}]
    pillars = [{"position_m": 10.0, "thickness_m": 0.5}, {"position_m": 20.0, "thickness_m": 0.5}]
    r = allocate_first_fit(30.0, vendors, pillars)
    assert len(r.rejected) == 1
    assert r.rejected[0].vendor_name == "Huge"

def test_pillar_past_effective_right_end_is_voided_whole():
    """钉死策略：米标超出缩后右端 → 整根柱作废，不参与切空、不出图。"""
    pillars = [
        {"id": 1, "position_m": 10.0, "thickness_m": 0.5},
        {"id": 2, "position_m": 20.0, "thickness_m": 0.5},
    ]
    kept, voided = clip_pillars_to_width(24.0, pillars)
    assert [p["id"] for p in kept] == [1, 2]  # 20m 仍在 24m 内
    assert voided == []
    # 缩到 18m：20m 柱整根作废
    kept, voided = clip_pillars_to_width(18.0, pillars)
    assert [p["id"] for p in kept] == [1]
    assert [p["id"] for p in voided] == [2]
    # 作废柱不产生阻断：最后空档一路到有效右端
    spans = free_spans_from_pillars(18.0, pillars)
    assert spans[-1] == (10.25, 18.0)

def test_pillar_straddling_right_end_is_clipped_not_voided():
    """米标在界内、柱身压过右端：保留柱并把遮挡区间裁到右端（不越界出图）。"""
    pillars = [{"id": 1, "position_m": 23.9, "thickness_m": 0.5}]
    kept, voided = clip_pillars_to_width(24.0, pillars)
    assert voided == []
    assert kept[0]["start_m"] == 23.65
    assert kept[0]["end_m"] == 24.0

def test_effective_width_changes_rejected_set():
    """雨天使有效宽缩短后，放不下集合随之变化，且坐标不超过有效右端。"""
    vendors = [
        {"id": 1, "name": "A", "stall_width_m": 10.0, "priority": 1},
        {"id": 2, "name": "B", "stall_width_m": 10.0, "priority": 1},
        {"id": 3, "name": "C", "stall_width_m": 10.0, "priority": 1},
    ]
    # 无挡柱：晴天全长 30 正好全放下；雨天 24 只能放两个，第三个进放不下
    sunny = allocate_first_fit(30.0, vendors, [])
    rainy = allocate_first_fit(24.0, vendors, [])
    assert len(sunny.rejected) == 0
    assert [x.vendor_name for x in rainy.rejected] == ["C"]
    # 任何落点都不得超出有效右端（禁止按晴天全长出放不下）
    for p in rainy.placements:
        assert p.end_m <= 24.0 + 1e-9
    for a, b in rainy.free_spans:
        assert b <= 24.0 + 1e-9
    assert rainy.free_spans == [(20.0, 24.0)]

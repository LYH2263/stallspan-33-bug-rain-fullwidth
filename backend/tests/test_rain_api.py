from app.models.models import MarketDay


def test_seed_rainy_day_and_24m_effective_width(client):
    """种子：周末夜市勾雨天系数 0.8，东街段 30m 按 24m 参与。"""
    days = client.get("/api/days").json()
    assert len(days) == 1
    d = days[0]
    assert d["name"] == "周末夜市"
    assert d["rainy"] is True
    assert d["rain_width_factor"] == 0.8

    run = client.post("/api/allocate/run?segment_id=1").json()
    seg = run["segment"]
    assert seg["registered_width_m"] == 30.0
    assert seg["effective_width_m"] == 24.0
    assert seg["width_m"] == 24.0  # 右端口径=有效宽，不是晴天 30
    # 主图/引擎同一右端：所有落点与空档不超过 24m
    for p in run["placements"]:
        assert p["end_m"] <= 24.0 + 1e-9
    for s in run["free_spans"]:
        assert s["end_m"] <= 24.0 + 1e-9


def test_rejected_set_differs_from_full_width(client):
    """相对晴天全长，雨天右端缩短后放不下集合可变。"""
    rainy = client.post("/api/allocate/run?segment_id=1").json()
    # 切回晴天全长 30m
    day_id = client.get("/api/days").json()[0]["id"]
    client.put(f"/api/days/{day_id}", json={"rainy": False, "rain_width_factor": None})
    sunny = client.post("/api/allocate/run?segment_id=1").json()
    assert sunny["segment"]["effective_width_m"] == 30.0
    assert rainy["segment"]["effective_width_m"] == 24.0
    # 晴天能放下更多（雨天放不下集合是其超集或等大；种子数据下严格更大）
    assert len(sunny["placements"]) >= len(rainy["placements"])


def test_invalid_or_missing_factor_is_rejected_and_state_kept(client):
    """系数非法 / 雨天未填系数：400 拒绝，库内保持改前；主图右端不半截缩短。"""
    day_id = client.get("/api/days").json()[0]["id"]
    for bad in (None, 1.5, -0.1):
        r = client.put(f"/api/days/{day_id}", json={"rainy": True, "rain_width_factor": bad})
        assert r.status_code == 400, (bad, r.status_code, r.text)
    # 系数 0 本身合法（0 到 1 闭区间）
    ok = client.put(f"/api/days/{day_id}", json={"rainy": True, "rain_width_factor": 0})
    assert ok.status_code == 200
    assert ok.json()["rain_width_factor"] == 0.0
    run = client.post("/api/allocate/run?segment_id=1").json()
    assert run["segment"]["effective_width_m"] == 0.0
    assert len(run["placements"]) == 0
    assert len(run["rejected"]) == 7


def test_non_rainy_ignores_factor(client):
    """非雨天忽略系数，按晴天全长（与绿仓一致）。"""
    day_id = client.get("/api/days").json()[0]["id"]
    r = client.put(f"/api/days/{day_id}", json={"rainy": False, "rain_width_factor": 0.8})
    assert r.status_code == 200
    assert r.json()["rain_width_factor"] is None
    run = client.post("/api/allocate/run?segment_id=1").json()
    assert run["segment"]["rainy"] is False
    assert run["segment"]["effective_width_m"] == 30.0


def test_old_run_right_end_not_rewritten_by_new_factor(client):
    """旧运行右端不得被新系数回刷：快照不可变。"""
    old = client.post("/api/allocate/run?segment_id=1").json()
    old_id, old_width = old["id"], old["segment"]["effective_width_m"]
    assert old_width == 24.0
    day_id = client.get("/api/days").json()[0]["id"]
    client.put(f"/api/days/{day_id}", json={"rainy": True, "rain_width_factor": 0.5})
    # 回看旧运行：右端仍是 24
    replay = client.get(f"/api/allocate/runs/{old_id}").json()
    assert replay["segment"]["effective_width_m"] == 24.0
    assert replay["segment"]["rain_width_factor"] == 0.8
    # 最新运行已经是新系数 15m
    new = client.post("/api/allocate/run?segment_id=1").json()
    assert new["segment"]["effective_width_m"] == 15.0
    again = client.get(f"/api/allocate/runs/{old_id}").json()
    assert again["segment"]["effective_width_m"] == 24.0
    listing = client.get("/api/allocate/runs?segment_id=1").json()
    widths = {row["id"]: row["effective_width_m"] for row in listing}
    assert widths[old_id] == 24.0


def test_rerun_uses_new_effective_width_no_stale_cache(client):
    """改系数后再分必须跟新有效宽，禁止吃改前缓存。"""
    day_id = client.get("/api/days").json()[0]["id"]
    client.put(f"/api/days/{day_id}", json={"rainy": True, "rain_width_factor": 0.5})
    run = client.post("/api/allocate/run?segment_id=1").json()
    assert run["segment"]["effective_width_m"] == 15.0
    latest = client.get("/api/allocate/latest?segment_id=1").json()
    assert latest["segment"]["effective_width_m"] == 15.0

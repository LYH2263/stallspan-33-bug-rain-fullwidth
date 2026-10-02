"""雨天缩宽的唯一有效宽度口径。

集日页、切空引擎、主图右端、放不下集合、运行抽屉都必须经这里取宽度，
禁止任何一方再按晴天全长自行计算。
"""
from __future__ import annotations

from app.models.models import MarketDay

# 系数允许的闭区间（题面：0 到 1）
def is_valid_factor(factor: float | None) -> bool:
    """合法系数：数值且 0 ≤ factor ≤ 1。系数 0 合法（有效宽 0，全部放不下）。"""
    if factor is None:
        return False
    try:
        f = float(factor)
    except (TypeError, ValueError):
        return False
    # NaN 防呆
    if f != f:
        return False
    return f >= -1e-9 and f <= 1.0 + 1e-9


class InvalidRainFactorError(ValueError):
    """雨天为真但系数缺失/非法。保存接口会拦截；运行接口见到此状态拒绝出图。"""


def effective_width(registered_width_m: float, day: MarketDay | None) -> float:
    """街段在当前集日设置下真正参与分配的宽度——全局唯一口径。

    - 非雨天（或集日缺失）：忽略系数，按晴天全长（与绿仓/登记宽度一致）。
    - 雨天且系数合法：登记宽度 * 系数，四舍五入到毫米避免浮点尾巴。
    - 雨天但系数缺失/非法：该状态本应在集日保存时被拒绝；若脏数据溜进来，
      这里抛错而*不是*回退晴天全长——严禁在雨天下按晴天全长出图/出放不下。
    """
    width = float(registered_width_m)
    if day is not None and day.rainy:
        if not is_valid_factor(day.rain_width_factor):
            raise InvalidRainFactorError("雨天集日缺少合法的有效宽度系数（需 0 到 1 之间）")
        return round(width * float(day.rain_width_factor), 3)
    return width

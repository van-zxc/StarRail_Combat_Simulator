from __future__ import annotations

"""引擎配置表 — 可在不修改引擎代码的情况下调整数值。

不确定项标注 `# TODO(#17): 待社区实测确认`，对应文档 §17。
"""

from core.enums import ActionType, PathType

# ── 削韧值 ──
TOUGHNESS_DAMAGE: dict[ActionType, float] = {
    ActionType.BASIC_ATTACK: 10.0,
    ActionType.SKILL: 20.0,
    ActionType.ULTIMATE: 20.0,
    ActionType.FOLLOW_UP: 10.0,
}

# ── 基础回能 ──
ENERGY_REGEN: dict[ActionType, float] = {
    ActionType.BASIC_ATTACK: 20.0,
    ActionType.ENHANCED_BASIC: 30.0,
    ActionType.SKILL: 30.0,
    ActionType.ULTIMATE: 5.0,
    ActionType.FOLLOW_UP: 0.0,
}
ENERGY_ON_KILL: float = 10.0
# TODO(#17): 多段攻击返能时点 / beingHitBucket 分段尚不明确, 暂用固定值
ENERGY_ON_HIT: float = 10.0

# ── FUA 返能分类 (§17.2) ──
FOLLOW_UP_ENERGY: dict[int, float] = {
    1: 0.0,
    2: 10.0,
    3: 10.0,
}

# ── SP 战技点 ──
SP_INITIAL: int = 3
SP_MAX: int = 5
SP_MIN: int = 0

# ── 基础仇恨 ──
BASE_AGGRO: dict[PathType, float] = {
    PathType.HUNT: 3,
    PathType.ERUDITION: 3,
    PathType.HARMONY: 4,
    PathType.NIHILITY: 4,
    PathType.ABUNDANCE: 4,
    PathType.REMEMBRANCE: 4,
    PathType.ELATION: 4,
    PathType.DESTRUCTION: 5,
    PathType.PRESERVATION: 6,
}

# ── 回合轮次 ──
CYCLE_0_DURATION: float = 150.0
CYCLE_DURATION: float = 100.0

# TODO(#17): AV 平手规则 (tie-breaker) 暂用 spawnOrder
TIMELINE_TIE_BREAKER: str = "spawn_order"

# ── 波次 ──
# TODO(#17): 换波 SP 继承仍需补录像实测
SP_CARRY_OVER_WAVES: bool = True

# ── 伏击 ──
AMBUSH_AV_DELAY: float = 20.0

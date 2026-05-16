"""March7th Eidolons — E1-E6 (from character_ranks.json)."""

from entities.base import StatModifier
from core.enums import StatModifierType, StatType


def e1_memory_of_you(owner) -> list[StatModifier]:
    """E1 记忆中的你: 终结技每冻结1个目标，恢复6点能量 (逻辑在终极技)。"""
    owner._has_e1 = True
    return []

def e2_memory_of_it(owner) -> list[StatModifier]:
    """E2 记忆中的它: 进入战斗时为最低 HP% 队友提供护盾 (DEF×24% + 320, 3回合)。"""
    owner._has_e2 = True
    return []

def e3_memory_of_all(owner) -> list[StatModifier]:
    """E3 记忆中的一切: 终结技 +2级, 普攻 +1级 (已满级, values from params diff)。"""
    # lv15→lv17 (cap 15): 终极技 multiplier 不变
    # lv10→lv11 (cap 10): 普攻 multiplier 不变
    # 当等级未满时: ult lv N→N+2 diff ≈ 0.30, basic lv N→N+1 diff ≈ 0.10
    ult = owner._skills.get("ultimate")
    basic = owner._skills.get("basic")
    if ult:
        ult.skill_multiplier += 0.30
    if basic:
        basic.skill_multiplier += 0.10
    return []

def e4_unwilling_to_lose(owner) -> list[StatModifier]:
    """E4 不愿再失去: 反击次数 +1, 反击伤害提高 DEF×30% (作为固定附加伤害)。"""
    owner._counter_max = 3
    owner._counter_used = 0
    # DEF×30% 固定值: 基础 DEF 304.2 + 22.5% trace + 其他装备
    # 动态读取 DEF 总值 × 0.30
    def_stat = owner.stats.get_total_stat(StatType.DEF)
    owner._e4_def_flat = def_stat * 0.30
    return []

def e5_unwilling_to_forget(owner) -> list[StatModifier]:
    """E5 不想再忘却: 战技 +2级, 天赋 +2级 (已满级, values from params diff)。"""
    # lv15→lv17 (cap 15): 战技护盾公式不变 (lv15=0.665 already max)
    # lv15→lv17 (cap 15): 天赋 lv N→N+2 diff ≈ 0.20
    talent = owner._skills.get("talent")
    if talent:
        talent.skill_multiplier += 0.20
    return []

def e6_just_like_this(owner) -> list[StatModifier]:
    """E6 就这样，一直…: 持盾者每回合开始回复 4% HP + 106 (逻辑在 TURN_START 监听)。"""
    owner._has_e6 = True
    return []


EIDOLON_REGISTRY: dict[int, callable] = {
    1: e1_memory_of_you,
    2: e2_memory_of_it,
    3: e3_memory_of_all,
    4: e4_unwilling_to_lose,
    5: e5_unwilling_to_forget,
    6: e6_just_like_this,
}

"""TemplateTraces — 行迹修饰器模板。

每个行迹为一个函数/类，接收角色引用，返回 StatModifier 列表。
角色 __init__ 中调用后通过 self.stats.add_modifier 挂载。
"""

from __future__ import annotations

from entities.base import StatModifier
from core.enums import StatModifierType, StatType


def trace_stat_bonus(owner: "BaseCharacter") -> list[StatModifier]:
    """属性加成行迹 (示例: ATK+10%)。

    角色构造时无条件挂载。
    """
    return [
        StatModifier(StatType.ATK, StatModifierType.PERCENT, 0.10, source="Trace_Stat"),
    ]


def trace_ascension_2(owner: "BaseCharacter") -> list[StatModifier]:
    """额外能力 1 (示例: 进战后 CRIT_RATE+5%)。

    仅在 unlocked_traces 包含 "A2" 时挂载。
    """
    return [
        StatModifier(StatType.CRIT_RATE, StatModifierType.FLAT, 0.05, source="Trace_A2"),
    ]


def trace_ascension_4(owner: "BaseCharacter") -> list[StatModifier]:
    """额外能力 2 (示例: DEF+20%)。"""
    return [
        StatModifier(StatType.DEF, StatModifierType.PERCENT, 0.20, source="Trace_A4"),
    ]


def trace_ascension_6(owner: "BaseCharacter") -> list[StatModifier]:
    """额外能力 3 (示例: DMG_BONUS+15%)。"""
    return [
        StatModifier(StatType.DMG_BONUS, StatModifierType.FLAT, 0.15, source="Trace_A6"),
    ]


# 行迹注册表: 标签 → 函数
TRACE_REGISTRY: dict[str, callable] = {
    "stat": trace_stat_bonus,
    "A2": trace_ascension_2,
    "A4": trace_ascension_4,
    "A6": trace_ascension_6,
}

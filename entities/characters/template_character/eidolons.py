"""TemplateEidolons — 星魂修饰器模板。

每个星魂为一个函数，接收角色引用，返回 StatModifier 列表。
按 eidolon_level 整数决定挂载 E1~E6。
"""

from __future__ import annotations

from entities.base import StatModifier
from core.enums import StatModifierType, StatType


def eidolon_1(owner: "BaseCharacter") -> list[StatModifier]:
    """E1 示例: 战技增伤 10%。"""
    return [
        StatModifier(StatType.SKILL_DMG, StatModifierType.FLAT, 0.10, source="E1"),
    ]


def eidolon_2(owner: "BaseCharacter") -> list[StatModifier]:
    """E2 示例: ATK+15%。"""
    return [
        StatModifier(StatType.ATK, StatModifierType.PERCENT, 0.15, source="E2"),
    ]


def eidolon_3(owner: "BaseCharacter") -> list[StatModifier]:
    """E3 示例: 战技等级+2 (技能倍率提升)。"""
    skill = owner._skills.get("skill")
    if skill:
        skill.skill_multiplier += 0.30  # +30% 倍率
    return []


def eidolon_4(owner: "BaseCharacter") -> list[StatModifier]:
    """E4 示例: HP+10%。"""
    return [
        StatModifier(StatType.HP, StatModifierType.PERCENT, 0.10, source="E4"),
    ]


def eidolon_5(owner: "BaseCharacter") -> list[StatModifier]:
    """E5 示例: 终结技等级+2。"""
    ult = owner._skills.get("ultimate")
    if ult:
        ult.skill_multiplier += 0.40
    return []


def eidolon_6(owner: "BaseCharacter") -> list[StatModifier]:
    """E6 示例: 全属性增伤 20%。"""
    return [
        StatModifier(StatType.DMG_BONUS, StatModifierType.FLAT, 0.20, source="E6"),
    ]


# 星魂注册表: 等级 → 函数
EIDOLON_REGISTRY: dict[int, callable] = {
    1: eidolon_1, 2: eidolon_2, 3: eidolon_3,
    4: eidolon_4, 5: eidolon_5, 6: eidolon_6,
}

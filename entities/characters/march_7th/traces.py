from __future__ import annotations

"""March7th Traces — 冰伤+22.4%, 防御+22.5%, 效果抵抗+10%, 3 bonus abilities。

来源: character_skill_trees.json
  冰伤: 1001201(3.2%) 1001203(3.2%) 1001205(4.8%) 1001208(4.8%) 1001209(6.4%) = 22.4%
  防御: 1001202(5%)   1001207(7.5%) 1001210(10%) = 22.5%
  抵抗: 1001204(4%)   1001206(6%) = 10%
"""

from entities.base import StatModifier
from core.enums import StatModifierType, StatType


def trace_ice_dmg_1(owner) -> list[StatModifier]:
    return [StatModifier(StatType.ICE_DMG_BONUS, StatModifierType.FLAT, 0.032, source="Trace_Ice1")]

def trace_ice_dmg_2(owner) -> list[StatModifier]:
    return [StatModifier(StatType.ICE_DMG_BONUS, StatModifierType.FLAT, 0.032, source="Trace_Ice2")]

def trace_ice_dmg_3(owner) -> list[StatModifier]:
    return [StatModifier(StatType.ICE_DMG_BONUS, StatModifierType.FLAT, 0.048, source="Trace_Ice3")]

def trace_ice_dmg_4(owner) -> list[StatModifier]:
    return [StatModifier(StatType.ICE_DMG_BONUS, StatModifierType.FLAT, 0.048, source="Trace_Ice4")]

def trace_ice_dmg_5(owner) -> list[StatModifier]:
    return [StatModifier(StatType.ICE_DMG_BONUS, StatModifierType.FLAT, 0.064, source="Trace_Ice5")]

def trace_def_1(owner) -> list[StatModifier]:
    return [StatModifier(StatType.DEF, StatModifierType.PERCENT, 0.05, source="Trace_DEF1")]

def trace_def_2(owner) -> list[StatModifier]:
    return [StatModifier(StatType.DEF, StatModifierType.PERCENT, 0.075, source="Trace_DEF2")]

def trace_def_3(owner) -> list[StatModifier]:
    return [StatModifier(StatType.DEF, StatModifierType.PERCENT, 0.10, source="Trace_DEF3")]

def trace_res_1(owner) -> list[StatModifier]:
    return [StatModifier(StatType.EFFECT_RES, StatModifierType.FLAT, 0.04, source="Trace_RES1")]

def trace_res_2(owner) -> list[StatModifier]:
    return [StatModifier(StatType.EFFECT_RES, StatModifierType.FLAT, 0.06, source="Trace_RES2")]

# Bonus abilities — 逻辑在技能类中处理
def trace_cleanse(owner) -> list[StatModifier]:
    return []

def trace_shield_plus(owner) -> list[StatModifier]:
    return []

def trace_freeze_plus(owner) -> list[StatModifier]:
    return []


TRACE_REGISTRY: dict[str, callable] = {
    "Ice1": trace_ice_dmg_1, "Ice2": trace_ice_dmg_2,
    "Ice3": trace_ice_dmg_3, "Ice4": trace_ice_dmg_4, "Ice5": trace_ice_dmg_5,
    "DEF1": trace_def_1, "DEF2": trace_def_2, "DEF3": trace_def_3,
    "RES1": trace_res_1, "RES2": trace_res_2,
    "Cleanse": trace_cleanse, "ShieldPlus": trace_shield_plus,
    "FreezePlus": trace_freeze_plus,
}

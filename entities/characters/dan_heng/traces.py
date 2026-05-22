from __future__ import annotations

"""DanHeng Traces — 风伤+22.4%, 攻击+18%, 防御+12.5%, 3 bonus abilities。

来源: 1002_danheng.json traces.stat_bonuses + traces.ability_bonuses
"""

from entities.base import StatModifier
from core.enums import StatModifierType, StatType


def trace_wind_1(owner) -> list[StatModifier]:
    return [StatModifier(StatType.WIND_DMG_BONUS, StatModifierType.FLAT, 0.032, source="Trace_Wind1")]

def trace_wind_2(owner) -> list[StatModifier]:
    return [StatModifier(StatType.WIND_DMG_BONUS, StatModifierType.FLAT, 0.032, source="Trace_Wind2")]

def trace_wind_3(owner) -> list[StatModifier]:
    return [StatModifier(StatType.WIND_DMG_BONUS, StatModifierType.FLAT, 0.048, source="Trace_Wind3")]

def trace_wind_4(owner) -> list[StatModifier]:
    return [StatModifier(StatType.WIND_DMG_BONUS, StatModifierType.FLAT, 0.048, source="Trace_Wind4")]

def trace_wind_5(owner) -> list[StatModifier]:
    return [StatModifier(StatType.WIND_DMG_BONUS, StatModifierType.FLAT, 0.064, source="Trace_Wind5")]

def trace_atk_1(owner) -> list[StatModifier]:
    return [StatModifier(StatType.ATK, StatModifierType.PERCENT, 0.04, source="Trace_ATK1")]

def trace_atk_2(owner) -> list[StatModifier]:
    return [StatModifier(StatType.ATK, StatModifierType.PERCENT, 0.06, source="Trace_ATK2")]

def trace_atk_3(owner) -> list[StatModifier]:
    return [StatModifier(StatType.ATK, StatModifierType.PERCENT, 0.08, source="Trace_ATK3")]

def trace_def_1(owner) -> list[StatModifier]:
    return [StatModifier(StatType.DEF, StatModifierType.PERCENT, 0.05, source="Trace_DEF1")]

def trace_def_2(owner) -> list[StatModifier]:
    return [StatModifier(StatType.DEF, StatModifierType.PERCENT, 0.075, source="Trace_DEF2")]


def trace_dragon_hide(owner) -> list[StatModifier]:
    return []

def trace_shadow(owner) -> list[StatModifier]:
    return []

def trace_wind(owner) -> list[StatModifier]:
    return []


TRACE_REGISTRY: dict[str, callable] = {
    "Wind1": trace_wind_1, "Wind2": trace_wind_2,
    "Wind3": trace_wind_3, "Wind4": trace_wind_4, "Wind5": trace_wind_5,
    "ATK1": trace_atk_1, "ATK2": trace_atk_2, "ATK3": trace_atk_3,
    "DEF1": trace_def_1, "DEF2": trace_def_2,
    "DragonHide": trace_dragon_hide, "Shadow": trace_shadow, "Wind": trace_wind,
}

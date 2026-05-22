from __future__ import annotations

"""Herta Traces — 冰伤+22.4%, 防御+22.5%, 暴击+6.7%, 3 bonus abilities.

来源: 1013_herta.json traces.stat_bonuses + traces.ability_bonuses
"""

from entities.base import StatModifier
from core.enums import StatModifierType, StatType


def trace_ice_1(owner) -> list[StatModifier]:
    return [StatModifier(StatType.ICE_DMG_BONUS, StatModifierType.FLAT, 0.032, source="Trace_Ice1")]

def trace_def_1(owner) -> list[StatModifier]:
    return [StatModifier(StatType.DEF, StatModifierType.PERCENT, 0.05, source="Trace_DEF1")]

def trace_ice_2(owner) -> list[StatModifier]:
    return [StatModifier(StatType.ICE_DMG_BONUS, StatModifierType.FLAT, 0.032, source="Trace_Ice2")]

def trace_cr_1(owner) -> list[StatModifier]:
    return [StatModifier(StatType.CRIT_RATE, StatModifierType.FLAT, 0.027, source="Trace_CR1")]

def trace_ice_3(owner) -> list[StatModifier]:
    return [StatModifier(StatType.ICE_DMG_BONUS, StatModifierType.FLAT, 0.048, source="Trace_Ice3")]

def trace_def_2(owner) -> list[StatModifier]:
    return [StatModifier(StatType.DEF, StatModifierType.PERCENT, 0.075, source="Trace_DEF2")]

def trace_ice_4(owner) -> list[StatModifier]:
    return [StatModifier(StatType.ICE_DMG_BONUS, StatModifierType.FLAT, 0.048, source="Trace_Ice4")]

def trace_cr_2(owner) -> list[StatModifier]:
    return [StatModifier(StatType.CRIT_RATE, StatModifierType.FLAT, 0.04, source="Trace_CR2")]

def trace_def_3(owner) -> list[StatModifier]:
    return [StatModifier(StatType.DEF, StatModifierType.PERCENT, 0.10, source="Trace_DEF3")]

def trace_ice_5(owner) -> list[StatModifier]:
    return [StatModifier(StatType.ICE_DMG_BONUS, StatModifierType.FLAT, 0.064, source="Trace_Ice5")]


def trace_efficiency(owner) -> list[StatModifier]:
    return []

def trace_puppet(owner) -> list[StatModifier]:
    return [StatModifier(StatType.EFFECT_RES, StatModifierType.FLAT, 0.35, source="Trace_Puppet")]

def trace_freeze(owner) -> list[StatModifier]:
    return []


TRACE_REGISTRY: dict[str, callable] = {
    "Ice1": trace_ice_1, "DEF1": trace_def_1, "Ice2": trace_ice_2,
    "CR1": trace_cr_1, "Ice3": trace_ice_3, "DEF2": trace_def_2,
    "Ice4": trace_ice_4, "CR2": trace_cr_2, "DEF3": trace_def_3,
    "Ice5": trace_ice_5,
    "Efficiency": trace_efficiency, "Puppet": trace_puppet, "Freeze": trace_freeze,
}

from __future__ import annotations

"""Asta Traces.

来源: 1009_asta.json traces (stat_bonuses + ability_bonuses)
"""

from entities.base import StatModifier
from core.enums import StatModifierType, StatType


def trace_fire_dmg_32(owner) -> list[StatModifier]:
    return [StatModifier(StatType.FIRE_DMG_BONUS, StatModifierType.FLAT, 0.032, source="Trace_FireDMG1")]

def trace_def_5(owner) -> list[StatModifier]:
    return [StatModifier(StatType.DEF, StatModifierType.PERCENT, 0.05, source="Trace_DEF5")]

def trace_fire_dmg_32b(owner) -> list[StatModifier]:
    return [StatModifier(StatType.FIRE_DMG_BONUS, StatModifierType.FLAT, 0.032, source="Trace_FireDMG2")]

def trace_crit_rate_27(owner) -> list[StatModifier]:
    return [StatModifier(StatType.CRIT_RATE, StatModifierType.FLAT, 0.027, source="Trace_CRIT27")]

def trace_fire_dmg_48(owner) -> list[StatModifier]:
    return [StatModifier(StatType.FIRE_DMG_BONUS, StatModifierType.FLAT, 0.048, source="Trace_FireDMG3")]

def trace_def_75(owner) -> list[StatModifier]:
    return [StatModifier(StatType.DEF, StatModifierType.PERCENT, 0.075, source="Trace_DEF75")]

def trace_fire_dmg_48b(owner) -> list[StatModifier]:
    return [StatModifier(StatType.FIRE_DMG_BONUS, StatModifierType.FLAT, 0.048, source="Trace_FireDMG4")]

def trace_crit_rate_40(owner) -> list[StatModifier]:
    return [StatModifier(StatType.CRIT_RATE, StatModifierType.FLAT, 0.04, source="Trace_CRIT40")]

def trace_def_10(owner) -> list[StatModifier]:
    return [StatModifier(StatType.DEF, StatModifierType.PERCENT, 0.10, source="Trace_DEF10")]

def trace_fire_dmg_64(owner) -> list[StatModifier]:
    return [StatModifier(StatType.FIRE_DMG_BONUS, StatModifierType.FLAT, 0.064, source="Trace_FireDMG5")]


def trace_spark(owner) -> list[StatModifier]:
    return []

def trace_ignite(owner) -> list[StatModifier]:
    return [StatModifier(StatType.FIRE_DMG_BONUS, StatModifierType.FLAT, 0.18, source="Trace_Ignite")]

def trace_constellation(owner) -> list[StatModifier]:
    return []


TRACE_REGISTRY: dict[str, callable] = {
    "FireDMG1": trace_fire_dmg_32, "DEF5": trace_def_5, "FireDMG2": trace_fire_dmg_32b,
    "CRIT27": trace_crit_rate_27, "FireDMG3": trace_fire_dmg_48, "DEF75": trace_def_75,
    "FireDMG4": trace_fire_dmg_48b, "CRIT40": trace_crit_rate_40, "DEF10": trace_def_10,
    "FireDMG5": trace_fire_dmg_64,
    "Spark": trace_spark, "Ignite": trace_ignite, "Constellation": trace_constellation,
}

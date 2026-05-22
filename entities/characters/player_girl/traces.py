from __future__ import annotations

"""PlayerGirl Traces — ATK+28%, HP+18%, DEF+12.5%, 3 bonus abilities。

来源: 8002_playergirl.json traces.stat_bonuses + traces.ability_bonuses
"""

from entities.base import StatModifier
from core.enums import StatModifierType, StatType


def trace_atk_1(owner) -> list[StatModifier]:
    return [StatModifier(StatType.ATK, StatModifierType.PERCENT, 0.04, source="Trace_ATK1")]

def trace_hp_1(owner) -> list[StatModifier]:
    return [StatModifier(StatType.HP, StatModifierType.PERCENT, 0.04, source="Trace_HP1")]

def trace_atk_2(owner) -> list[StatModifier]:
    return [StatModifier(StatType.ATK, StatModifierType.PERCENT, 0.04, source="Trace_ATK2")]

def trace_def_1(owner) -> list[StatModifier]:
    return [StatModifier(StatType.DEF, StatModifierType.PERCENT, 0.05, source="Trace_DEF1")]

def trace_atk_3(owner) -> list[StatModifier]:
    return [StatModifier(StatType.ATK, StatModifierType.PERCENT, 0.06, source="Trace_ATK3")]

def trace_hp_2(owner) -> list[StatModifier]:
    return [StatModifier(StatType.HP, StatModifierType.PERCENT, 0.06, source="Trace_HP2")]

def trace_atk_4(owner) -> list[StatModifier]:
    return [StatModifier(StatType.ATK, StatModifierType.PERCENT, 0.06, source="Trace_ATK4")]

def trace_def_2(owner) -> list[StatModifier]:
    return [StatModifier(StatType.DEF, StatModifierType.PERCENT, 0.075, source="Trace_DEF2")]

def trace_hp_3(owner) -> list[StatModifier]:
    return [StatModifier(StatType.HP, StatModifierType.PERCENT, 0.08, source="Trace_HP3")]

def trace_atk_5(owner) -> list[StatModifier]:
    return [StatModifier(StatType.ATK, StatModifierType.PERCENT, 0.08, source="Trace_ATK5")]


def trace_a2_energy(owner) -> list[StatModifier]:
    return []

def trace_tenacity(owner) -> list[StatModifier]:
    return []

def trace_fighting_spirit(owner) -> list[StatModifier]:
    return []


TRACE_REGISTRY: dict[str, callable] = {
    "ATK1": trace_atk_1, "HP1": trace_hp_1, "ATK2": trace_atk_2,
    "DEF1": trace_def_1, "ATK3": trace_atk_3, "HP2": trace_hp_2,
    "ATK4": trace_atk_4, "DEF2": trace_def_2, "HP3": trace_hp_3,
    "ATK5": trace_atk_5,
    "A2Energy": trace_a2_energy, "Tenacity": trace_tenacity,
    "FightingSpirit": trace_fighting_spirit,
}

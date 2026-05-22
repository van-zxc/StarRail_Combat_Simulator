from __future__ import annotations

"""Kafka Traces (Enhanced) — ATK+28%, 效果命中+18%, HP+10%, 3 bonus abilities。

来源: 1005_kafka.json traces (enhanced 11005xx stat_bonuses + ability_bonuses)
"""

from entities.base import StatModifier
from core.enums import StatModifierType, StatType


def trace_atk_1(owner) -> list[StatModifier]:
    return [StatModifier(StatType.ATK, StatModifierType.PERCENT, 0.04, source="Trace_ATK1")]

def trace_ehr_1(owner) -> list[StatModifier]:
    return [StatModifier(StatType.EFFECT_HIT_RATE, StatModifierType.FLAT, 0.04, source="Trace_EHR1")]

def trace_atk_2(owner) -> list[StatModifier]:
    return [StatModifier(StatType.ATK, StatModifierType.PERCENT, 0.04, source="Trace_ATK2")]

def trace_hp_1(owner) -> list[StatModifier]:
    return [StatModifier(StatType.HP, StatModifierType.PERCENT, 0.04, source="Trace_HP1")]

def trace_atk_3(owner) -> list[StatModifier]:
    return [StatModifier(StatType.ATK, StatModifierType.PERCENT, 0.06, source="Trace_ATK3")]

def trace_ehr_2(owner) -> list[StatModifier]:
    return [StatModifier(StatType.EFFECT_HIT_RATE, StatModifierType.FLAT, 0.06, source="Trace_EHR2")]

def trace_atk_4(owner) -> list[StatModifier]:
    return [StatModifier(StatType.ATK, StatModifierType.PERCENT, 0.06, source="Trace_ATK4")]

def trace_hp_2(owner) -> list[StatModifier]:
    return [StatModifier(StatType.HP, StatModifierType.PERCENT, 0.06, source="Trace_HP2")]

def trace_ehr_3(owner) -> list[StatModifier]:
    return [StatModifier(StatType.EFFECT_HIT_RATE, StatModifierType.FLAT, 0.08, source="Trace_EHR3")]

def trace_atk_5(owner) -> list[StatModifier]:
    return [StatModifier(StatType.ATK, StatModifierType.PERCENT, 0.08, source="Trace_ATK5")]


def trace_torture(owner) -> list[StatModifier]:
    return []

def trace_plunder(owner) -> list[StatModifier]:
    return []

def trace_thorn(owner) -> list[StatModifier]:
    return []


TRACE_REGISTRY: dict[str, callable] = {
    "ATK1": trace_atk_1, "EHR1": trace_ehr_1, "ATK2": trace_atk_2,
    "HP1": trace_hp_1,  "ATK3": trace_atk_3, "EHR2": trace_ehr_2,
    "ATK4": trace_atk_4, "HP2": trace_hp_2,  "EHR3": trace_ehr_3,
    "ATK5": trace_atk_5,
    "Torture": trace_torture, "Plunder": trace_plunder, "Thorn": trace_thorn,
}

from __future__ import annotations

"""Arlan Traces.

来源: 1008_arlan.json traces (stat_bonuses + ability_bonuses)
"""

from entities.base import StatModifier
from core.enums import StatModifierType, StatType


# ── Stat Bonuses ──

def trace_atk_4(owner) -> list[StatModifier]:
    return [StatModifier(StatType.ATK, StatModifierType.PERCENT, 0.04, source="Trace_ATK4")]

def trace_eff_res_4(owner) -> list[StatModifier]:
    return [StatModifier(StatType.EFFECT_RES, StatModifierType.FLAT, 0.04, source="Trace_EffRes4")]

def trace_atk_4b(owner) -> list[StatModifier]:
    return [StatModifier(StatType.ATK, StatModifierType.PERCENT, 0.04, source="Trace_ATK4b")]

def trace_hp_4(owner) -> list[StatModifier]:
    return [StatModifier(StatType.HP, StatModifierType.PERCENT, 0.04, source="Trace_HP4")]

def trace_atk_6(owner) -> list[StatModifier]:
    return [StatModifier(StatType.ATK, StatModifierType.PERCENT, 0.06, source="Trace_ATK6")]

def trace_eff_res_6(owner) -> list[StatModifier]:
    return [StatModifier(StatType.EFFECT_RES, StatModifierType.FLAT, 0.06, source="Trace_EffRes6")]

def trace_atk_6b(owner) -> list[StatModifier]:
    return [StatModifier(StatType.ATK, StatModifierType.PERCENT, 0.06, source="Trace_ATK6b")]

def trace_hp_6(owner) -> list[StatModifier]:
    return [StatModifier(StatType.HP, StatModifierType.PERCENT, 0.06, source="Trace_HP6")]

def trace_eff_res_8(owner) -> list[StatModifier]:
    return [StatModifier(StatType.EFFECT_RES, StatModifierType.FLAT, 0.08, source="Trace_EffRes8")]

def trace_atk_8(owner) -> list[StatModifier]:
    return [StatModifier(StatType.ATK, StatModifierType.PERCENT, 0.08, source="Trace_ATK8")]


# ── Ability Bonuses (逻辑在技能/天赋中判断) ──

def trace_revival(owner) -> list[StatModifier]:
    return []

def trace_endurance(owner) -> list[StatModifier]:
    return [
        StatModifier(StatType.DEBUFF_RES_BLEED, StatModifierType.FLAT, 0.50, source="Trace_Endurance"),
        StatModifier(StatType.DEBUFF_RES_BURN, StatModifierType.FLAT, 0.50, source="Trace_Endurance"),
        StatModifier(StatType.DEBUFF_RES_SHOCK, StatModifierType.FLAT, 0.50, source="Trace_Endurance"),
        StatModifier(StatType.DEBUFF_RES_WIND_SHEAR, StatModifierType.FLAT, 0.50, source="Trace_Endurance"),
    ]

def trace_repel(owner) -> list[StatModifier]:
    return []


TRACE_REGISTRY: dict[str, callable] = {
    "ATK4": trace_atk_4, "EffRes4": trace_eff_res_4, "ATK4b": trace_atk_4b,
    "HP4": trace_hp_4, "ATK6": trace_atk_6, "EffRes6": trace_eff_res_6,
    "ATK6b": trace_atk_6b, "HP6": trace_hp_6, "EffRes8": trace_eff_res_8,
    "ATK8": trace_atk_8,
    "Revival": trace_revival, "Endurance": trace_endurance, "Repel": trace_repel,
}

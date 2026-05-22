from __future__ import annotations

"""Silver Wolf Traces (Enhanced 11006xx).

来源: 1006_silverwolf.json traces (stat_bonuses + ability_bonuses)
"""

from entities.base import StatModifier
from core.enums import StatModifierType, StatType


# ── Stat Bonuses ──

def trace_atk_4(owner) -> list[StatModifier]:
    return [StatModifier(StatType.ATK, StatModifierType.PERCENT, 0.04, source="Trace_ATK4")]

def trace_ehr_4(owner) -> list[StatModifier]:
    return [StatModifier(StatType.EFFECT_HIT_RATE, StatModifierType.FLAT, 0.04, source="Trace_EHR4")]

def trace_atk_4b(owner) -> list[StatModifier]:
    return [StatModifier(StatType.ATK, StatModifierType.PERCENT, 0.04, source="Trace_ATK4b")]

def trace_quantum_dmg_32(owner) -> list[StatModifier]:
    return [StatModifier(StatType.QUANTUM_DMG_BONUS, StatModifierType.FLAT, 0.032, source="Trace_QuantumDMG")]

def trace_atk_6(owner) -> list[StatModifier]:
    return [StatModifier(StatType.ATK, StatModifierType.PERCENT, 0.06, source="Trace_ATK6")]

def trace_ehr_6(owner) -> list[StatModifier]:
    return [StatModifier(StatType.EFFECT_HIT_RATE, StatModifierType.FLAT, 0.06, source="Trace_EHR6")]

def trace_atk_6b(owner) -> list[StatModifier]:
    return [StatModifier(StatType.ATK, StatModifierType.PERCENT, 0.06, source="Trace_ATK6b")]

def trace_quantum_dmg_48(owner) -> list[StatModifier]:
    return [StatModifier(StatType.QUANTUM_DMG_BONUS, StatModifierType.FLAT, 0.048, source="Trace_QuantumDMG2")]

def trace_ehr_8(owner) -> list[StatModifier]:
    return [StatModifier(StatType.EFFECT_HIT_RATE, StatModifierType.FLAT, 0.08, source="Trace_EHR8")]

def trace_atk_8(owner) -> list[StatModifier]:
    return [StatModifier(StatType.ATK, StatModifierType.PERCENT, 0.08, source="Trace_ATK8")]


# ── Ability Bonuses (逻辑在技能/天赋中判断) ──

def trace_generate(owner) -> list[StatModifier]:
    return []

def trace_inject(owner) -> list[StatModifier]:
    return []

def trace_annotation(owner) -> list[StatModifier]:
    return []


TRACE_REGISTRY: dict[str, callable] = {
    "ATK4": trace_atk_4, "EHR4": trace_ehr_4, "ATK4b": trace_atk_4b,
    "QuantumDMG": trace_quantum_dmg_32,
    "ATK6": trace_atk_6, "EHR6": trace_ehr_6, "ATK6b": trace_atk_6b,
    "QuantumDMG2": trace_quantum_dmg_48,
    "EHR8": trace_ehr_8, "ATK8": trace_atk_8,
    "Generate": trace_generate, "Inject": trace_inject, "Annotation": trace_annotation,
}

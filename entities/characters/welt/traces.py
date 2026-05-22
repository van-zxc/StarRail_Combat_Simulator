from __future__ import annotations

"""Welt Traces (Enhanced) — 虚数伤+14.4%, 效果命中+28%, 效果抵抗+10%, 3 bonus abilities。

来源: 1004_welt.json traces (enhanced 11004xx stat_bonuses + ability_bonuses)
"""

from entities.base import StatModifier
from core.enums import StatModifierType, StatType


def trace_ehr_1(owner) -> list[StatModifier]:
    return [StatModifier(StatType.EFFECT_HIT_RATE, StatModifierType.FLAT, 0.04, source="Trace_EHR1")]

def trace_imag_1(owner) -> list[StatModifier]:
    return [StatModifier(StatType.IMAGINARY_DMG_BONUS, StatModifierType.FLAT, 0.032, source="Trace_IMAG1")]

def trace_ehr_2(owner) -> list[StatModifier]:
    return [StatModifier(StatType.EFFECT_HIT_RATE, StatModifierType.FLAT, 0.04, source="Trace_EHR2")]

def trace_res_1(owner) -> list[StatModifier]:
    return [StatModifier(StatType.EFFECT_RES, StatModifierType.FLAT, 0.04, source="Trace_RES1")]

def trace_ehr_3(owner) -> list[StatModifier]:
    return [StatModifier(StatType.EFFECT_HIT_RATE, StatModifierType.FLAT, 0.06, source="Trace_EHR3")]

def trace_imag_2(owner) -> list[StatModifier]:
    return [StatModifier(StatType.IMAGINARY_DMG_BONUS, StatModifierType.FLAT, 0.048, source="Trace_IMAG2")]

def trace_ehr_4(owner) -> list[StatModifier]:
    return [StatModifier(StatType.EFFECT_HIT_RATE, StatModifierType.FLAT, 0.06, source="Trace_EHR4")]

def trace_res_2(owner) -> list[StatModifier]:
    return [StatModifier(StatType.EFFECT_RES, StatModifierType.FLAT, 0.06, source="Trace_RES2")]

def trace_imag_3(owner) -> list[StatModifier]:
    return [StatModifier(StatType.IMAGINARY_DMG_BONUS, StatModifierType.FLAT, 0.064, source="Trace_IMAG3")]

def trace_ehr_5(owner) -> list[StatModifier]:
    return [StatModifier(StatType.EFFECT_HIT_RATE, StatModifierType.FLAT, 0.08, source="Trace_EHR5")]


def trace_retribution(owner) -> list[StatModifier]:
    return []

def trace_judgement(owner) -> list[StatModifier]:
    return []

def trace_verdict(owner) -> list[StatModifier]:
    return []


TRACE_REGISTRY: dict[str, callable] = {
    "EHR1": trace_ehr_1, "IMAG1": trace_imag_1, "EHR2": trace_ehr_2,
    "RES1": trace_res_1,  "EHR3": trace_ehr_3, "IMAG2": trace_imag_2,
    "EHR4": trace_ehr_4, "RES2": trace_res_2,  "IMAG3": trace_imag_3,
    "EHR5": trace_ehr_5,
    "Retribution": trace_retribution, "Judgement": trace_judgement,
    "Verdict": trace_verdict,
}

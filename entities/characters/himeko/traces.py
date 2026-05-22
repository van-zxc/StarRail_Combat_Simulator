from __future__ import annotations

"""Himeko Traces — 火伤+22.4%, 攻击+18%, 效果抵抗+10%, 3 bonus abilities。

来源: 1003_himeko.json traces.stat_bonuses + traces.ability_bonuses
"""

from entities.base import StatModifier
from core.enums import StatModifierType, StatType


def trace_fire_1(owner) -> list[StatModifier]:
    return [StatModifier(StatType.FIRE_DMG_BONUS, StatModifierType.FLAT, 0.032, source="Trace_Fire1")]

def trace_atk_1(owner) -> list[StatModifier]:
    return [StatModifier(StatType.ATK, StatModifierType.PERCENT, 0.04, source="Trace_ATK1")]

def trace_fire_2(owner) -> list[StatModifier]:
    return [StatModifier(StatType.FIRE_DMG_BONUS, StatModifierType.FLAT, 0.032, source="Trace_Fire2")]

def trace_res_1(owner) -> list[StatModifier]:
    return [StatModifier(StatType.EFFECT_RES, StatModifierType.FLAT, 0.04, source="Trace_RES1")]

def trace_fire_3(owner) -> list[StatModifier]:
    return [StatModifier(StatType.FIRE_DMG_BONUS, StatModifierType.FLAT, 0.048, source="Trace_Fire3")]

def trace_atk_2(owner) -> list[StatModifier]:
    return [StatModifier(StatType.ATK, StatModifierType.PERCENT, 0.06, source="Trace_ATK2")]

def trace_fire_4(owner) -> list[StatModifier]:
    return [StatModifier(StatType.FIRE_DMG_BONUS, StatModifierType.FLAT, 0.048, source="Trace_Fire4")]

def trace_res_2(owner) -> list[StatModifier]:
    return [StatModifier(StatType.EFFECT_RES, StatModifierType.FLAT, 0.06, source="Trace_RES2")]

def trace_atk_3(owner) -> list[StatModifier]:
    return [StatModifier(StatType.ATK, StatModifierType.PERCENT, 0.08, source="Trace_ATK3")]

def trace_fire_5(owner) -> list[StatModifier]:
    return [StatModifier(StatType.FIRE_DMG_BONUS, StatModifierType.FLAT, 0.064, source="Trace_Fire5")]


def trace_starfire(owner) -> list[StatModifier]:
    return []

def trace_scorch(owner) -> list[StatModifier]:
    return []

def trace_beacon(owner) -> list[StatModifier]:
    return []


TRACE_REGISTRY: dict[str, callable] = {
    "Fire1": trace_fire_1, "ATK1": trace_atk_1, "Fire2": trace_fire_2,
    "RES1": trace_res_1, "Fire3": trace_fire_3, "ATK2": trace_atk_2,
    "Fire4": trace_fire_4, "RES2": trace_res_2, "ATK3": trace_atk_3,
    "Fire5": trace_fire_5,
    "StarFire": trace_starfire, "Scorch": trace_scorch, "Beacon": trace_beacon,
}

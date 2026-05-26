from __future__ import annotations
"""乘区计算纯函数 — 每个乘区一个函数，签名统一。"""

import random
from typing import Optional

from core.enums import ActionType, DamageType, ElementType, StatType

# ActionType → 条件增伤 StatType 映射
_CONDITIONAL_DMG: dict[ActionType, StatType] = {
    ActionType.BASIC_ATTACK: StatType.BASIC_ATK_DMG,
    ActionType.SKILL: StatType.SKILL_DMG,
    ActionType.ULTIMATE: StatType.ULT_DMG,
}

# 元素击破基础伤害倍率
_ELEMENT_BREAK_DMG_MULT: dict[ElementType, float] = {
    ElementType.PHYSICAL: 2.0,
    ElementType.FIRE: 2.0,
    ElementType.ICE: 1.0,
    ElementType.LIGHTNING: 1.0,
    ElementType.WIND: 1.5,
    ElementType.QUANTUM: 0.5,
    ElementType.IMAGINARY: 0.5,
}

# ElementType → 元素专属易伤 StatType 映射
_ELEMENT_VULN_MAP: dict[ElementType, StatType] = {
    ElementType.FIRE: StatType.FIRE_VULN,
    ElementType.ICE: StatType.ICE_VULN,
    ElementType.LIGHTNING: StatType.THUNDER_VULN,
    ElementType.PHYSICAL: StatType.PHYSICAL_VULN,
    ElementType.WIND: StatType.WIND_VULN,
    ElementType.QUANTUM: StatType.QUANTUM_VULN,
    ElementType.IMAGINARY: StatType.IMAGINARY_VULN,
}


# ── 增伤乘区 ──

def damage_bonus_multiplier(attacker: "Character") -> float:
    """通用增伤乘区: 1.0 + DMG_BONUS (不含条件增伤/动作标签过滤)。"""
    return 1.0 + attacker.stats.get_total_stat(StatType.DMG_BONUS)


def apply_dmg_bonus(
    dmg: int,
    attacker: "Fighter",
    target: object = None,
    action_type: ActionType | None = None,
    damage_type: DamageType | None = None,
    tags: set[str] | None = None,
    element: ElementType | None = None,
) -> int:
    """增伤乘区: 1.0 + 通用增伤 + 元素专属增伤 + 条件增伤 (按 action_type 过滤)。

    ADDITIONAL_DMG 只享受通用增伤，不享受动作标签增伤和元素专属增伤。
    BREAK / SUPER_BREAK 不享受增伤。
    DoT 伤害额外加入 DOT_DMG 与 DMG_BONUS 加法叠加。
    """
    if damage_type in (DamageType.BREAK, DamageType.SUPER_BREAK):
        return dmg

    # 通用 + 元素专属 (ADDITIONAL_DMG 不享受元素专属)
    if damage_type == DamageType.ADDITIONAL_DMG or element is None:
        bonus = attacker.stats.get_total_stat(StatType.DMG_BONUS)
    else:
        bonus = attacker.stats.get_element_dmg_bonus(element)

    # DoT 专属增伤 (与 DMG_BONUS 加算)
    if damage_type == DamageType.DOT:
        bonus += attacker.stats.get_total_stat(StatType.DOT_DMG)

    if damage_type != DamageType.ADDITIONAL_DMG and action_type is not None:
        cond_stat = _CONDITIONAL_DMG.get(action_type)
        if cond_stat:
            bonus += attacker.stats.get_total_stat(cond_stat)

    if tags and "follow_up" in tags:
        bonus += attacker.stats.get_total_stat(StatType.FUA_DMG)

    return int(dmg * (1.0 + bonus))


# ── 易伤乘区 ──

def vulnerability_multiplier(defender: "Enemy", element: ElementType | None = None) -> float:
    """易伤乘区: 1.0 + VULNERABILITY + 元素专属易伤。"""
    total = 1.0 + defender.stats.get_total_stat(StatType.VULNERABILITY)
    if element is not None:
        vuln_stat = _ELEMENT_VULN_MAP.get(element)
        if vuln_stat is not None:
            total += defender.stats.get_total_stat(vuln_stat)
    return total


def apply_vulnerability(dmg: int, attacker: "Character", defender: "Enemy",
                        element: ElementType | None = None) -> int:
    return int(dmg * vulnerability_multiplier(defender, element))


# ── 弱化乘区 ──

def weaken_multiplier(defender: "Enemy") -> float:
    """弱化乘区: 1.0 - ΣWEAKEN。"""
    return 1.0 - defender.stats.get_total_stat(StatType.WEAKEN)


def apply_weaken(dmg: int, attacker: "Character", defender: "Enemy") -> int:
    return int(dmg * weaken_multiplier(defender))


# ── 防御减伤乘区 ──

def defense_multiplier(attacker: "Character", defender: "Enemy") -> float:
    """防御减伤乘区: attacker_base / (effective_def + attacker_base)。
    
    effective_def = DEF × (1 − DEF_REDUCTION − DEF_IGNORE), 减防与无视防御同桶。
    """
    attacker_base = attacker.level * 10 + 200
    defender_def = max(defender.stats.get_total_stat(StatType.DEF), 0.0)
    def_reduction = min(defender.stats.get_total_stat(StatType.DEF_REDUCTION), 1.0)
    def_ignore = max(attacker.stats.get_total_stat(StatType.DEF_IGNORE), 0.0) if hasattr(attacker, "stats") else 0.0
    total_reduction = min(def_reduction + def_ignore, 1.0)
    effective_def = defender_def * (1.0 - total_reduction)
    return attacker_base / (max(effective_def, 0.0) + attacker_base)


def apply_defense(dmg: int, attacker: "Character", defender: "Enemy") -> int:
    return int(dmg * defense_multiplier(attacker, defender))


# ── 抗性乘区 ──

def resistance_multiplier(
    attacker: "Character",
    defender: "Enemy",
    element_override: Optional[ElementType] = None,
) -> float:
    """抗性乘区: 1.0 - (enemy_res - attacker_pen)。

    支持: 自然弱点 / 植入弱点 / 全局 RES / per-element RES 修改。
    """
    element = element_override if element_override is not None else attacker.element
    # 检查自然弱点 + 植入弱点
    has_weakness = element in defender.weaknesses
    if not has_weakness and hasattr(defender, "implanted_weakness") and defender.implanted_weakness is not None:
        has_weakness = defender.implanted_weakness.element == element
    base_res = 0.0 if has_weakness else 0.2
    # 全局 RES + per-element RES 修改
    element_res_mod = 0.0
    if hasattr(defender, "element_res_modifiers"):
        element_res_mod = defender.element_res_modifiers.get(element, 0.0)
    enemy_res = base_res + defender.stats.get_total_stat(StatType.RES) + element_res_mod
    attacker_pen = attacker.stats.get_total_stat(StatType.RES_PEN)
    effective_res = max(-1.0, min(0.9, enemy_res - attacker_pen))
    return 1.0 - effective_res


def apply_resistance(
    dmg: int,
    attacker: "Character",
    defender: "Enemy",
    element_override: Optional[ElementType] = None,
) -> int:
    return int(dmg * resistance_multiplier(attacker, defender, element_override))


# ── 破韧乘区 ──

def toughness_multiplier(defender: "Enemy") -> float:
    """破韧乘区: 击破 1.0, 未击破 0.9。"""
    return 1.0 if defender.broken else 0.9


def apply_toughness(dmg: int, attacker: "Character", defender: "Enemy") -> int:
    return int(dmg * toughness_multiplier(defender))


# ── 减伤乘区 ──

def apply_mitigation(dmg: int, attacker: "Character", defender: "Enemy") -> int:
    """减伤乘区: Π(1 - m_i)，独立累乘。"""
    mult = 1.0
    for mv in defender.stats.get_mitigation_values():
        mult *= (1.0 - mv)
    return int(dmg * mult)


# ── 真实伤害乘区 ──

def apply_true_dmg(dmg: int, attacker: "Character", defender: "Enemy") -> int:
    """真实伤害乘区: 1.0 + ΣTRUE_DMG_BONUS。"""
    return int(dmg * (1.0 + attacker.stats.get_total_stat(StatType.TRUE_DMG_BONUS)))


# ── 击破特攻乘区 ──

def apply_break_effect(
    dmg: int,
    attacker: "Character",
    defender: "Enemy",
    break_effect_override: float | None = None,
) -> int:
    """击破特攻乘区: 1.0 + BREAK_EFFECT (或快照覆盖值)。"""
    be = break_effect_override if break_effect_override is not None else attacker.stats.get_total_stat(StatType.BREAK_EFFECT)
    return int(dmg * (1.0 + be))


# ── 击破增伤乘区 ──

def apply_break_dmg_increase(dmg: int, attacker: "Character", defender: "Enemy") -> int:
    """击破伤害提高: 1.0 + BREAK_DMG_INCREASE, 仅作用于 BREAK/SUPER_BREAK。"""
    return int(dmg * (1.0 + attacker.stats.get_total_stat(StatType.BREAK_DMG_INCREASE)))


# ── 暴击乘区 ──

def crit_multiplier(attacker: "Character") -> tuple[float, bool]:
    """暴击乘区: 判定 → (乘数, 是否暴击)。"""
    crit_rate = attacker.stats.get_total_stat(StatType.CRIT_RATE)
    is_crit = random.random() < crit_rate
    if is_crit:
        crit_dmg = attacker.stats.get_total_stat(StatType.CRIT_DMG)
        return (1.0 + crit_dmg, True)
    return (1.0, False)


def apply_crit(
    dmg: int, attacker: "Character", defender: "Enemy"
) -> tuple[int, bool]:
    mult, is_crit = crit_multiplier(attacker)
    return (int(dmg * mult), is_crit)


# ── 欢愉乘区 ──

def apply_elation_mult(dmg: int, attacker: "Character", defender: "Enemy") -> int:
    return int(dmg * (1.0 + attacker.stats.get_total_stat(StatType.ELATION)))


def apply_punchline_mult(
    dmg: int, attacker: "Character", defender: "Enemy", *,
    state: "GameState | None" = None,
) -> int:
    punchline = state.punchline if state else 0
    if punchline > 0:
        mult = 1.0 + (punchline * 5.0) / (punchline + 240.0)
    else:
        mult = 1.0
    return int(dmg * mult)


def apply_merrymake_mult(dmg: int, attacker: "Character", defender: "Enemy") -> int:
    return int(dmg * (1.0 + attacker.stats.get_total_stat(StatType.MERRYMAKE)))


def apply_elation_vuln(dmg: int, attacker: "Character", defender: "Enemy",
                       element: ElementType | None = None) -> int:
    vuln = defender.stats.get_total_stat(StatType.VULNERABILITY)
    if element is not None:
        vuln_stat = _ELEMENT_VULN_MAP.get(element)
        if vuln_stat is not None:
            vuln += defender.stats.get_total_stat(vuln_stat)
    elation_vuln = defender.stats.get_total_stat(StatType.ELATION_VULN)
    return int(dmg * (1.0 + vuln + elation_vuln))

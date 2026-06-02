from __future__ import annotations
"""enemy_pipeline — 敌人→角色伤害管道。"""

import random
from typing import Optional

from core.enums import ElementType, StatType


def compute_enemy_damage(
    enemy: "BaseEnemy",
    skill: "EnemySkill",
    target: "Character",
) -> int:
    base = int(enemy.atk * skill.multiplier)
    if base <= 0:
        return 0

    dmg = float(base)

    dmg = _resistance_mult(dmg, skill.element, target)
    dmg = _defense_mult(dmg, enemy.level, target)
    dmg = _vuln_mult(dmg, target, skill.element)
    dmg = _weaken_mult(dmg, target)
    dmg = _damage_bonus_mult(dmg, enemy)
    dmg = _crit_mult(dmg, enemy)

    return int(max(dmg, 0))


def _resistance_mult(dmg: float, element: ElementType | None, target: "Character") -> float:
    res = target.stats.get_total_stat(StatType.RES) if hasattr(target, "stats") else 0.0
    return dmg * (1.0 - min(max(res, -1.0), 0.9))


def _defense_mult(dmg: float, attacker_level: int, target: "Character") -> float:
    attacker_base = attacker_level * 10 + 200
    defender_def = max(target.stats.get_total_stat(StatType.DEF), 0.0)
    def_reduction = min(target.stats.get_total_stat(StatType.DEF_REDUCTION), 1.0)
    effective_def = defender_def * (1.0 - def_reduction)
    return dmg * attacker_base / (max(effective_def, 0.0) + attacker_base)


def _vuln_mult(dmg: float, target: "Character", element: ElementType | None) -> float:
    if not hasattr(target, "stats"):
        return dmg
    from core.damage.multipliers import _ELEMENT_VULN_MAP
    total = 1.0 + target.stats.get_total_stat(StatType.VULNERABILITY)
    if element is not None:
        vuln_stat = _ELEMENT_VULN_MAP.get(element)
        if vuln_stat is not None:
            total += target.stats.get_total_stat(vuln_stat)
    return dmg * total


def _weaken_mult(dmg: float, target: "Character") -> float:
    if not hasattr(target, "stats"):
        return dmg
    weaken = target.stats.get_total_stat(StatType.WEAKEN)
    return dmg * (1.0 - weaken)


def _damage_bonus_mult(dmg: float, enemy: "BaseEnemy") -> float:
    bonus = enemy.stats.get_total_stat(StatType.DMG_BONUS)
    return dmg * (1.0 + bonus)


def _crit_mult(dmg: float, enemy: "BaseEnemy") -> float:
    rate = enemy.crit_rate
    if rate <= 0.0:
        return dmg
    roll = random.random()
    if roll < rate:
        return dmg * (1.0 + enemy.crit_dmg)
    return dmg

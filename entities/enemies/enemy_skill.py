from __future__ import annotations
"""EnemySkill — 敌人技能 + 可组合效果系统。"""

from dataclasses import dataclass, field
from typing import Optional

from core.enums import ActionType, ElementType, StatType, StatModifierType


@dataclass
class EnemySkill:
    skill_id: str
    name: str = ""
    multiplier: float = 1.0
    element: ElementType = ElementType.PHYSICAL
    targeting: str = "single"
    cooldown: int = 0
    energy_gain: float = 10.0
    energy_cost: float = 0.0
    effects: list[SkillEffect] = field(default_factory=list)
    _current_cooldown: int = 0

    @property
    def available(self) -> bool:
        return self._current_cooldown == 0

    def start_cooldown(self) -> None:
        self._current_cooldown = self.cooldown

    def tick_cooldown(self) -> None:
        if self._current_cooldown > 0:
            self._current_cooldown -= 1


# ── 技能效果基类 ──

@dataclass
class SkillEffect:
    pass


@dataclass
class DamageEffect(SkillEffect):
    extra_multiplier: float = 0.0
    element: Optional[ElementType] = None


@dataclass
class DebuffEffect(SkillEffect):
    stat_type: StatType = StatType.DEF
    modifier_type: StatModifierType = StatModifierType.PERCENT
    value: float = 0.0
    base_chance: float = 1.0
    duration: int = 2


@dataclass
class DoTEffect(SkillEffect):
    element: ElementType = ElementType.PHYSICAL
    dot_multiplier: float = 0.0
    duration: int = 2
    base_chance: float = 1.0


@dataclass
class BuffEffect(SkillEffect):
    stat_type: StatType = StatType.ATK
    modifier_type: StatModifierType = StatModifierType.PERCENT
    value: float = 0.0
    duration: int = 2


@dataclass
class HealEffect(SkillEffect):
    multiplier: float = 0.0
    flat_amount: float = 0.0


@dataclass
class ShieldEffect(SkillEffect):
    multiplier: float = 0.0
    flat_amount: float = 0.0
    duration: int = 3
    block_once: bool = False


@dataclass
class SummonEffect(SkillEffect):
    enemy_template: str = ""
    count: int = 1


@dataclass
class DispelEffect(SkillEffect):
    target: str = "target"
    count: int = 1

from __future__ import annotations
"""论剑 (Swordplay) — 4★ 巡猎光锥。

特效: 多次击中同一目标时每次伤害提高#1[i]%（最多#2[i]层），目标变化解除。
     （方案B: 每次命中叠1层）
"""

from typing import Optional

from entities.light_cones.base import BaseLightCone
from entities.base import EquipmentEffect, StatModifier


class Swordplay(BaseLightCone):
    _default_id = "21010"
    _default_name = "论剑"
    _default_path_key = "Rogue"

    _PROMOTIONS = [
        {"hp_base": 43.2, "hp_step": 6.48, "atk_base": 21.6, "atk_step": 3.24, "def_base": 15, "def_step": 2.25},
        {"hp_base": 95.04, "hp_step": 6.48, "atk_base": 47.52, "atk_step": 3.24, "def_base": 33, "def_step": 2.25},
        {"hp_base": 164.16, "hp_step": 6.48, "atk_base": 82.08, "atk_step": 3.24, "def_base": 57, "def_step": 2.25},
        {"hp_base": 233.28, "hp_step": 6.48, "atk_base": 116.64, "atk_step": 3.24, "def_base": 81, "def_step": 2.25},
        {"hp_base": 302.4, "hp_step": 6.48, "atk_base": 151.2, "atk_step": 3.24, "def_base": 105, "def_step": 2.25},
        {"hp_base": 371.52, "hp_step": 6.48, "atk_base": 185.76, "atk_step": 3.24, "def_base": 129, "def_step": 2.25},
        {"hp_base": 440.64, "hp_step": 6.48, "atk_base": 220.32, "atk_step": 3.24, "def_base": 153, "def_step": 2.25},
    ]

    def __init__(self, id: str = "", **kwargs):
        super().__init__(id=id, **kwargs)
        if self.effect is None:
            self.effect = SwordplayEffect(self.superimpose)


class SwordplayEffect(EquipmentEffect):
    _PARAMS = [[0.08, 5], [0.10, 5], [0.12, 5], [0.14, 5], [0.16, 5]]
    _SOURCE = "LightCone_21010"

    def __init__(self, superimpose: int = 1) -> None:
        self.superimpose = max(1, min(superimpose, 5))
        self._character: Optional["Character"] = None
        self._current_target_name: Optional[str] = None
        self._hit_count: int = 0
        self._cb_hit: Optional[callable] = None

    def on_equip(self, character: "Character") -> None:
        pass

    def on_combat_start(self, state: "GameState", character: "Character") -> None:
        from core.events import EventType

        self._character = character
        self._cb_hit = lambda **kw: self._on_hit(kw.get("source"), kw.get("target"))
        state.event_bus.subscribe(EventType.ON_HIT, self._cb_hit)

    def _recalc_modifier(self) -> None:
        from core.enums import StatType, StatModifierType

        p = self._PARAMS[self.superimpose - 1]
        per_stack = p[0]
        max_stacks = p[1]
        stacks = min(self._hit_count, max_stacks)
        if stacks > 0:
            mod = StatModifier(
                stat_type=StatType.DMG_BONUS,
                modifier_type=StatModifierType.PERCENT,
                value=per_stack * stacks,
                source=self._SOURCE,
                dispellable=False,
            )
            self._character.stats.apply_modifier(mod, "refresh")
        else:
            self._character.stats.purge_source(self._SOURCE)

    def _on_hit(self, source: "Character", target: "Fighter") -> None:
        if source is not self._character:
            return
        if target is None:
            return
        # TODO: 使用 target.name 比较无法区分同种不同怪物个体。
        # 当怪物系统支持身份标识(id/UUID)后, 改为按 identity 比较。
        if self._current_target_name is None or target.name != self._current_target_name:
            self._current_target_name = target.name
            self._hit_count = 1
        else:
            self._hit_count += 1
        self._recalc_modifier()

    def on_unequip(self, character: "Character") -> None:
        from core.events import EventType

        character.stats.purge_source(self._SOURCE)
        if self._cb_hit is not None and character.event_bus is not None:
            character.event_bus.unsubscribe(EventType.ON_HIT, self._cb_hit)

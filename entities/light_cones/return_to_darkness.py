from __future__ import annotations
"""重返幽冥 (Return to Darkness) — 4★ 巡猎光锥。

特效: 暴击率提高#1[i]%。暴击后有#2[i]%的固定概率解除被攻击目标1个增益（每攻击1次）。

JSON对齐: OnAfterHitAll:IsDamageCritical+RandomChance → DispelStatus (全部命中后一次性判定).
Python: ACTION_START:set_flag + ON_HIT:Crit→dispel (per-hit判定, _can_dispel gate 防重复)."""

from typing import Optional

from entities.light_cones.base import BaseLightCone
from entities.base import EquipmentEffect, StatModifier


class ReturnToDarkness(BaseLightCone):
    _default_id = "21031"
    _default_name = "重返幽冥"
    _default_path_key = "Rogue"

    _PROMOTIONS = [
        {"hp_base": 38.4, "hp_step": 5.76, "atk_base": 24, "atk_step": 3.6, "def_base": 15, "def_step": 2.25},
        {"hp_base": 84.48, "hp_step": 5.76, "atk_base": 52.8, "atk_step": 3.6, "def_base": 33, "def_step": 2.25},
        {"hp_base": 145.92, "hp_step": 5.76, "atk_base": 91.2, "atk_step": 3.6, "def_base": 57, "def_step": 2.25},
        {"hp_base": 207.36, "hp_step": 5.76, "atk_base": 129.6, "atk_step": 3.6, "def_base": 81, "def_step": 2.25},
        {"hp_base": 268.8, "hp_step": 5.76, "atk_base": 168, "atk_step": 3.6, "def_base": 105, "def_step": 2.25},
        {"hp_base": 330.24, "hp_step": 5.76, "atk_base": 206.4, "atk_step": 3.6, "def_base": 129, "def_step": 2.25},
        {"hp_base": 391.68, "hp_step": 5.76, "atk_base": 244.8, "atk_step": 3.6, "def_base": 153, "def_step": 2.25},
    ]

    def __init__(self, id: str = "", **kwargs):
        super().__init__(id=id, **kwargs)
        if self.effect is None:
            self.effect = ReturnToDarknessEffect(self.superimpose)


class ReturnToDarknessEffect(EquipmentEffect):
    _PARAMS = [[0.12, 0.16], [0.15, 0.20], [0.18, 0.24], [0.21, 0.28], [0.24, 0.32]]
    _SOURCE = "LightCone_21031"

    def __init__(self, superimpose: int = 1) -> None:
        self.superimpose = max(1, min(superimpose, 5))
        self._character: Optional["Character"] = None
        self._state: Optional["GameState"] = None
        self._triggered_this_action: bool = False
        self._cb_action_start: Optional[callable] = None
        self._cb_hit: Optional[callable] = None

    def on_equip(self, character: "Character") -> None:
        from core.enums import StatType, StatModifierType

        cr_val = self._PARAMS[self.superimpose - 1][0]
        mod = StatModifier(
            stat_type=StatType.CRIT_RATE,
            modifier_type=StatModifierType.PERCENT,
            value=cr_val,
            source=self._SOURCE,
            dispellable=False,
        )
        character.stats.apply_modifier(mod, "refresh")

    def on_combat_start(self, state: "GameState", character: "Character") -> None:
        from core.events import EventType

        self._character = character
        self._state = state
        self._cb_action_start = lambda **kw: self._on_action_start(kw.get("unit"))
        self._cb_hit = lambda **kw: self._on_hit(kw.get("source"), kw.get("target"), kw.get("is_crit"))
        state.event_bus.subscribe(EventType.ACTION_START, self._cb_action_start)
        state.event_bus.subscribe(EventType.ON_HIT, self._cb_hit)

    def _on_action_start(self, unit: "Character") -> None:
        if unit is self._character:
            self._triggered_this_action = False

    def _on_hit(self, source: "Character", target: "Fighter", is_crit: bool) -> None:
        if source is not self._character:
            return
        if self._triggered_this_action:
            return
        if target is None or not hasattr(target, "stats"):
            return
        if not is_crit:
            return
        import random

        pct = self._PARAMS[self.superimpose - 1][1]
        if random.random() >= pct:
            return
        self._triggered_this_action = True
        self._state.dispel_one_buff(target)

    def on_unequip(self, character: "Character") -> None:
        from core.events import EventType

        character.stats.purge_source(self._SOURCE)
        if character.event_bus is not None:
            if self._cb_action_start is not None:
                character.event_bus.unsubscribe(EventType.ACTION_START, self._cb_action_start)
            if self._cb_hit is not None:
                character.event_bus.unsubscribe(EventType.ON_HIT, self._cb_hit)

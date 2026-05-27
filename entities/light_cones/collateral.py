from __future__ import annotations
"""Collateral (物穰) — 3★ 丰饶光锥。

特效: 装备者施放战技和终结技时，治疗量提高#1[i]%。
"""

from typing import Optional

from entities.light_cones.base import BaseLightCone
from entities.base import EquipmentEffect, StatModifier


class Collateral(BaseLightCone):
    _default_id = "20001"
    _default_name = "物穰"
    _default_path_key = "Priest"

    _PROMOTIONS = [
        {"hp_base": 43.2, "hp_step": 6.48, "atk_base": 12, "atk_step": 1.8, "def_base": 12, "def_step": 1.8},
        {"hp_base": 95.04, "hp_step": 6.48, "atk_base": 26.4, "atk_step": 1.8, "def_base": 26.4, "def_step": 1.8},
        {"hp_base": 164.16, "hp_step": 6.48, "atk_base": 45.6, "atk_step": 1.8, "def_base": 45.6, "def_step": 1.8},
        {"hp_base": 233.28, "hp_step": 6.48, "atk_base": 64.8, "atk_step": 1.8, "def_base": 64.8, "def_step": 1.8},
        {"hp_base": 302.4, "hp_step": 6.48, "atk_base": 84, "atk_step": 1.8, "def_base": 84, "def_step": 1.8},
        {"hp_base": 371.52, "hp_step": 6.48, "atk_base": 103.2, "atk_step": 1.8, "def_base": 103.2, "def_step": 1.8},
        {"hp_base": 440.64, "hp_step": 6.48, "atk_base": 122.4, "atk_step": 1.8, "def_base": 122.4, "def_step": 1.8},
    ]

    def __init__(self, id: str = "", **kwargs):
        super().__init__(id=id, **kwargs)
        if self.effect is None:
            self.effect = CollateralEffect(self.superimpose)


class CollateralEffect(EquipmentEffect):
    _PARAMS = [
        [0.12],
        [0.15],
        [0.18],
        [0.21],
        [0.24],
    ]
    _SOURCE = "LightCone_20001"

    def __init__(self, superimpose: int = 1) -> None:
        self.superimpose = max(1, min(superimpose, 5))
        self._character: Optional["Character"] = None
        self._callback: Optional[callable] = None

    def on_equip(self, character: "Character") -> None:
        pass

    def on_combat_start(self, state: "GameState", character: "Character") -> None:
        from core.events import EventType

        self._character = character
        self._callback = lambda **kw: self._on_action_start(kw.get("unit"), kw.get("action_type"))
        state.event_bus.subscribe(EventType.ACTION_START, self._callback)

    def _on_action_start(self, unit, action_type) -> None:
        if unit is not self._character:
            return
        from core.enums import ActionType, StatType, StatModifierType

        if action_type not in (ActionType.SKILL, ActionType.ULTIMATE):
            return

        p = self._PARAMS[self.superimpose - 1]
        mod = StatModifier(
            stat_type=StatType.OUTGOING_HEALING_BOOST,
            modifier_type=StatModifierType.PERCENT,
            value=p[0],
            source=self._SOURCE,
            duration=1,
            dispellable=False,
        )
        self._character.stats.apply_modifier(mod, "refresh")

    def on_unequip(self, character: "Character") -> None:
        from core.events import EventType

        character.stats.purge_source(self._SOURCE)
        if self._callback is not None and character.event_bus is not None:
            character.event_bus.unsubscribe(EventType.ACTION_START, self._callback)

from __future__ import annotations
"""与行星相会 (Planetary Rendezvous) — 4★ 同谐光锥。

特效: 进入战斗后，我方目标造成与装备者相同属性的伤害时伤害提高#1[i]%。
"""

from typing import Optional

from entities.light_cones.base import BaseLightCone
from entities.base import EquipmentEffect, StatModifier


class PlanetaryRendezvous(BaseLightCone):
    _default_id = "21011"
    _default_name = "与行星相会"
    _default_path_key = "Shaman"

    _PROMOTIONS = [
        {"hp_base": 48, "hp_step": 7.2, "atk_base": 19.2, "atk_step": 2.88, "def_base": 15, "def_step": 2.25},
        {"hp_base": 105.6, "hp_step": 7.2, "atk_base": 42.24, "atk_step": 2.88, "def_base": 33, "def_step": 2.25},
        {"hp_base": 182.4, "hp_step": 7.2, "atk_base": 72.96, "atk_step": 2.88, "def_base": 57, "def_step": 2.25},
        {"hp_base": 259.2, "hp_step": 7.2, "atk_base": 103.68, "atk_step": 2.88, "def_base": 81, "def_step": 2.25},
        {"hp_base": 336, "hp_step": 7.2, "atk_base": 134.4, "atk_step": 2.88, "def_base": 105, "def_step": 2.25},
        {"hp_base": 412.8, "hp_step": 7.2, "atk_base": 165.12, "atk_step": 2.88, "def_base": 129, "def_step": 2.25},
        {"hp_base": 489.6, "hp_step": 7.2, "atk_base": 195.84, "atk_step": 2.88, "def_base": 153, "def_step": 2.25},
    ]

    def __init__(self, id: str = "", **kwargs):
        super().__init__(id=id, **kwargs)
        if self.effect is None:
            self.effect = PlanetaryRendezvousEffect(self.superimpose)


class PlanetaryRendezvousEffect(EquipmentEffect):
    _PARAMS = [0.12, 0.15, 0.18, 0.21, 0.24]
    _SOURCE = "LightCone_21011"

    def __init__(self, superimpose: int = 1) -> None:
        self.superimpose = max(1, min(superimpose, 5))
        self._character: Optional["Character"] = None
        self._state: Optional["GameState"] = None
        self._cb_action_start: Optional[callable] = None
        self._cb_after: Optional[callable] = None

    def on_equip(self, character: "Character") -> None:
        pass

    def on_combat_start(self, state: "GameState", character: "Character") -> None:
        from core.events import EventType

        self._character = character
        self._state = state
        self._cb_action_start = lambda **kw: self._on_action_start(kw.get("unit"))
        self._cb_after = lambda **kw: self._on_after()
        bus = state.event_bus
        bus.subscribe(EventType.ACTION_START, self._cb_action_start)
        bus.subscribe(EventType.AFTER_ACTION, self._cb_after)

    def _on_action_start(self, unit: "Character") -> None:
        if unit is None or not hasattr(unit, "element"):
            return
        if unit.element == self._character.element:
            from core.enums import StatType, StatModifierType

            dmg_val = self._PARAMS[self.superimpose - 1]
            mod = StatModifier(
                stat_type=StatType.DMG_BONUS,
                modifier_type=StatModifierType.PERCENT,
                value=dmg_val,
                source=self._SOURCE,
                dispellable=False,
            )
            unit.stats.apply_modifier(mod, "refresh")

    def _on_after(self) -> None:
        if self._state is None:
            return
        for char in self._state.characters:
            if hasattr(char, "stats"):
                char.stats.purge_source(self._SOURCE)

    def on_unequip(self, character: "Character") -> None:
        from core.events import EventType

        self._on_after()
        if character.event_bus is not None:
            bus = character.event_bus
            if self._cb_action_start is not None:
                bus.unsubscribe(EventType.ACTION_START, self._cb_action_start)
            if self._cb_after is not None:
                bus.unsubscribe(EventType.AFTER_ACTION, self._cb_after)

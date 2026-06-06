from __future__ import annotations
"""同一种心情 (Shared Feeling) — 4★ 丰饶光锥。

特效: 治疗量提高#1[i]%，施放战技时为我方全体恢复#2[f1]点能量。
"""

from typing import Optional

from entities.light_cones.base import BaseLightCone
from entities.base import EquipmentEffect, StatModifier


class SharedFeeling(BaseLightCone):
    _default_id = "21007"
    _default_name = "同一种心情"
    _default_path_key = "Priest"

    _PROMOTIONS = [
        {"hp_base": 43.2, "hp_step": 6.48, "atk_base": 19.2, "atk_step": 2.88, "def_base": 18, "def_step": 2.7},
        {"hp_base": 95.04, "hp_step": 6.48, "atk_base": 42.24, "atk_step": 2.88, "def_base": 39.6, "def_step": 2.7},
        {"hp_base": 164.16, "hp_step": 6.48, "atk_base": 72.96, "atk_step": 2.88, "def_base": 68.4, "def_step": 2.7},
        {"hp_base": 233.28, "hp_step": 6.48, "atk_base": 103.68, "atk_step": 2.88, "def_base": 97.2, "def_step": 2.7},
        {"hp_base": 302.4, "hp_step": 6.48, "atk_base": 134.4, "atk_step": 2.88, "def_base": 126, "def_step": 2.7},
        {"hp_base": 371.52, "hp_step": 6.48, "atk_base": 165.12, "atk_step": 2.88, "def_base": 154.8, "def_step": 2.7},
        {"hp_base": 440.64, "hp_step": 6.48, "atk_base": 195.84, "atk_step": 2.88, "def_base": 183.6, "def_step": 2.7},
    ]

    def __init__(self, id: str = "", **kwargs):
        super().__init__(id=id, **kwargs)
        if self.effect is None:
            self.effect = SharedFeelingEffect(self.superimpose)


class SharedFeelingEffect(EquipmentEffect):
    _PARAMS = [[0.10, 2], [0.125, 2.5], [0.15, 3], [0.175, 3.5], [0.20, 4]]
    _SOURCE = "LightCone_21007"

    def __init__(self, superimpose: int = 1) -> None:
        self.superimpose = max(1, min(superimpose, 5))
        self._character: Optional["Character"] = None
        self._state: Optional["GameState"] = None
        self._cb_after: Optional[callable] = None

    def on_equip(self, character: "Character") -> None:
        from core.enums import StatType, StatModifierType

        pct = self._PARAMS[self.superimpose - 1][0]
        mod = StatModifier(
            stat_type=StatType.OUTGOING_HEALING_BOOST,
            modifier_type=StatModifierType.PERCENT,
            value=pct,
            source=self._SOURCE,
            dispellable=False,
        )
        character.stats.apply_modifier(mod, "refresh")

    def on_combat_start(self, state: "GameState", character: "Character") -> None:
        from core.events import EventType

        self._character = character
        self._state = state
        self._cb_after = lambda **kw: self._on_after(kw.get("unit"), kw.get("action_type"))
        state.event_bus.subscribe(EventType.AFTER_ACTION, self._cb_after)

    def _on_after(self, unit: "Character", action_type: object) -> None:
        from core.enums import ActionType

        if unit is not self._character:
            return
        if action_type != ActionType.SKILL:
            return
        energy = self._PARAMS[self.superimpose - 1][1]
        for char in self._state.characters:
            if not hasattr(char, "gain_energy"):
                continue
            if hasattr(char, "is_memosprite") and char.is_memosprite:
                continue
            char.gain_energy(energy, affected_by_err=False)  # JSON: ModifySPNew bypasses ERR

    def on_unequip(self, character: "Character") -> None:
        from core.events import EventType

        character.stats.purge_source(self._SOURCE)
        if self._cb_after is not None and character.event_bus is not None:
            character.event_bus.unsubscribe(EventType.AFTER_ACTION, self._cb_after)

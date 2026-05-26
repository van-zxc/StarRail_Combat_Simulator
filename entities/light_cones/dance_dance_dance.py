from __future__ import annotations
"""舞！舞！舞！ (Dance! Dance! Dance!) — 4★ 同谐光锥。

特效: 施放终结技后，我方全体行动提前#1[i]%。
"""

from typing import Optional

from entities.light_cones.base import BaseLightCone
from entities.base import EquipmentEffect


class DanceDanceDance(BaseLightCone):
    _default_id = "21018"
    _default_name = "舞！舞！舞！"
    _default_path_key = "Shaman"

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
            self.effect = DanceDanceDanceEffect(self.superimpose)


class DanceDanceDanceEffect(EquipmentEffect):
    _PARAMS = [0.16, 0.18, 0.20, 0.22, 0.24]
    _SOURCE = "LightCone_21018"

    def __init__(self, superimpose: int = 1) -> None:
        self.superimpose = max(1, min(superimpose, 5))
        self._character: Optional["Character"] = None
        self._state: Optional["GameState"] = None
        self._cb_ult: Optional[callable] = None

    def on_equip(self, character: "Character") -> None:
        pass

    def on_combat_start(self, state: "GameState", character: "Character") -> None:
        from core.events import EventType

        self._character = character
        self._state = state
        self._cb_ult = lambda **kw: self._on_ult(kw.get("character"))
        state.event_bus.subscribe(EventType.ON_ULTIMATE_INSERTED, self._cb_ult)

    def _on_ult(self, caster: "Character") -> None:
        if caster is not self._character:
            return
        pct = self._PARAMS[self.superimpose - 1]
        for char in self._state.characters:
            if not hasattr(char, "advance_action"):
                continue
            if hasattr(char, "is_memosprite") and char.is_memosprite:
                continue
            char.advance_action(pct)

    def on_unequip(self, character: "Character") -> None:
        from core.events import EventType

        if self._cb_ult is not None and character.event_bus is not None:
            character.event_bus.unsubscribe(EventType.ON_ULTIMATE_INSERTED, self._cb_ult)

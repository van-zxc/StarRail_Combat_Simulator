from __future__ import annotations
"""蕃息 (Multiplication) — 3★ 丰饶光锥。

特效: 施放普攻后，使下一次行动提前#1[i]%。
"""

from typing import Optional

from entities.light_cones.base import BaseLightCone
from entities.base import EquipmentEffect


class Multiplication(BaseLightCone):
    _default_id = "20015"
    _default_name = "蕃息"
    _default_path_key = "Priest"

    _PROMOTIONS = [
        {"hp_base": 43.2, "hp_step": 6.48, "atk_base": 14.4, "atk_step": 2.16, "def_base": 9, "def_step": 1.35},
        {"hp_base": 95.04, "hp_step": 6.48, "atk_base": 31.68, "atk_step": 2.16, "def_base": 19.8, "def_step": 1.35},
        {"hp_base": 164.16, "hp_step": 6.48, "atk_base": 54.72, "atk_step": 2.16, "def_base": 34.2, "def_step": 1.35},
        {"hp_base": 233.28, "hp_step": 6.48, "atk_base": 77.76, "atk_step": 2.16, "def_base": 48.6, "def_step": 1.35},
        {"hp_base": 302.4, "hp_step": 6.48, "atk_base": 100.8, "atk_step": 2.16, "def_base": 63, "def_step": 1.35},
        {"hp_base": 371.52, "hp_step": 6.48, "atk_base": 123.84, "atk_step": 2.16, "def_base": 77.4, "def_step": 1.35},
        {"hp_base": 440.64, "hp_step": 6.48, "atk_base": 146.88, "atk_step": 2.16, "def_base": 91.8, "def_step": 1.35},
    ]

    def __init__(self, id: str = "", **kwargs):
        super().__init__(id=id, **kwargs)
        if self.effect is None:
            self.effect = MultiplicationEffect(self.superimpose)


class MultiplicationEffect(EquipmentEffect):
    _PARAMS = [0.12, 0.14, 0.16, 0.18, 0.20]
    _SOURCE = "LightCone_20015"

    def __init__(self, superimpose: int = 1) -> None:
        self.superimpose = max(1, min(superimpose, 5))
        self._character: Optional["Character"] = None
        self._cb_after: Optional[callable] = None

    def on_equip(self, character: "Character") -> None:
        pass

    def on_combat_start(self, state: "GameState", character: "Character") -> None:
        from core.events import EventType

        self._character = character
        self._cb_after = lambda **kw: self._on_after(kw.get("unit"), kw.get("action_type"))
        state.event_bus.subscribe(EventType.AFTER_ACTION, self._cb_after)

    def _on_after(self, unit: "Character", action_type: object) -> None:
        from core.enums import ActionType

        if unit is not self._character:
            return
        if action_type != ActionType.BASIC_ATTACK:
            return
        pct = self._PARAMS[self.superimpose - 1]
        self._character.advance_action(pct)

    def on_unequip(self, character: "Character") -> None:
        from core.events import EventType

        if self._cb_after is not None and character.event_bus is not None:
            character.event_bus.unsubscribe(EventType.AFTER_ACTION, self._cb_after)

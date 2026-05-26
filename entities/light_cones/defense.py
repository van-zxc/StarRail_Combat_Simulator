from __future__ import annotations
"""戍御 (Defense) — 3★ 存护光锥。

特效: 施放终结技时，回复等同于自身生命上限#1[i]%的生命值。
"""

from typing import Optional

from entities.light_cones.base import BaseLightCone
from entities.base import EquipmentEffect


class Defense(BaseLightCone):
    _default_id = "20010"
    _default_name = "戍御"
    _default_path_key = "Knight"

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
            self.effect = DefenseEffect(self.superimpose)


class DefenseEffect(EquipmentEffect):
    _PARAMS = [0.18, 0.21, 0.24, 0.27, 0.30]
    _SOURCE = "LightCone_20010"

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
        self._state.calculate_and_apply_heal(
            healer=self._character,
            target=self._character,
            base_stat_amount=self._character.max_hp,
            percentage=pct,
        )

    def on_unequip(self, character: "Character") -> None:
        from core.events import EventType

        if self._cb_ult is not None and character.event_bus is not None:
            character.event_bus.unsubscribe(EventType.ON_ULTIMATE_INSERTED, self._cb_ult)

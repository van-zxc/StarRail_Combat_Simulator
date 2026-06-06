from __future__ import annotations
"""灵钥 (Passkey) — 3★ 智识光锥。

特效: 施放战技后额外恢复#1[i]点能量，该效果单个回合内不可重复触发。
"""

from typing import Optional

from entities.light_cones.base import BaseLightCone
from entities.base import EquipmentEffect


class Passkey(BaseLightCone):
    _default_id = "20013"
    _default_name = "灵钥"
    _default_path_key = "Mage"

    _PROMOTIONS = [
        {"hp_base": 33.6, "hp_step": 5.04, "atk_base": 16.8, "atk_step": 2.52, "def_base": 12, "def_step": 1.8},
        {"hp_base": 73.92, "hp_step": 5.04, "atk_base": 36.96, "atk_step": 2.52, "def_base": 26.4, "def_step": 1.8},
        {"hp_base": 127.68, "hp_step": 5.04, "atk_base": 63.84, "atk_step": 2.52, "def_base": 45.6, "def_step": 1.8},
        {"hp_base": 181.44, "hp_step": 5.04, "atk_base": 90.72, "atk_step": 2.52, "def_base": 64.8, "def_step": 1.8},
        {"hp_base": 235.2, "hp_step": 5.04, "atk_base": 117.6, "atk_step": 2.52, "def_base": 84, "def_step": 1.8},
        {"hp_base": 288.96, "hp_step": 5.04, "atk_base": 144.48, "atk_step": 2.52, "def_base": 103.2, "def_step": 1.8},
        {"hp_base": 342.72, "hp_step": 5.04, "atk_base": 171.36, "atk_step": 2.52, "def_base": 122.4, "def_step": 1.8},
    ]

    def __init__(self, id: str = "", **kwargs):
        super().__init__(id=id, **kwargs)
        if self.effect is None:
            self.effect = PasskeyEffect(self.superimpose)


class PasskeyEffect(EquipmentEffect):
    _PARAMS = [8, 9, 10, 11, 12]
    _SOURCE = "LightCone_20013"

    def __init__(self, superimpose: int = 1) -> None:
        self.superimpose = max(1, min(superimpose, 5))
        self._character: Optional["Character"] = None
        self._triggered_this_turn: bool = False
        self._cb_turn_start: Optional[callable] = None
        self._cb_after: Optional[callable] = None

    def on_equip(self, character: "Character") -> None:
        pass

    def on_combat_start(self, state: "GameState", character: "Character") -> None:
        from core.events import EventType

        self._character = character
        self._cb_turn_start = lambda **kw: self._on_turn_start(kw.get("unit"))
        self._cb_after = lambda **kw: self._on_after(kw.get("unit"), kw.get("action_type"))
        bus = state.event_bus
        bus.subscribe(EventType.TURN_START, self._cb_turn_start)
        bus.subscribe(EventType.AFTER_ACTION, self._cb_after)

    def _on_turn_start(self, unit: "Fighter") -> None:
        if unit is self._character:
            self._triggered_this_turn = False

    def _on_after(self, unit: "Character", action_type: object) -> None:
        if unit is not self._character:
            return
        from core.enums import ActionType

        if action_type != ActionType.SKILL:
            return
        if self._triggered_this_turn:
            return
        self._triggered_this_turn = True
        energy = self._PARAMS[self.superimpose - 1]
        self._character.gain_energy(energy, affected_by_err=False)  # JSON: ModifySPNew bypasses ERR

    def on_unequip(self, character: "Character") -> None:
        from core.events import EventType

        if character.event_bus is not None:
            bus = character.event_bus
            if self._cb_turn_start is not None:
                bus.unsubscribe(EventType.TURN_START, self._cb_turn_start)
            if self._cb_after is not None:
                bus.unsubscribe(EventType.AFTER_ACTION, self._cb_after)

from __future__ import annotations
"""轮契 (Meshing Cogs) — 3★ 同谐光锥。

特效: 施放攻击或受到攻击后，额外恢复#1[i]点能量，该效果单个回合内不可重复触发。
"""

from typing import Optional

from entities.light_cones.base import BaseLightCone
from entities.base import EquipmentEffect


class MeshingCogs(BaseLightCone):
    _default_id = "20012"
    _default_name = "轮契"
    _default_path_key = "Shaman"

    _PROMOTIONS = [
        {"hp_base": 38.4, "hp_step": 5.76, "atk_base": 14.4, "atk_step": 2.16, "def_base": 12, "def_step": 1.8},
        {"hp_base": 84.48, "hp_step": 5.76, "atk_base": 31.68, "atk_step": 2.16, "def_base": 26.4, "def_step": 1.8},
        {"hp_base": 145.92, "hp_step": 5.76, "atk_base": 54.72, "atk_step": 2.16, "def_base": 45.6, "def_step": 1.8},
        {"hp_base": 207.36, "hp_step": 5.76, "atk_base": 77.76, "atk_step": 2.16, "def_base": 64.8, "def_step": 1.8},
        {"hp_base": 268.8, "hp_step": 5.76, "atk_base": 100.8, "atk_step": 2.16, "def_base": 84, "def_step": 1.8},
        {"hp_base": 330.24, "hp_step": 5.76, "atk_base": 123.84, "atk_step": 2.16, "def_base": 103.2, "def_step": 1.8},
        {"hp_base": 391.68, "hp_step": 5.76, "atk_base": 146.88, "atk_step": 2.16, "def_base": 122.4, "def_step": 1.8},
    ]

    def __init__(self, id: str = "", **kwargs):
        super().__init__(id=id, **kwargs)
        if self.effect is None:
            self.effect = MeshingCogsEffect(self.superimpose)


class MeshingCogsEffect(EquipmentEffect):
    _PARAMS = [4, 5, 6, 7, 8]
    _SOURCE = "LightCone_20012"

    def __init__(self, superimpose: int = 1) -> None:
        self.superimpose = max(1, min(superimpose, 5))
        self._character: Optional["Character"] = None
        self._triggered_this_turn: bool = False
        self._cb_turn_start: Optional[callable] = None
        self._cb_damage_dealt: Optional[callable] = None
        self._cb_hit: Optional[callable] = None

    def on_equip(self, character: "Character") -> None:
        pass

    def on_combat_start(self, state: "GameState", character: "Character") -> None:
        from core.events import EventType

        self._character = character
        self._cb_turn_start = lambda **kw: self._on_turn_start(kw.get("unit"))
        self._cb_damage_dealt = lambda **kw: self._on_damage_dealt(kw.get("source"))
        self._cb_hit = lambda **kw: self._on_hit(kw.get("target"))
        bus = state.event_bus
        bus.subscribe(EventType.TURN_START, self._cb_turn_start)
        bus.subscribe(EventType.ON_DAMAGE_DEALT, self._cb_damage_dealt)
        bus.subscribe(EventType.ON_HIT, self._cb_hit)

    def _on_turn_start(self, unit: "Fighter") -> None:
        if unit is self._character:
            self._triggered_this_turn = False

    def _on_damage_dealt(self, source: "Character") -> None:
        if source is not self._character:
            return
        if self._triggered_this_turn:
            return
        self._triggered_this_turn = True
        energy = self._PARAMS[self.superimpose - 1]
        self._character.gain_energy(energy)

    def _on_hit(self, target: "Fighter") -> None:
        if target is not self._character:
            return
        if self._triggered_this_turn:
            return
        self._triggered_this_turn = True
        energy = self._PARAMS[self.superimpose - 1]
        self._character.gain_energy(energy)

    def on_unequip(self, character: "Character") -> None:
        from core.events import EventType

        if character.event_bus is not None:
            bus = character.event_bus
            if self._cb_turn_start is not None:
                bus.unsubscribe(EventType.TURN_START, self._cb_turn_start)
            if self._cb_damage_dealt is not None:
                bus.unsubscribe(EventType.ON_DAMAGE_DEALT, self._cb_damage_dealt)
            if self._cb_hit is not None:
                bus.unsubscribe(EventType.ON_HIT, self._cb_hit)

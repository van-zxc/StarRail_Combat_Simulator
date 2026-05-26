from __future__ import annotations
"""等价交换 (Quid Pro Quo) — 4★ 丰饶光锥。

特效: 回合开始时，随机为1个能量百分比<#1[i]%的队友恢复#2[i]点能量。
"""

import random
from typing import Optional

from entities.light_cones.base import BaseLightCone
from entities.base import EquipmentEffect


class QuidProQuo(BaseLightCone):
    _default_id = "21021"
    _default_name = "等价交换"
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
            self.effect = QuidProQuoEffect(self.superimpose)


class QuidProQuoEffect(EquipmentEffect):
    _PARAMS = [[0.50, 8], [0.50, 10], [0.50, 12], [0.50, 14], [0.50, 16]]
    _SOURCE = "LightCone_21021"

    def __init__(self, superimpose: int = 1) -> None:
        self.superimpose = max(1, min(superimpose, 5))
        self._character: Optional["Character"] = None
        self._state: Optional["GameState"] = None
        self._cb_turn_start: Optional[callable] = None

    def on_equip(self, character: "Character") -> None:
        pass

    def on_combat_start(self, state: "GameState", character: "Character") -> None:
        from core.events import EventType

        self._character = character
        self._state = state
        self._cb_turn_start = lambda **kw: self._on_turn_start(kw.get("unit"))
        state.event_bus.subscribe(EventType.TURN_START, self._cb_turn_start)

    def _on_turn_start(self, unit: "Fighter") -> None:
        if unit is not self._character:
            return
        p = self._PARAMS[self.superimpose - 1]
        threshold = p[0]
        energy = p[1]
        candidates = []
        for char in self._state.characters:
            if char is self._character:
                continue
            if hasattr(char, "is_memosprite") and char.is_memosprite:
                continue
            energy_pct = char.energy / char.max_energy if char.max_energy > 0 else 1.0
            if energy_pct < threshold:
                candidates.append(char)
        if candidates:
            target = random.choice(candidates)
            target.gain_energy(energy)

    def on_unequip(self, character: "Character") -> None:
        from core.events import EventType

        if self._cb_turn_start is not None and character.event_bus is not None:
            character.event_bus.unsubscribe(EventType.TURN_START, self._cb_turn_start)

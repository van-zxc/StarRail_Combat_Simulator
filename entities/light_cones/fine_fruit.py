from __future__ import annotations
"""嘉果 (Fine Fruit) — 3★ 丰饶光锥。

特效: 战斗开始时，立即为我方全体恢复#1[i]点能量。
"""

from typing import Optional

from entities.light_cones.base import BaseLightCone
from entities.base import EquipmentEffect


class FineFruit(BaseLightCone):
    _default_id = "20008"
    _default_name = "嘉果"
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
            self.effect = FineFruitEffect(self.superimpose)


class FineFruitEffect(EquipmentEffect):
    _PARAMS = [6, 7.5, 9, 10.5, 12]
    _SOURCE = "LightCone_20008"

    def __init__(self, superimpose: int = 1) -> None:
        self.superimpose = max(1, min(superimpose, 5))
        self._character: Optional["Character"] = None
        self._cb_start: Optional[callable] = None

    def on_equip(self, character: "Character") -> None:
        pass

    def on_combat_start(self, state: "GameState", character: "Character") -> None:
        from core.events import EventType

        self._character = character
        self._cb_start = lambda **kw: self._on_start(state)
        state.event_bus.subscribe(EventType.BATTLE_START, self._cb_start)

    def _on_start(self, state: "GameState") -> None:
        energy = self._PARAMS[self.superimpose - 1]
        for char in state.characters:
            if hasattr(char, "is_memosprite") and char.is_memosprite:
                continue
            if not hasattr(char, "gain_energy"):
                continue
            char.gain_energy(energy, affected_by_err=False)  # JSON: ModifySPNew bypasses ERR

    def on_unequip(self, character: "Character") -> None:
        from core.events import EventType

        if self._cb_start is not None and character.event_bus is not None:
            character.event_bus.unsubscribe(EventType.BATTLE_START, self._cb_start)

from __future__ import annotations
"""调和 (Mediation) — 3★ 同谐光锥。

特效: 进入战斗时，我方全体速度提高#1[i]点，持续#2[i]回合。
"""

from typing import Optional

from entities.light_cones.base import BaseLightCone
from entities.base import EquipmentEffect, StatModifier


class Mediation(BaseLightCone):
    _default_id = "20019"
    _default_name = "调和"
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
            self.effect = MediationEffect(self.superimpose)


class MediationEffect(EquipmentEffect):
    _PARAMS = [[12, 1], [14, 1], [16, 1], [18, 1], [20, 1]]
    _SOURCE = "LightCone_20019"

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
        from core.enums import StatType, StatModifierType

        spd_val = self._PARAMS[self.superimpose - 1][0]
        duration = self._PARAMS[self.superimpose - 1][1]
        for char in state.characters:
            if hasattr(char, "is_memosprite") and char.is_memosprite:
                continue
            if not hasattr(char, "stats"):
                continue
            mod = StatModifier(
                stat_type=StatType.SPD,
                modifier_type=StatModifierType.FLAT,
                value=spd_val,
                source=self._SOURCE,
                duration=duration,
                dispellable=False,
            )
            char.stats.apply_modifier(mod, "refresh")

    def on_unequip(self, character: "Character") -> None:
        from core.events import EventType

        character.stats.purge_source(self._SOURCE)
        if self._cb_start is not None and character.event_bus is not None:
            character.event_bus.unsubscribe(EventType.BATTLE_START, self._cb_start)

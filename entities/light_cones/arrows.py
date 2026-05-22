from __future__ import annotations
"""Arrows (锋镝) — 3★ 巡猎光锥。

特效: 战斗开始时，使装备者的暴击率提高#1[i]%，持续#2[i]回合。
"""

from typing import Optional

from entities.light_cones.base import BaseLightCone
from entities.base import EquipmentEffect, StatModifier


class Arrows(BaseLightCone):
    _default_id = "20000"
    _default_name = "锋镝"
    _default_path_key = "Rogue"

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
        superimpose = kwargs.pop("superimpose", 1)
        if not isinstance(superimpose, int):
            superimpose = 1
        super().__init__(id=id, superimpose=superimpose, **kwargs)
        if self.effect is None:
            self.effect = ArrowsEffect(self.superimpose)


class ArrowsEffect(EquipmentEffect):
    _PARAMS = [
        [0.12, 3],
        [0.15, 3],
        [0.18, 3],
        [0.21, 3],
        [0.24, 3],
    ]
    _SOURCE = "LightCone_20000"

    def __init__(self, superimpose: int = 1) -> None:
        self.superimpose = max(1, min(superimpose, 5))
        self._character: Optional["Character"] = None
        self._callback: Optional[callable] = None

    def on_equip(self, character: "Character") -> None:
        pass

    def on_combat_start(self, state: "GameState", character: "Character") -> None:
        from core.events import EventType

        self._character = character
        self._callback = lambda **kw: self._on_battle_start()
        state.event_bus.subscribe(EventType.BATTLE_START, self._callback)

    def _on_battle_start(self) -> None:
        from core.enums import StatType, StatModifierType

        p = self._PARAMS[self.superimpose - 1]
        mod = StatModifier(
            stat_type=StatType.CRIT_RATE,
            modifier_type=StatModifierType.PERCENT,
            value=p[0],
            source=self._SOURCE,
            duration=int(p[1]),
            dispellable=False,
        )
        self._character.stats.apply_modifier(mod, "refresh")

    def on_unequip(self, character: "Character") -> None:
        from core.events import EventType

        character.stats.purge_source(self._SOURCE)
        if self._callback is not None and character.event_bus is not None:
            character.event_bus.unsubscribe(EventType.BATTLE_START, self._callback)

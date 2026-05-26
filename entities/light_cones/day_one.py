from __future__ import annotations
"""余生的第一天 (Day One of My New Life) — 4★ 存护光锥。

特效: 防御力提高#1[i]%。进入战斗后，全体全属性抗性提高#2[i]%。同类效果无法重复生效。
"""

from typing import Optional

from entities.light_cones.base import BaseLightCone
from entities.base import EquipmentEffect, StatModifier


class DayOne(BaseLightCone):
    _default_id = "21002"
    _default_name = "余生的第一天"
    _default_path_key = "Knight"

    _PROMOTIONS = [
        {"hp_base": 43.2, "hp_step": 6.48, "atk_base": 16.8, "atk_step": 2.52, "def_base": 21, "def_step": 3.15},
        {"hp_base": 95.04, "hp_step": 6.48, "atk_base": 36.96, "atk_step": 2.52, "def_base": 46.2, "def_step": 3.15},
        {"hp_base": 164.16, "hp_step": 6.48, "atk_base": 63.84, "atk_step": 2.52, "def_base": 79.8, "def_step": 3.15},
        {"hp_base": 233.28, "hp_step": 6.48, "atk_base": 90.72, "atk_step": 2.52, "def_base": 113.4, "def_step": 3.15},
        {"hp_base": 302.4, "hp_step": 6.48, "atk_base": 117.6, "atk_step": 2.52, "def_base": 147, "def_step": 3.15},
        {"hp_base": 371.52, "hp_step": 6.48, "atk_base": 144.48, "atk_step": 2.52, "def_base": 180.6, "def_step": 3.15},
        {"hp_base": 440.64, "hp_step": 6.48, "atk_base": 171.36, "atk_step": 2.52, "def_base": 214.2, "def_step": 3.15},
    ]

    def __init__(self, id: str = "", **kwargs):
        super().__init__(id=id, **kwargs)
        if self.effect is None:
            self.effect = DayOneEffect(self.superimpose)


class DayOneEffect(EquipmentEffect):
    _PARAMS = [[0.16, 0.08], [0.18, 0.09], [0.20, 0.10], [0.22, 0.11], [0.24, 0.12]]
    _SOURCE = "LightCone_21002"

    def __init__(self, superimpose: int = 1) -> None:
        self.superimpose = max(1, min(superimpose, 5))
        self._character: Optional["Character"] = None
        self._cb_start: Optional[callable] = None

    def on_equip(self, character: "Character") -> None:
        from core.enums import StatType, StatModifierType

        def_pct = self._PARAMS[self.superimpose - 1][0]
        mod = StatModifier(
            stat_type=StatType.DEF,
            modifier_type=StatModifierType.PERCENT,
            value=def_pct,
            source=self._SOURCE,
            dispellable=False,
        )
        character.stats.apply_modifier(mod, "refresh")

    def on_combat_start(self, state: "GameState", character: "Character") -> None:
        from core.events import EventType

        self._character = character
        self._cb_start = lambda **kw: self._on_start(state)
        state.event_bus.subscribe(EventType.BATTLE_START, self._cb_start)

    def _on_start(self, state: "GameState") -> None:
        if self._already_active(state):
            return
        from core.enums import StatType, StatModifierType

        res_pct = self._PARAMS[self.superimpose - 1][1]
        res_mod = StatModifier(
            stat_type=StatType.RES,
            modifier_type=StatModifierType.PERCENT,
            value=res_pct,
            source=self._SOURCE,
            dispellable=False,
        )
        for char in state.characters:
            if hasattr(char, "is_memosprite") and char.is_memosprite:
                continue
            if not hasattr(char, "stats"):
                continue
            char.stats.apply_modifier(res_mod, "refresh")

    def _already_active(self, state: "GameState") -> bool:
        for char in state.characters:
            if not hasattr(char, "stats"):
                continue
            for m in char.stats.active_modifiers:
                if m.source == self._SOURCE:
                    return True
        return False

    def on_unequip(self, character: "Character") -> None:
        from core.events import EventType

        character.stats.purge_source(self._SOURCE)
        if self._cb_start is not None and character.event_bus is not None:
            character.event_bus.unsubscribe(EventType.BATTLE_START, self._cb_start)

from __future__ import annotations
"""镂月裁云之意 (Carve the Moon, Weave the Clouds) — 4★ 同谐光锥。

特效: 战斗开始时及回合开始时，随机生效1个效果（ATK%/CRIT_DMG%/ERR%），
      替换上次效果且不与上次重复，同类效果无法叠加。
"""

import random
from typing import Optional

from entities.light_cones.base import BaseLightCone
from entities.base import EquipmentEffect, StatModifier


class CarveTheMoon(BaseLightCone):
    _default_id = "21032"
    _default_name = "镂月裁云之意"
    _default_path_key = "Shaman"

    _PROMOTIONS = [
        {"hp_base": 43.2, "hp_step": 6.48, "atk_base": 21.6, "atk_step": 3.24, "def_base": 15, "def_step": 2.25},
        {"hp_base": 95.04, "hp_step": 6.48, "atk_base": 47.52, "atk_step": 3.24, "def_base": 33, "def_step": 2.25},
        {"hp_base": 164.16, "hp_step": 6.48, "atk_base": 82.08, "atk_step": 3.24, "def_base": 57, "def_step": 2.25},
        {"hp_base": 233.28, "hp_step": 6.48, "atk_base": 116.64, "atk_step": 3.24, "def_base": 81, "def_step": 2.25},
        {"hp_base": 302.4, "hp_step": 6.48, "atk_base": 151.2, "atk_step": 3.24, "def_base": 105, "def_step": 2.25},
        {"hp_base": 371.52, "hp_step": 6.48, "atk_base": 185.76, "atk_step": 3.24, "def_base": 129, "def_step": 2.25},
        {"hp_base": 440.64, "hp_step": 6.48, "atk_base": 220.32, "atk_step": 3.24, "def_base": 153, "def_step": 2.25},
    ]

    def __init__(self, id: str = "", **kwargs):
        super().__init__(id=id, **kwargs)
        if self.effect is None:
            self.effect = CarveTheMoonEffect(self.superimpose)


class CarveTheMoonEffect(EquipmentEffect):
    _PARAMS = [[0.10, 0.12, 0.06], [0.125, 0.15, 0.075], [0.15, 0.18, 0.09], [0.175, 0.21, 0.105], [0.20, 0.24, 0.12]]
    _SOURCES = ["LightCone_21032_ATK", "LightCone_21032_CDMG", "LightCone_21032_ERR"]
    _EFFECT_LABELS = ["ATK", "CRIT_DMG", "ERR"]

    def __init__(self, superimpose: int = 1) -> None:
        self.superimpose = max(1, min(superimpose, 5))
        self._character: Optional["Character"] = None
        self._state: Optional["GameState"] = None
        self._last_choice: Optional[int] = None
        self._cb_start: Optional[callable] = None
        self._cb_turn_start: Optional[callable] = None

    def on_equip(self, character: "Character") -> None:
        pass

    def on_combat_start(self, state: "GameState", character: "Character") -> None:
        from core.events import EventType

        self._character = character
        self._state = state
        self._cb_start = lambda **kw: self._apply_random_effect()
        self._cb_turn_start = lambda **kw: self._on_turn_start(kw.get("unit"))
        bus = state.event_bus
        bus.subscribe(EventType.BATTLE_START, self._cb_start)
        bus.subscribe(EventType.TURN_START, self._cb_turn_start)

    def _on_turn_start(self, unit: "Fighter") -> None:
        if unit is not self._character:
            return
        self._apply_random_effect()

    def _apply_random_effect(self) -> None:
        if self._state is None:
            return

        choices = [0, 1, 2]
        if self._last_choice is not None and len(choices) > 1:
            choices.remove(self._last_choice)
        idx = random.choice(choices)
        self._last_choice = idx

        # Purge all three sources from all teammates
        for s in self._SOURCES:
            for char in self._state.characters:
                if hasattr(char, "stats"):
                    char.stats.purge_source(s)

        # Apply the chosen effect to all teammates
        from core.enums import StatType, StatModifierType

        p = self._PARAMS[self.superimpose - 1]
        stat_types = [StatType.ATK, StatType.CRIT_DMG, StatType.ERR]
        stat_type = stat_types[idx]
        value = p[idx]
        source = self._SOURCES[idx]

        mod = StatModifier(
            stat_type=stat_type,
            modifier_type=StatModifierType.PERCENT,
            value=value,
            source=source,
            dispellable=False,
        )
        for char in self._state.characters:
            if hasattr(char, "is_memosprite") and char.is_memosprite:
                continue
            if not hasattr(char, "stats"):
                continue
            char.stats.apply_modifier(mod, "refresh")

    def on_unequip(self, character: "Character") -> None:
        from core.events import EventType

        for s in self._SOURCES:
            character.stats.purge_source(s)
        if character.event_bus is not None:
            bus = character.event_bus
            if self._cb_start is not None:
                bus.unsubscribe(EventType.BATTLE_START, self._cb_start)
            if self._cb_turn_start is not None:
                bus.unsubscribe(EventType.TURN_START, self._cb_turn_start)

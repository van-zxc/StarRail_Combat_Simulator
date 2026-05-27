from __future__ import annotations
"""Amber (琥珀) — 3★ 存护光锥。

特效:
  #1: 装备者的防御力提高#1[i]%
  #2/#3: 当前HP百分比小于#2[i]%时，防御力额外提高#3[i]%（状态依赖）
"""

from typing import Optional

from entities.light_cones.base import BaseLightCone
from entities.base import EquipmentEffect, StatModifier


class Amber(BaseLightCone):
    _default_id = "20003"
    _default_name = "琥珀"
    _default_path_key = "Knight"

    _PROMOTIONS = [
        {"hp_base": 38.4, "hp_step": 5.76, "atk_base": 12, "atk_step": 1.8, "def_base": 15, "def_step": 2.25},
        {"hp_base": 84.48, "hp_step": 5.76, "atk_base": 26.4, "atk_step": 1.8, "def_base": 33, "def_step": 2.25},
        {"hp_base": 145.92, "hp_step": 5.76, "atk_base": 45.6, "atk_step": 1.8, "def_base": 57, "def_step": 2.25},
        {"hp_base": 207.36, "hp_step": 5.76, "atk_base": 64.8, "atk_step": 1.8, "def_base": 81, "def_step": 2.25},
        {"hp_base": 268.8, "hp_step": 5.76, "atk_base": 84, "atk_step": 1.8, "def_base": 105, "def_step": 2.25},
        {"hp_base": 330.24, "hp_step": 5.76, "atk_base": 103.2, "atk_step": 1.8, "def_base": 129, "def_step": 2.25},
        {"hp_base": 391.68, "hp_step": 5.76, "atk_base": 122.4, "atk_step": 1.8, "def_base": 153, "def_step": 2.25},
    ]

    def __init__(self, id: str = "", **kwargs):
        super().__init__(id=id, **kwargs)
        if self.effect is None:
            self.effect = AmberEffect(self.superimpose)


class AmberEffect(EquipmentEffect):
    _PARAMS = [
        [0.16, 0.50, 0.16],
        [0.20, 0.50, 0.20],
        [0.24, 0.50, 0.24],
        [0.28, 0.50, 0.28],
        [0.32, 0.50, 0.32],
    ]
    _SOURCE = "LightCone_20003"
    _SOURCE_COND = "LightCone_20003_COND"

    def __init__(self, superimpose: int = 1) -> None:
        self.superimpose = max(1, min(superimpose, 5))
        self._character: Optional["Character"] = None
        self._cb_start: Optional[callable] = None
        self._cb_dmg: Optional[callable] = None
        self._cb_heal: Optional[callable] = None

    def on_equip(self, character: "Character") -> None:
        from core.enums import StatType, StatModifierType

        p = self._PARAMS[self.superimpose - 1]
        mod = StatModifier(
            stat_type=StatType.DEF,
            modifier_type=StatModifierType.PERCENT,
            value=p[0],
            source=self._SOURCE,
            dispellable=False,
        )
        character.stats.apply_modifier(mod, "refresh")

    def on_combat_start(self, state: "GameState", character: "Character") -> None:
        from core.events import EventType

        self._character = character
        self._cb_start = lambda **kw: self._check_hp(character)
        self._cb_dmg = lambda **kw: self._check_hp(kw.get("target"))
        self._cb_heal = lambda **kw: self._check_hp(kw.get("target"))
        state.event_bus.subscribe(EventType.BATTLE_START, self._cb_start)
        state.event_bus.subscribe(EventType.ON_DAMAGE_DEALT, self._cb_dmg)
        state.event_bus.subscribe(EventType.HEAL_DONE, self._cb_heal)

    def _check_hp(self, target) -> None:
        from core.enums import StatType, StatModifierType

        if target is not self._character:
            return

        p = self._PARAMS[self.superimpose - 1]
        threshold = p[1]
        extra_def = p[2]

        under_threshold = self._character.hp <= self._character.max_hp * threshold

        if under_threshold:
            mod = StatModifier(
                stat_type=StatType.DEF,
                modifier_type=StatModifierType.PERCENT,
                value=extra_def,
                source=self._SOURCE_COND,
                dispellable=False,
            )
            self._character.stats.apply_modifier(mod, "refresh")
        else:
            self._character.stats.purge_source(self._SOURCE_COND)

    def on_unequip(self, character: "Character") -> None:
        from core.events import EventType

        character.stats.purge_source(self._SOURCE)
        character.stats.purge_source(self._SOURCE_COND)
        if character.event_bus is not None:
            if self._cb_start is not None:
                character.event_bus.unsubscribe(EventType.BATTLE_START, self._cb_start)
            if self._cb_dmg is not None:
                character.event_bus.unsubscribe(EventType.ON_DAMAGE_DEALT, self._cb_dmg)
            if self._cb_heal is not None:
                character.event_bus.unsubscribe(EventType.HEAL_DONE, self._cb_heal)

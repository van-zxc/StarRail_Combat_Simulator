from __future__ import annotations
"""渊环 (Loop) — 3★ 虚无光锥。

特效: 对减速状态下的敌方目标造成的伤害提高#1[i]%。
"""

from typing import Optional

from entities.light_cones.base import BaseLightCone
from entities.base import EquipmentEffect, StatModifier


class Loop(BaseLightCone):
    _default_id = "20011"
    _default_name = "渊环"
    _default_path_key = "Warlock"

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
            self.effect = LoopEffect(self.superimpose)


class LoopEffect(EquipmentEffect):
    _PARAMS = [0.24, 0.30, 0.36, 0.42, 0.48]
    _SOURCE = "LightCone_20011"

    def __init__(self, superimpose: int = 1) -> None:
        self.superimpose = max(1, min(superimpose, 5))
        self._character: Optional["Character"] = None
        self._cb_action_start: Optional[callable] = None
        self._cb_after: Optional[callable] = None

    @staticmethod
    def _target_is_slowed(target: "Fighter") -> bool:
        if not hasattr(target, "stats"):
            return False
        from core.enums import StatType

        for m in target.stats.active_modifiers:
            if m.stat_type == StatType.SPD and m.value < 0:
                return True
        return False

    def on_equip(self, character: "Character") -> None:
        pass

    def on_combat_start(self, state: "GameState", character: "Character") -> None:
        from core.events import EventType

        self._character = character
        self._cb_action_start = lambda **kw: self._on_action_start(kw.get("unit"), kw.get("target"))
        self._cb_after = lambda **kw: self._on_after_action(kw.get("unit"))
        bus = state.event_bus
        bus.subscribe(EventType.ACTION_START, self._cb_action_start)
        bus.subscribe(EventType.AFTER_ACTION, self._cb_after)

    def _on_action_start(self, unit: "Character", target: "Fighter") -> None:
        if unit is not self._character:
            return
        if target is None or not hasattr(target, "stats"):
            return
        from core.enums import StatType, StatModifierType

        dmg_val = self._PARAMS[self.superimpose - 1]

        if self._target_is_slowed(target):
            mod = StatModifier(
                stat_type=StatType.DMG_BONUS,
                modifier_type=StatModifierType.PERCENT,
                value=dmg_val,
                source=self._SOURCE,
                dispellable=False,
            )
            self._character.stats.apply_modifier(mod, "refresh")
        else:
            self._character.stats.purge_source(self._SOURCE)

    def _on_after_action(self, unit: "Character") -> None:
        if unit is not self._character:
            return
        self._character.stats.purge_source(self._SOURCE)

    def on_unequip(self, character: "Character") -> None:
        from core.events import EventType

        character.stats.purge_source(self._SOURCE)
        if character.event_bus is not None:
            bus = character.event_bus
            if self._cb_action_start is not None:
                bus.unsubscribe(EventType.ACTION_START, self._cb_action_start)
            if self._cb_after is not None:
                bus.unsubscribe(EventType.AFTER_ACTION, self._cb_after)

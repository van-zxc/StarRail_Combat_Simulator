from __future__ import annotations
"""延长记号 (Fermata) — 4★ 虚无光锥。

特效: 击破特攻提高#1[i]%，对触电或风化状态的敌人伤害提高#2[i]%（对持续伤害生效）。
"""

from typing import Optional

from entities.light_cones.base import BaseLightCone
from entities.base import EquipmentEffect, StatModifier


class Fermata(BaseLightCone):
    _default_id = "21022"
    _default_name = "延长记号"
    _default_path_key = "Warlock"

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
            self.effect = FermataEffect(self.superimpose)


class FermataEffect(EquipmentEffect):
    _PARAMS = [[0.16, 0.16], [0.20, 0.20], [0.24, 0.24], [0.28, 0.28], [0.32, 0.32]]
    _SOURCE = "LightCone_21022"
    _COND_SOURCE = "LightCone_21022_COND"

    def __init__(self, superimpose: int = 1) -> None:
        self.superimpose = max(1, min(superimpose, 5))
        self._character: Optional["Character"] = None
        self._cb_action_start: Optional[callable] = None
        self._cb_after: Optional[callable] = None

    def on_equip(self, character: "Character") -> None:
        from core.enums import StatType, StatModifierType

        be_pct = self._PARAMS[self.superimpose - 1][0]
        mod = StatModifier(
            stat_type=StatType.BREAK_EFFECT,
            modifier_type=StatModifierType.PERCENT,
            value=be_pct,
            source=self._SOURCE,
            dispellable=False,
        )
        character.stats.apply_modifier(mod, "refresh")

    @staticmethod
    def _target_has_shock_or_wind_shear(target: "Fighter") -> bool:
        from core.enums import ElementType

        if not hasattr(target, "dot_statuses"):
            return False
        for dot in target.dot_statuses:
            if dot.element in (ElementType.LIGHTNING, ElementType.WIND):
                return True
        return False

    def on_combat_start(self, state: "GameState", character: "Character") -> None:
        from core.events import EventType

        self._character = character
        self._cb_action_start = lambda **kw: self._on_action_start(kw.get("unit"), kw.get("target"))
        self._cb_after = lambda **kw: self._on_after(kw.get("unit"))
        bus = state.event_bus
        bus.subscribe(EventType.ACTION_START, self._cb_action_start)
        bus.subscribe(EventType.AFTER_ACTION, self._cb_after)

    def _on_action_start(self, unit: "Character", target: "Fighter") -> None:
        if unit is not self._character:
            return
        if target is None or not hasattr(target, "dot_statuses"):
            return
        from core.enums import StatType, StatModifierType

        dmg_val = self._PARAMS[self.superimpose - 1][1]

        if self._target_has_shock_or_wind_shear(target):
            mod = StatModifier(
                stat_type=StatType.DMG_BONUS,
                modifier_type=StatModifierType.PERCENT,
                value=dmg_val,
                source=self._COND_SOURCE,
                dispellable=False,
            )
            self._character.stats.apply_modifier(mod, "refresh")
        else:
            self._character.stats.purge_source(self._COND_SOURCE)

    def _on_after(self, unit: "Character") -> None:
        if unit is not self._character:
            return
        self._character.stats.purge_source(self._COND_SOURCE)

    def on_unequip(self, character: "Character") -> None:
        from core.events import EventType

        character.stats.purge_source(self._SOURCE)
        character.stats.purge_source(self._COND_SOURCE)
        if character.event_bus is not None:
            bus = character.event_bus
            if self._cb_action_start is not None:
                bus.unsubscribe(EventType.ACTION_START, self._cb_action_start)
            if self._cb_after is not None:
                bus.unsubscribe(EventType.AFTER_ACTION, self._cb_after)

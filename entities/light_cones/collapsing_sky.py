from __future__ import annotations
"""乐圮 (Collapsing Sky) — 3★ 毁灭光锥。

特效: 对当前生命值百分比大于#1[i]%的敌方目标造成的伤害提高#2[i]%。
"""

from typing import Optional

from entities.light_cones.base import BaseLightCone
from entities.base import EquipmentEffect, StatModifier


class CollapsingSky(BaseLightCone):
    _default_id = "20009"
    _default_name = "乐圮"
    _default_path_key = "Warrior"

    _PROMOTIONS = [
        {"hp_base": 38.4, "hp_step": 5.76, "atk_base": 16.8, "atk_step": 2.52, "def_base": 9, "def_step": 1.35},
        {"hp_base": 84.48, "hp_step": 5.76, "atk_base": 36.96, "atk_step": 2.52, "def_base": 19.8, "def_step": 1.35},
        {"hp_base": 145.92, "hp_step": 5.76, "atk_base": 63.84, "atk_step": 2.52, "def_base": 34.2, "def_step": 1.35},
        {"hp_base": 207.36, "hp_step": 5.76, "atk_base": 90.72, "atk_step": 2.52, "def_base": 48.6, "def_step": 1.35},
        {"hp_base": 268.8, "hp_step": 5.76, "atk_base": 117.6, "atk_step": 2.52, "def_base": 63, "def_step": 1.35},
        {"hp_base": 330.24, "hp_step": 5.76, "atk_base": 144.48, "atk_step": 2.52, "def_base": 77.4, "def_step": 1.35},
        {"hp_base": 391.68, "hp_step": 5.76, "atk_base": 171.36, "atk_step": 2.52, "def_base": 91.8, "def_step": 1.35},
    ]

    def __init__(self, id: str = "", **kwargs):
        super().__init__(id=id, **kwargs)
        if self.effect is None:
            self.effect = CollapsingSkyEffect(self.superimpose)


class CollapsingSkyEffect(EquipmentEffect):
    _PARAMS = [[0.50, 0.20], [0.50, 0.25], [0.50, 0.30], [0.50, 0.35], [0.50, 0.40]]
    _SOURCE = "LightCone_20009"

    def __init__(self, superimpose: int = 1) -> None:
        self.superimpose = max(1, min(superimpose, 5))
        self._character: Optional["Character"] = None
        self._cb_action_start: Optional[callable] = None
        self._cb_after: Optional[callable] = None

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
        if target is None or not hasattr(target, "hp"):
            return
        from core.enums import StatType, StatModifierType

        threshold = self._PARAMS[self.superimpose - 1][0]
        dmg_val = self._PARAMS[self.superimpose - 1][1]
        target_hp_pct = target.hp / target.max_hp if target.max_hp > 0 else 0.0

        if target_hp_pct > threshold:
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

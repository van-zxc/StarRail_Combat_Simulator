from __future__ import annotations
"""点个关注吧！ (Subscribe for More!) — 4★ 巡猎光锥。

特效: 普攻和战技伤害提高#1[i]%，能量满时额外提高#2[i]%。
"""

from typing import Optional

from entities.light_cones.base import BaseLightCone
from entities.base import EquipmentEffect, StatModifier


class SubscribeForMore(BaseLightCone):
    _default_id = "21017"
    _default_name = "点个关注吧！"
    _default_path_key = "Rogue"

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
            self.effect = SubscribeForMoreEffect(self.superimpose)


class SubscribeForMoreEffect(EquipmentEffect):
    _PARAMS = [[0.24, 0.24], [0.30, 0.30], [0.36, 0.36], [0.42, 0.42], [0.48, 0.48]]
    _SOURCE = "LightCone_21017"
    _COND_SOURCE = "LightCone_21017_COND"

    def __init__(self, superimpose: int = 1) -> None:
        self.superimpose = max(1, min(superimpose, 5))
        self._character: Optional["Character"] = None
        self._cb_action_start: Optional[callable] = None
        self._cb_after: Optional[callable] = None

    def on_equip(self, character: "Character") -> None:
        from core.enums import StatType, StatModifierType

        pct = self._PARAMS[self.superimpose - 1][0]
        mod = StatModifier(
            stat_type=StatType.BASIC_ATK_DMG,
            modifier_type=StatModifierType.PERCENT,
            value=pct,
            source=self._SOURCE,
            dispellable=False,
        )
        character.stats.apply_modifier(mod, "refresh")
        mod2 = StatModifier(
            stat_type=StatType.SKILL_DMG,
            modifier_type=StatModifierType.PERCENT,
            value=pct,
            source=self._SOURCE,
            dispellable=False,
        )
        character.stats.apply_modifier(mod2, "refresh")

    def on_combat_start(self, state: "GameState", character: "Character") -> None:
        from core.events import EventType

        self._character = character
        self._cb_action_start = lambda **kw: self._on_action_start(kw.get("unit"))
        self._cb_after = lambda **kw: self._on_after(kw.get("unit"))
        bus = state.event_bus
        bus.subscribe(EventType.ACTION_START, self._cb_action_start)
        bus.subscribe(EventType.AFTER_ACTION, self._cb_after)

    def _on_action_start(self, unit: "Character") -> None:
        if unit is not self._character:
            return
        from core.enums import StatType, StatModifierType

        extra = self._PARAMS[self.superimpose - 1][1]
        if self._character.energy >= self._character.max_energy:
            mod = StatModifier(
                stat_type=StatType.DMG_BONUS,
                modifier_type=StatModifierType.PERCENT,
                value=extra,
                source=self._COND_SOURCE,
                dispellable=False,
            )
            self._character.stats.apply_modifier(mod, "refresh")

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

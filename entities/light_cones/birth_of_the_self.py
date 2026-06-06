from __future__ import annotations
"""『我』的诞生 (The Birth of the Self) — 4★ 智识光锥。

特效: 追加攻击伤害提高#1[i]%，若目标HP≤#2[i]%则额外提高#3[i]%。

JSON对齐: OnBeforeHitAll:Insert+HP≤X → AllDamageTypeAddedRatio (per-hit 实时HP判定).
Python: ACTION_START/AFTER_ACTION → FUA_DMG + FUA_DMG_COND (per-action, KI-005 模式)."""

from typing import Optional

from entities.light_cones.base import BaseLightCone
from entities.base import EquipmentEffect, StatModifier


class BirthOfTheSelf(BaseLightCone):
    _default_id = "21006"
    _default_name = "「我」的诞生"
    _default_path_key = "Mage"

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
            self.effect = BirthOfTheSelfEffect(self.superimpose)


class BirthOfTheSelfEffect(EquipmentEffect):
    _PARAMS = [[0.24, 0.50, 0.24], [0.30, 0.50, 0.30], [0.36, 0.50, 0.36], [0.42, 0.50, 0.42], [0.48, 0.50, 0.48]]
    _SOURCE = "LightCone_21006"
    _COND_SOURCE = "LightCone_21006_COND"

    def __init__(self, superimpose: int = 1) -> None:
        self.superimpose = max(1, min(superimpose, 5))
        self._character: Optional["Character"] = None
        self._cb_action_start: Optional[callable] = None
        self._cb_after: Optional[callable] = None

    def on_equip(self, character: "Character") -> None:
        from core.enums import StatType, StatModifierType

        fua_pct = self._PARAMS[self.superimpose - 1][0]
        mod = StatModifier(
            stat_type=StatType.FUA_DMG,
            modifier_type=StatModifierType.PERCENT,
            value=fua_pct,
            source=self._SOURCE,
            dispellable=False,
        )
        character.stats.apply_modifier(mod, "refresh")

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
        if target is None or target.max_hp <= 0:
            return
        from core.enums import StatType, StatModifierType

        threshold = self._PARAMS[self.superimpose - 1][1]
        extra_pct = self._PARAMS[self.superimpose - 1][2]
        target_pct = target.hp / target.max_hp

        if target_pct <= threshold:
            mod = StatModifier(
                stat_type=StatType.FUA_DMG,
                modifier_type=StatModifierType.PERCENT,
                value=extra_pct,
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

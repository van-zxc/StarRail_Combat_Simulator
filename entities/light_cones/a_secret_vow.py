from __future__ import annotations
"""秘密誓心 (A Secret Vow) — 4★ 毁灭光锥。

特效: 造成的伤害提高#1[i]%，同时对HP%>=装备者HP%的敌方目标额外造成#2[i]%伤害。

JSON对齐: OnBeforeHitAll:SetDynamicValueByHPRatio → AllDamageTypeAddedRatio (per-hit 实时HP比较).
Python: ACTION_START/AFTER_ACTION → DMG_BONUS_COND (per-action, KI-005 模式)."""

from typing import Optional

from entities.light_cones.base import BaseLightCone
from entities.base import EquipmentEffect, StatModifier


class ASecretVow(BaseLightCone):
    _default_id = "21012"
    _default_name = "秘密誓心"
    _default_path_key = "Warrior"

    _PROMOTIONS = [
        {"hp_base": 48, "hp_step": 7.2, "atk_base": 21.6, "atk_step": 3.24, "def_base": 12, "def_step": 1.8},
        {"hp_base": 105.6, "hp_step": 7.2, "atk_base": 47.52, "atk_step": 3.24, "def_base": 26.4, "def_step": 1.8},
        {"hp_base": 182.4, "hp_step": 7.2, "atk_base": 82.08, "atk_step": 3.24, "def_base": 45.6, "def_step": 1.8},
        {"hp_base": 259.2, "hp_step": 7.2, "atk_base": 116.64, "atk_step": 3.24, "def_base": 64.8, "def_step": 1.8},
        {"hp_base": 336, "hp_step": 7.2, "atk_base": 151.2, "atk_step": 3.24, "def_base": 84, "def_step": 1.8},
        {"hp_base": 412.8, "hp_step": 7.2, "atk_base": 185.76, "atk_step": 3.24, "def_base": 103.2, "def_step": 1.8},
        {"hp_base": 489.6, "hp_step": 7.2, "atk_base": 220.32, "atk_step": 3.24, "def_base": 122.4, "def_step": 1.8},
    ]

    def __init__(self, id: str = "", **kwargs):
        super().__init__(id=id, **kwargs)
        if self.effect is None:
            self.effect = ASecretVowEffect(self.superimpose)


class ASecretVowEffect(EquipmentEffect):
    _PARAMS = [[0.20, 0.20], [0.25, 0.25], [0.30, 0.30], [0.35, 0.35], [0.40, 0.40]]
    _SOURCE = "LightCone_21012"
    _COND_SOURCE = "LightCone_21012_COND"

    def __init__(self, superimpose: int = 1) -> None:
        self.superimpose = max(1, min(superimpose, 5))
        self._character: Optional["Character"] = None
        self._cb_action_start: Optional[callable] = None
        self._cb_after: Optional[callable] = None

    def on_equip(self, character: "Character") -> None:
        from core.enums import StatType, StatModifierType

        pct = self._PARAMS[self.superimpose - 1][0]
        mod = StatModifier(
            stat_type=StatType.DMG_BONUS,
            modifier_type=StatModifierType.PERCENT,
            value=pct,
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
        if target is None or not hasattr(target, "hp") or not hasattr(target, "max_hp"):
            return
        from core.enums import StatType, StatModifierType

        extra = self._PARAMS[self.superimpose - 1][1]
        char_pct = self._character.hp / self._character.max_hp if self._character.max_hp > 0 else 1.0
        target_pct = target.hp / target.max_hp if target.max_hp > 0 else 0.0

        if target_pct >= char_pct:
            mod = StatModifier(
                stat_type=StatType.DMG_BONUS,
                modifier_type=StatModifierType.PERCENT,
                value=extra,
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

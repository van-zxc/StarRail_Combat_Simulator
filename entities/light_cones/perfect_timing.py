from __future__ import annotations
"""此时恰好 (Perfect Timing) — 4★ 丰饶光锥。

特效: 效果抵抗提高#1[i]%，治疗量提高 = 效果抵抗×#2[i]%（最多#3[i]%）。
"""

from typing import Optional

from entities.light_cones.base import BaseLightCone
from entities.base import EquipmentEffect, StatModifier


class PerfectTiming(BaseLightCone):
    _default_id = "21014"
    _default_name = "此时恰好"
    _default_path_key = "Priest"

    _PROMOTIONS = [
        {"hp_base": 43.2, "hp_step": 6.48, "atk_base": 19.2, "atk_step": 2.88, "def_base": 18, "def_step": 2.7},
        {"hp_base": 95.04, "hp_step": 6.48, "atk_base": 42.24, "atk_step": 2.88, "def_base": 39.6, "def_step": 2.7},
        {"hp_base": 164.16, "hp_step": 6.48, "atk_base": 72.96, "atk_step": 2.88, "def_base": 68.4, "def_step": 2.7},
        {"hp_base": 233.28, "hp_step": 6.48, "atk_base": 103.68, "atk_step": 2.88, "def_base": 97.2, "def_step": 2.7},
        {"hp_base": 302.4, "hp_step": 6.48, "atk_base": 134.4, "atk_step": 2.88, "def_base": 126, "def_step": 2.7},
        {"hp_base": 371.52, "hp_step": 6.48, "atk_base": 165.12, "atk_step": 2.88, "def_base": 154.8, "def_step": 2.7},
        {"hp_base": 440.64, "hp_step": 6.48, "atk_base": 195.84, "atk_step": 2.88, "def_base": 183.6, "def_step": 2.7},
    ]

    def __init__(self, id: str = "", **kwargs):
        super().__init__(id=id, **kwargs)
        if self.effect is None:
            self.effect = PerfectTimingEffect(self.superimpose)


class PerfectTimingEffect(EquipmentEffect):
    _PARAMS = [[0.16, 0.33, 0.15], [0.20, 0.36, 0.18], [0.24, 0.39, 0.21], [0.28, 0.42, 0.24], [0.32, 0.45, 0.27]]
    _SOURCE_RES = "LightCone_21014_RES"
    _SOURCE_HEAL = "LightCone_21014_HEAL"

    def __init__(self, superimpose: int = 1) -> None:
        self.superimpose = max(1, min(superimpose, 5))
        self._character: Optional["Character"] = None
        self._recalc_in_progress: bool = False
        self._cb_status_apply: Optional[callable] = None
        self._cb_status_expire: Optional[callable] = None

    def on_equip(self, character: "Character") -> None:
        from core.enums import StatType, StatModifierType

        er_val = self._PARAMS[self.superimpose - 1][0]
        mod = StatModifier(
            stat_type=StatType.EFFECT_RES,
            modifier_type=StatModifierType.PERCENT,
            value=er_val,
            source=self._SOURCE_RES,
            dispellable=False,
        )
        character.stats.apply_modifier(mod, "refresh")

    def _recalc_heal_boost(self) -> None:
        if self._recalc_in_progress:
            return
        self._recalc_in_progress = True
        try:
            from core.enums import StatType, StatModifierType

            p = self._PARAMS[self.superimpose - 1]
            ratio = p[1]
            cap = p[2]
            eff_res = self._character.stats.get_total_stat(StatType.EFFECT_RES)
            heal_val = min(eff_res * ratio, cap)
            if heal_val > 0:
                mod = StatModifier(
                    stat_type=StatType.OUTGOING_HEALING_BOOST,
                    modifier_type=StatModifierType.PERCENT,
                    value=heal_val,
                    source=self._SOURCE_HEAL,
                    dispellable=False,
                )
                self._character.stats.apply_modifier(mod, "refresh")
            else:
                self._character.stats.purge_source(self._SOURCE_HEAL)
        finally:
            self._recalc_in_progress = False

    def on_combat_start(self, state: "GameState", character: "Character") -> None:
        from core.events import EventType

        self._character = character
        self._cb_status_apply = lambda **kw: self._on_status_change(kw.get("target"))
        self._cb_status_expire = lambda **kw: self._on_status_change(kw.get("unit"))
        bus = state.event_bus
        bus.subscribe(EventType.ON_STATUS_APPLY, self._cb_status_apply)
        bus.subscribe(EventType.ON_STATUS_EXPIRE, self._cb_status_expire)
        self._recalc_heal_boost()

    def _on_status_change(self, target: "Fighter") -> None:
        if target is not self._character:
            return
        self._recalc_heal_boost()

    def on_unequip(self, character: "Character") -> None:
        from core.events import EventType

        character.stats.purge_source(self._SOURCE_RES)
        character.stats.purge_source(self._SOURCE_HEAL)
        if character.event_bus is not None:
            bus = character.event_bus
            if self._cb_status_apply is not None:
                bus.unsubscribe(EventType.ON_STATUS_APPLY, self._cb_status_apply)
            if self._cb_status_expire is not None:
                bus.unsubscribe(EventType.ON_STATUS_EXPIRE, self._cb_status_expire)

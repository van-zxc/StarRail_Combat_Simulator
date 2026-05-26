from __future__ import annotations
"""俱殁 (Mutual Demise) — 3★ 毁灭光锥。

特效: 当前生命值百分比小于#1[i]%时，暴击率提高#2[i]%。
"""

from typing import Optional

from entities.light_cones.base import BaseLightCone
from entities.base import EquipmentEffect, StatModifier


class MutualDemise(BaseLightCone):
    _default_id = "20016"
    _default_name = "俱殁"
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
            self.effect = MutualDemiseEffect(self.superimpose)


class MutualDemiseEffect(EquipmentEffect):
    _PARAMS = [[0.80, 0.12], [0.80, 0.15], [0.80, 0.18], [0.80, 0.21], [0.80, 0.24]]
    _SOURCE = "LightCone_20016"

    def __init__(self, superimpose: int = 1) -> None:
        self.superimpose = max(1, min(superimpose, 5))
        self._character: Optional["Character"] = None
        self._cb_damage: Optional[callable] = None
        self._cb_heal: Optional[callable] = None

    def on_equip(self, character: "Character") -> None:
        self._check_hp(character)

    def _check_hp(self, character: "Character") -> None:
        from core.enums import StatType, StatModifierType

        threshold = self._PARAMS[self.superimpose - 1][0]
        crit_val = self._PARAMS[self.superimpose - 1][1]
        hp_pct = character.hp / character.max_hp if character.max_hp > 0 else 1.0

        if hp_pct < threshold:
            mod = StatModifier(
                stat_type=StatType.CRIT_RATE,
                modifier_type=StatModifierType.PERCENT,
                value=crit_val,
                source=self._SOURCE,
                dispellable=False,
            )
            character.stats.apply_modifier(mod, "refresh")
        else:
            character.stats.purge_source(self._SOURCE)

    def on_combat_start(self, state: "GameState", character: "Character") -> None:
        from core.events import EventType

        self._character = character
        self._cb_damage = lambda **kw: self._on_damage_or_heal(kw.get("target"))
        self._cb_heal = lambda **kw: self._on_damage_or_heal(kw.get("target"))
        state.event_bus.subscribe(EventType.ON_DAMAGE_DEALT, self._cb_damage)
        state.event_bus.subscribe(EventType.HEAL_DONE, self._cb_heal)

    def _on_damage_or_heal(self, target: "Fighter") -> None:
        if target is not self._character:
            return
        self._check_hp(self._character)

    def on_unequip(self, character: "Character") -> None:
        from core.events import EventType

        character.stats.purge_source(self._SOURCE)
        if character.event_bus is not None:
            bus = character.event_bus
            if self._cb_damage is not None:
                bus.unsubscribe(EventType.ON_DAMAGE_DEALT, self._cb_damage)
            if self._cb_heal is not None:
                bus.unsubscribe(EventType.HEAL_DONE, self._cb_heal)

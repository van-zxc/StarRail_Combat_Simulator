from __future__ import annotations
"""决心如汗珠般闪耀 (Resolution Shines As Pearls of Sweat) — 4★ 虚无光锥。

特效: 击中目标有#1[i]%基础概率使其陷入【攻陷】，防御力降低#2[i]%，持续#3[i]回合。
"""

import random
from typing import Optional

from entities.light_cones.base import BaseLightCone
from entities.base import EquipmentEffect, StatModifier


class ResolutionShines(BaseLightCone):
    _default_id = "21015"
    _default_name = "决心如汗珠般闪耀"
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
            self.effect = ResolutionShinesEffect(self.superimpose)


_RESOLUTION_TAG = "Resolution_21015_Ensnared"


class ResolutionShinesEffect(EquipmentEffect):
    _PARAMS = [[0.60, 0.12, 1], [0.70, 0.13, 1], [0.80, 0.14, 1], [0.90, 0.15, 1], [1.00, 0.16, 1]]
    _SOURCE = "LightCone_21015"

    def __init__(self, superimpose: int = 1) -> None:
        self.superimpose = max(1, min(superimpose, 5))
        self._character: Optional["Character"] = None
        self._cb_hit: Optional[callable] = None

    def on_equip(self, character: "Character") -> None:
        pass

    @staticmethod
    def _target_has_ensnared(target: "Fighter") -> bool:
        if not hasattr(target, "stats"):
            return False
        for m in target.stats.active_modifiers:
            if getattr(m, "tag", "") == _RESOLUTION_TAG:
                return True
        return False

    def on_combat_start(self, state: "GameState", character: "Character") -> None:
        from core.events import EventType

        self._character = character
        self._cb_hit = lambda **kw: self._on_hit(kw.get("source"), kw.get("target"))
        state.event_bus.subscribe(EventType.ON_HIT, self._cb_hit)

    def _on_hit(self, source: "Character", target: "Fighter") -> None:
        if source is not self._character:
            return
        if target is None or not hasattr(target, "stats"):
            return
        if self._target_has_ensnared(target):
            return
        from core.enums import StatType, StatModifierType

        p = self._PARAMS[self.superimpose - 1]
        base_chance = p[0]
        def_reduction = p[1]
        duration = p[2]

        ehr = self._character.stats.get_total_stat(StatType.EFFECT_HIT_RATE)
        actual_chance = base_chance * (1.0 + ehr)
        if random.random() >= actual_chance:
            return

        mod = StatModifier(
            stat_type=StatType.DEF_REDUCTION,
            modifier_type=StatModifierType.PERCENT,
            value=def_reduction,
            source=self._SOURCE,
            duration=duration,
            dispellable=True,
        )
        mod.tag = _RESOLUTION_TAG
        target.stats.apply_modifier(mod, "refresh")

    def on_unequip(self, character: "Character") -> None:
        from core.events import EventType

        character.stats.purge_source(self._SOURCE)
        if self._cb_hit is not None and character.event_bus is not None:
            character.event_bus.unsubscribe(EventType.ON_HIT, self._cb_hit)

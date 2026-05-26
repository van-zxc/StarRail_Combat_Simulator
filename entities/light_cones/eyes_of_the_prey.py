from __future__ import annotations
"""猎物的视线 (Eyes of the Prey) — 4★ 虚无光锥。

特效: 效果命中提高#1[i]%，同时造成的持续伤害提高#2[i]%。
"""

from typing import Optional

from entities.light_cones.base import BaseLightCone
from entities.base import EquipmentEffect, StatModifier


class EyesOfThePrey(BaseLightCone):
    _default_id = "21008"
    _default_name = "猎物的视线"
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
            self.effect = EyesOfThePreyEffect(self.superimpose)


class EyesOfThePreyEffect(EquipmentEffect):
    _PARAMS = [[0.20, 0.24], [0.25, 0.30], [0.30, 0.36], [0.35, 0.42], [0.40, 0.48]]
    _SOURCE = "LightCone_21008"

    def __init__(self, superimpose: int = 1) -> None:
        self.superimpose = max(1, min(superimpose, 5))

    def on_equip(self, character: "Character") -> None:
        from core.enums import StatType, StatModifierType

        p = self._PARAMS[self.superimpose - 1]
        ehr_mod = StatModifier(
            stat_type=StatType.EFFECT_HIT_RATE,
            modifier_type=StatModifierType.PERCENT,
            value=p[0],
            source=self._SOURCE,
            dispellable=False,
        )
        dot_dmg_mod = StatModifier(
            stat_type=StatType.DOT_DMG,
            modifier_type=StatModifierType.PERCENT,
            value=p[1],
            source=self._SOURCE,
            dispellable=False,
        )
        character.stats.apply_modifier(ehr_mod, "refresh")
        character.stats.apply_modifier(dot_dmg_mod, "refresh")

    def on_combat_start(self, state: "GameState", character: "Character") -> None:
        pass

    def on_unequip(self, character: "Character") -> None:
        character.stats.purge_source(self._SOURCE)

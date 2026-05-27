from __future__ import annotations
"""Skyfall (天倾) — 3★ 毁灭光锥。

特效: 使装备者普攻和战技造成的伤害提高#1[i]%。
"""

from typing import Optional

from entities.light_cones.base import BaseLightCone
from entities.base import EquipmentEffect, StatModifier


class Skyfall(BaseLightCone):
    _default_id = "20002"
    _default_name = "天倾"
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
            self.effect = SkyfallEffect(self.superimpose)


class SkyfallEffect(EquipmentEffect):
    _PARAMS = [
        [0.20],
        [0.25],
        [0.30],
        [0.35],
        [0.40],
    ]
    _SOURCE_BA = "LightCone_20002_BA"
    _SOURCE_SKILL = "LightCone_20002_SKILL"

    def __init__(self, superimpose: int = 1) -> None:
        self.superimpose = max(1, min(superimpose, 5))
        self._character: Optional["Character"] = None

    def on_equip(self, character: "Character") -> None:
        from core.enums import StatType, StatModifierType

        p = self._PARAMS[self.superimpose - 1]
        for stat, src in ((StatType.BASIC_ATK_DMG, self._SOURCE_BA),
                           (StatType.SKILL_DMG, self._SOURCE_SKILL)):
            mod = StatModifier(
                stat_type=stat,
                modifier_type=StatModifierType.PERCENT,
                value=p[0],
                source=src,
                dispellable=False,
            )
            character.stats.apply_modifier(mod, "refresh")

    def on_combat_start(self, state: "GameState", character: "Character") -> None:
        pass

    def on_unequip(self, character: "Character") -> None:
        character.stats.purge_source(self._SOURCE_BA)
        character.stats.purge_source(self._SOURCE_SKILL)

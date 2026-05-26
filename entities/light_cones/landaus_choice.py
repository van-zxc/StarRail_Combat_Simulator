from __future__ import annotations
"""朗道的选择 (Landau's Choice) — 4★ 存护光锥。

特效: 受到攻击的概率提高，同时受到的伤害降低#2[i]%。
"""

from entities.light_cones.base import BaseLightCone
from entities.base import EquipmentEffect, StatModifier


class LandausChoice(BaseLightCone):
    _default_id = "21009"
    _default_name = "朗道的选择"
    _default_path_key = "Knight"

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
            self.effect = LandausChoiceEffect(self.superimpose)


class LandausChoiceEffect(EquipmentEffect):
    _PARAMS = [[2, 0.16], [2, 0.18], [2, 0.20], [2, 0.22], [2, 0.24]]
    _SOURCE = "LightCone_21009"

    def __init__(self, superimpose: int = 1) -> None:
        self.superimpose = max(1, min(superimpose, 5))

    def on_equip(self, character: "Character") -> None:
        from core.enums import StatType, StatModifierType

        p = self._PARAMS[self.superimpose - 1]
        agg_mod = StatModifier(
            stat_type=StatType.AGGRO_MODIFIER,
            modifier_type=StatModifierType.FLAT,
            value=p[0],
            source=self._SOURCE,
            dispellable=False,
        )
        mit_mod = StatModifier(
            stat_type=StatType.DMG_MITIGATION,
            modifier_type=StatModifierType.PERCENT,
            value=p[1],
            source=self._SOURCE,
            dispellable=False,
        )
        character.stats.apply_modifier(agg_mod, "refresh")
        character.stats.apply_modifier(mit_mod, "refresh")

    def on_combat_start(self, state: "GameState", character: "Character") -> None:
        pass

    def on_unequip(self, character: "Character") -> None:
        character.stats.purge_source(self._SOURCE)

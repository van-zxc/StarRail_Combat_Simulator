from __future__ import annotations
"""DataBank (智库) — 3★ 智识光锥。

特效: 使装备者终结技造成的伤害提高#1[i]%。
"""

from typing import Optional

from entities.light_cones.base import BaseLightCone
from entities.base import EquipmentEffect, StatModifier


class DataBank(BaseLightCone):
    _default_id = "20006"
    _default_name = "智库"
    _default_path_key = "Mage"

    _PROMOTIONS = [
        {"hp_base": 33.6, "hp_step": 5.04, "atk_base": 16.8, "atk_step": 2.52, "def_base": 12, "def_step": 1.8},
        {"hp_base": 73.92, "hp_step": 5.04, "atk_base": 36.96, "atk_step": 2.52, "def_base": 26.4, "def_step": 1.8},
        {"hp_base": 127.68, "hp_step": 5.04, "atk_base": 63.84, "atk_step": 2.52, "def_base": 45.6, "def_step": 1.8},
        {"hp_base": 181.44, "hp_step": 5.04, "atk_base": 90.72, "atk_step": 2.52, "def_base": 64.8, "def_step": 1.8},
        {"hp_base": 235.2, "hp_step": 5.04, "atk_base": 117.6, "atk_step": 2.52, "def_base": 84, "def_step": 1.8},
        {"hp_base": 288.96, "hp_step": 5.04, "atk_base": 144.48, "atk_step": 2.52, "def_base": 103.2, "def_step": 1.8},
        {"hp_base": 342.72, "hp_step": 5.04, "atk_base": 171.36, "atk_step": 2.52, "def_base": 122.4, "def_step": 1.8},
    ]

    def __init__(self, id: str = "", **kwargs):
        super().__init__(id=id, **kwargs)
        if self.effect is None:
            self.effect = DataBankEffect(self.superimpose)


class DataBankEffect(EquipmentEffect):
    _PARAMS = [
        [0.28],
        [0.35],
        [0.42],
        [0.49],
        [0.56],
    ]
    _SOURCE = "LightCone_20006"

    def __init__(self, superimpose: int = 1) -> None:
        self.superimpose = max(1, min(superimpose, 5))
        self._character: Optional["Character"] = None

    def on_equip(self, character: "Character") -> None:
        from core.enums import StatType, StatModifierType

        p = self._PARAMS[self.superimpose - 1]
        mod = StatModifier(
            stat_type=StatType.ULT_DMG,
            modifier_type=StatModifierType.PERCENT,
            value=p[0],
            source=self._SOURCE,
            dispellable=False,
        )
        character.stats.apply_modifier(mod, "refresh")

    def on_combat_start(self, state: "GameState", character: "Character") -> None:
        pass

    def on_unequip(self, character: "Character") -> None:
        character.stats.purge_source(self._SOURCE)

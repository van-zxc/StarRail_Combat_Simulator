from __future__ import annotations
"""今日亦是和平的一日 (Today Is Another Peaceful Day) — 4★ 智识光锥。

特效: 根据能量上限提高伤害：每点能量+#1[f2]%，最多#2[i]点。

JSON对齐: OnStack 动态 SetDynamicValueByProperty(CasterMaxSP) → AllDamageTypeAddedRatio.
Python: on_equip 静态计算一次 (max_energy 当前不变化, 若未来需支持动态 max_energy 需改为 per-event 重算).
"""

from entities.light_cones.base import BaseLightCone
from entities.base import EquipmentEffect, StatModifier


class TodayIsPeaceful(BaseLightCone):
    _default_id = "21034"
    _default_name = "今日亦是和平的一日"
    _default_path_key = "Mage"

    _PROMOTIONS = [
        {"hp_base": 38.4, "hp_step": 5.76, "atk_base": 24, "atk_step": 3.6, "def_base": 15, "def_step": 2.25},
        {"hp_base": 84.48, "hp_step": 5.76, "atk_base": 52.8, "atk_step": 3.6, "def_base": 33, "def_step": 2.25},
        {"hp_base": 145.92, "hp_step": 5.76, "atk_base": 91.2, "atk_step": 3.6, "def_base": 57, "def_step": 2.25},
        {"hp_base": 207.36, "hp_step": 5.76, "atk_base": 129.6, "atk_step": 3.6, "def_base": 81, "def_step": 2.25},
        {"hp_base": 268.8, "hp_step": 5.76, "atk_base": 168, "atk_step": 3.6, "def_base": 105, "def_step": 2.25},
        {"hp_base": 330.24, "hp_step": 5.76, "atk_base": 206.4, "atk_step": 3.6, "def_base": 129, "def_step": 2.25},
        {"hp_base": 391.68, "hp_step": 5.76, "atk_base": 244.8, "atk_step": 3.6, "def_base": 153, "def_step": 2.25},
    ]

    def __init__(self, id: str = "", **kwargs):
        super().__init__(id=id, **kwargs)
        if self.effect is None:
            self.effect = TodayIsPeacefulEffect(self.superimpose)


class TodayIsPeacefulEffect(EquipmentEffect):
    _PARAMS = [[0.002, 160], [0.0025, 160], [0.003, 160], [0.0035, 160], [0.004, 160]]
    _SOURCE = "LightCone_21034"

    def __init__(self, superimpose: int = 1) -> None:
        self.superimpose = max(1, min(superimpose, 5))

    def on_equip(self, character: "Character") -> None:
        from core.enums import StatType, StatModifierType

        p = self._PARAMS[self.superimpose - 1]
        per_energy = p[0]
        cap = p[1]
        dmg_bonus = min(character.max_energy, cap) * per_energy
        mod = StatModifier(
            stat_type=StatType.DMG_BONUS,
            modifier_type=StatModifierType.PERCENT,
            value=dmg_bonus,
            source=self._SOURCE,
            dispellable=False,
        )
        character.stats.apply_modifier(mod, "refresh")

    def on_combat_start(self, state: "GameState", character: "Character") -> None:
        pass

    def on_unequip(self, character: "Character") -> None:
        character.stats.purge_source(self._SOURCE)

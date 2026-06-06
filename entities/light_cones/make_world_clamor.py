from __future__ import annotations
"""别让世界静下来 (Make the World Clamor) — 4★ 智识光锥。

特效: 进入战斗时恢复#2[i]点能量，终结技伤害提高#1[i]%。
"""

from typing import Optional

from entities.light_cones.base import BaseLightCone
from entities.base import EquipmentEffect, StatModifier


class MakeWorldClamor(BaseLightCone):
    _default_id = "21013"
    _default_name = "别让世界静下来"
    _default_path_key = "Mage"

    _PROMOTIONS = [
        {"hp_base": 38.4, "hp_step": 5.76, "atk_base": 21.6, "atk_step": 3.24, "def_base": 18, "def_step": 2.7},
        {"hp_base": 84.48, "hp_step": 5.76, "atk_base": 47.52, "atk_step": 3.24, "def_base": 39.6, "def_step": 2.7},
        {"hp_base": 145.92, "hp_step": 5.76, "atk_base": 82.08, "atk_step": 3.24, "def_base": 68.4, "def_step": 2.7},
        {"hp_base": 207.36, "hp_step": 5.76, "atk_base": 116.64, "atk_step": 3.24, "def_base": 97.2, "def_step": 2.7},
        {"hp_base": 268.8, "hp_step": 5.76, "atk_base": 151.2, "atk_step": 3.24, "def_base": 126, "def_step": 2.7},
        {"hp_base": 330.24, "hp_step": 5.76, "atk_base": 185.76, "atk_step": 3.24, "def_base": 154.8, "def_step": 2.7},
        {"hp_base": 391.68, "hp_step": 5.76, "atk_base": 220.32, "atk_step": 3.24, "def_base": 183.6, "def_step": 2.7},
    ]

    def __init__(self, id: str = "", **kwargs):
        super().__init__(id=id, **kwargs)
        if self.effect is None:
            self.effect = MakeWorldClamorEffect(self.superimpose)


class MakeWorldClamorEffect(EquipmentEffect):
    _PARAMS = [[0.32, 20], [0.40, 23], [0.48, 26], [0.56, 29], [0.64, 32]]
    _SOURCE = "LightCone_21013"

    def __init__(self, superimpose: int = 1) -> None:
        self.superimpose = max(1, min(superimpose, 5))
        self._character: Optional["Character"] = None
        self._cb_start: Optional[callable] = None

    def on_equip(self, character: "Character") -> None:
        from core.enums import StatType, StatModifierType

        ult_pct = self._PARAMS[self.superimpose - 1][0]
        mod = StatModifier(
            stat_type=StatType.ULT_DMG,
            modifier_type=StatModifierType.PERCENT,
            value=ult_pct,
            source=self._SOURCE,
            dispellable=False,
        )
        character.stats.apply_modifier(mod, "refresh")

    def on_combat_start(self, state: "GameState", character: "Character") -> None:
        from core.events import EventType

        self._character = character
        self._cb_start = lambda **kw: self._on_start()
        state.event_bus.subscribe(EventType.BATTLE_START, self._cb_start)

    def _on_start(self) -> None:
        energy = self._PARAMS[self.superimpose - 1][1]
        self._character.gain_energy(energy, affected_by_err=False)  # JSON: ModifySPNew bypasses ERR

    def on_unequip(self, character: "Character") -> None:
        from core.events import EventType

        character.stats.purge_source(self._SOURCE)
        if self._cb_start is not None and character.event_bus is not None:
            character.event_bus.unsubscribe(EventType.BATTLE_START, self._cb_start)

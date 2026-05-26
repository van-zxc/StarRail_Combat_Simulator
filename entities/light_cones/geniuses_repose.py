from __future__ import annotations
"""天才们的休憩 (Geniuses' Repose) — 4★ 智识光锥。

特效: 攻击力提高#1[i]%，消灭敌方目标后暴击伤害提高#2[i]%，持续#3[i]回合。
"""

from typing import Optional

from entities.light_cones.base import BaseLightCone
from entities.base import EquipmentEffect, StatModifier


class GeniusesRepose(BaseLightCone):
    _default_id = "21020"
    _default_name = "天才们的休憩"
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
            self.effect = GeniusesReposeEffect(self.superimpose)


class GeniusesReposeEffect(EquipmentEffect):
    _PARAMS = [[0.16, 0.24, 3], [0.20, 0.30, 3], [0.24, 0.36, 3], [0.28, 0.42, 3], [0.32, 0.48, 3]]
    _SOURCE = "LightCone_21020"

    def __init__(self, superimpose: int = 1) -> None:
        self.superimpose = max(1, min(superimpose, 5))
        self._character: Optional["Character"] = None
        self._cb_kill: Optional[callable] = None

    def on_equip(self, character: "Character") -> None:
        from core.enums import StatType, StatModifierType

        atk_pct = self._PARAMS[self.superimpose - 1][0]
        mod = StatModifier(
            stat_type=StatType.ATK,
            modifier_type=StatModifierType.PERCENT,
            value=atk_pct,
            source=self._SOURCE,
            dispellable=False,
        )
        character.stats.apply_modifier(mod, "refresh")

    def on_combat_start(self, state: "GameState", character: "Character") -> None:
        from core.events import EventType

        self._character = character
        self._cb_kill = lambda **kw: self._on_kill(kw.get("source"))
        state.event_bus.subscribe(EventType.ON_KILL, self._cb_kill)

    def _on_kill(self, source: "Character") -> None:
        if source is not self._character:
            return
        from core.enums import StatType, StatModifierType

        cd_val = self._PARAMS[self.superimpose - 1][1]
        duration = self._PARAMS[self.superimpose - 1][2]
        mod = StatModifier(
            stat_type=StatType.CRIT_DMG,
            modifier_type=StatModifierType.PERCENT,
            value=cd_val,
            source=self._SOURCE,
            duration=duration,
            dispellable=False,
        )
        self._character.stats.apply_modifier(mod, "refresh")

    def on_unequip(self, character: "Character") -> None:
        from core.events import EventType

        character.stats.purge_source(self._SOURCE)
        if self._cb_kill is not None and character.event_bus is not None:
            character.event_bus.unsubscribe(EventType.ON_KILL, self._cb_kill)

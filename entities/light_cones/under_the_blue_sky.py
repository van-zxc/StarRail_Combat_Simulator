from __future__ import annotations
"""在蓝天下 (Under the Blue Sky) — 4★ 毁灭光锥。

特效: 攻击力提高#1[i]%，消灭敌方目标后暴击率提高#2[i]%，持续#3[i]回合。
"""

from typing import Optional

from entities.light_cones.base import BaseLightCone
from entities.base import EquipmentEffect, StatModifier


class UnderTheBlueSky(BaseLightCone):
    _default_id = "21019"
    _default_name = "在蓝天下"
    _default_path_key = "Warrior"

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
            self.effect = UnderTheBlueSkyEffect(self.superimpose)


class UnderTheBlueSkyEffect(EquipmentEffect):
    _PARAMS = [[0.16, 0.12, 3], [0.20, 0.15, 3], [0.24, 0.18, 3], [0.28, 0.21, 3], [0.32, 0.24, 3]]
    _SOURCE_ATK = "LightCone_21019_ATK"
    _SOURCE_CRIT = "LightCone_21019_CRIT"

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
            source=self._SOURCE_ATK,
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

        p = self._PARAMS[self.superimpose - 1]
        cr_val = p[1]
        duration = p[2]
        mod = StatModifier(
            stat_type=StatType.CRIT_RATE,
            modifier_type=StatModifierType.PERCENT,
            value=cr_val,
            source=self._SOURCE_CRIT,
            duration=duration,
            dispellable=False,
        )
        self._character.stats.apply_modifier(mod, "refresh")

    def on_unequip(self, character: "Character") -> None:
        from core.events import EventType

        character.stats.purge_source(self._SOURCE_ATK)
        character.stats.purge_source(self._SOURCE_CRIT)
        if self._cb_kill is not None and character.event_bus is not None:
            character.event_bus.unsubscribe(EventType.ON_KILL, self._cb_kill)

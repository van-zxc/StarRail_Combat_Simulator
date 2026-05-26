from __future__ import annotations
"""离弦 (Darting Arrow) — 3★ 巡猎光锥。

特效: 消灭敌方目标后，攻击力提高#1[i]%，持续#2[i]回合。
"""

from typing import Optional

from entities.light_cones.base import BaseLightCone
from entities.base import EquipmentEffect, StatModifier


class DartingArrow(BaseLightCone):
    _default_id = "20007"
    _default_name = "离弦"
    _default_path_key = "Rogue"

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
            self.effect = DartingArrowEffect(self.superimpose)


class DartingArrowEffect(EquipmentEffect):
    _PARAMS = [0.24, 0.30, 0.36, 0.42, 0.48]
    _DURATION = 3
    _SOURCE = "LightCone_20007"

    def __init__(self, superimpose: int = 1) -> None:
        self.superimpose = max(1, min(superimpose, 5))
        self._character: Optional["Character"] = None
        self._cb_kill: Optional[callable] = None

    def on_equip(self, character: "Character") -> None:
        pass

    def on_combat_start(self, state: "GameState", character: "Character") -> None:
        from core.events import EventType

        self._character = character
        self._cb_kill = lambda **kw: self._on_kill(kw.get("source"))
        state.event_bus.subscribe(EventType.ON_KILL, self._cb_kill)

    def _on_kill(self, source: "Character") -> None:
        if source is not self._character:
            return
        from core.enums import StatType, StatModifierType

        atk_pct = self._PARAMS[self.superimpose - 1]
        mod = StatModifier(
            stat_type=StatType.ATK,
            modifier_type=StatModifierType.PERCENT,
            value=atk_pct,
            source=self._SOURCE,
            duration=self._DURATION,
            dispellable=False,
        )
        self._character.stats.apply_modifier(mod, "refresh")

    def on_unequip(self, character: "Character") -> None:
        from core.events import EventType

        character.stats.purge_source(self._SOURCE)
        if self._cb_kill is not None and character.event_bus is not None:
            character.event_bus.unsubscribe(EventType.ON_KILL, self._cb_kill)

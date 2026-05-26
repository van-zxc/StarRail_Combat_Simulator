from __future__ import annotations
"""春水初生 (River Flows in Spring) — 4★ 巡猎光锥。

特效: 进入战斗后SPD+#1[i]%，DMG+#2[i]%。受击后失效，下回合结束时恢复。
"""

from typing import Optional

from entities.light_cones.base import BaseLightCone
from entities.base import EquipmentEffect, StatModifier


class RiverFlowsInSpring(BaseLightCone):
    _default_id = "21024"
    _default_name = "春水初生"
    _default_path_key = "Rogue"

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
            self.effect = RiverFlowsInSpringEffect(self.superimpose)


class RiverFlowsInSpringEffect(EquipmentEffect):
    _PARAMS = [[0.08, 0.12], [0.09, 0.15], [0.10, 0.18], [0.11, 0.21], [0.12, 0.24]]
    _SOURCE = "LightCone_21024"
    _STATE_ACTIVE = "active"
    _STATE_BROKEN = "broken"

    def __init__(self, superimpose: int = 1) -> None:
        self.superimpose = max(1, min(superimpose, 5))
        self._character: Optional["Character"] = None
        self._state: str = self._STATE_ACTIVE
        self._cb_start: Optional[callable] = None
        self._cb_hit: Optional[callable] = None
        self._cb_turn_end: Optional[callable] = None

    def _apply_buffs(self) -> None:
        from core.enums import StatType, StatModifierType

        p = self._PARAMS[self.superimpose - 1]
        spd_mod = StatModifier(
            stat_type=StatType.SPD,
            modifier_type=StatModifierType.PERCENT,
            value=p[0],
            source=self._SOURCE,
            dispellable=False,
        )
        dmg_mod = StatModifier(
            stat_type=StatType.DMG_BONUS,
            modifier_type=StatModifierType.PERCENT,
            value=p[1],
            source=self._SOURCE,
            dispellable=False,
        )
        self._character.stats.apply_modifier(spd_mod, "refresh")
        self._character.stats.apply_modifier(dmg_mod, "refresh")

    def on_equip(self, character: "Character") -> None:
        pass

    def on_combat_start(self, state: "GameState", character: "Character") -> None:
        from core.events import EventType

        self._character = character
        self._state = self._STATE_ACTIVE
        self._cb_start = lambda **kw: self._apply_buffs()
        self._cb_hit = lambda **kw: self._on_hit(kw.get("target"))
        self._cb_turn_end = lambda **kw: self._on_turn_end(kw.get("unit"))
        bus = state.event_bus
        bus.subscribe(EventType.BATTLE_START, self._cb_start)
        bus.subscribe(EventType.ON_HIT, self._cb_hit)
        bus.subscribe(EventType.TURN_END, self._cb_turn_end)

    def _on_hit(self, target: "Fighter") -> None:
        if target is not self._character:
            return
        self._state = self._STATE_BROKEN
        self._character.stats.purge_source(self._SOURCE)

    def _on_turn_end(self, unit: "Fighter") -> None:
        if unit is not self._character:
            return
        if self._state == self._STATE_BROKEN:
            self._state = self._STATE_ACTIVE
            self._apply_buffs()

    def on_unequip(self, character: "Character") -> None:
        from core.events import EventType

        character.stats.purge_source(self._SOURCE)
        if character.event_bus is not None:
            bus = character.event_bus
            if self._cb_start is not None:
                bus.unsubscribe(EventType.BATTLE_START, self._cb_start)
            if self._cb_hit is not None:
                bus.unsubscribe(EventType.ON_HIT, self._cb_hit)
            if self._cb_turn_end is not None:
                bus.unsubscribe(EventType.TURN_END, self._cb_turn_end)

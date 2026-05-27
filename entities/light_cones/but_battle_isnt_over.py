from __future__ import annotations
"""但战斗还未结束 (But the Battle Isn't Over) — 5★ 同谐光锥。

特效:
  1. 能量恢复效率提高#1[i]%
  2. 对我方施放终结技时恢复 1 SP（每 2 次可触发 1 次）
  3. 战技后，下一个行动的我方其他目标伤害提高#2[i]%，持续#3[i]回合
"""

from typing import Optional

from entities.light_cones.base import BaseLightCone
from entities.base import EquipmentEffect, StatModifier


class ButBattleIsntOver(BaseLightCone):
    _default_id = "23003"
    _default_name = "但战斗还未结束"
    _default_path_key = "Shaman"

    _PROMOTIONS = [
        {"hp_base": 52.8, "hp_step": 7.92, "atk_base": 24, "atk_step": 3.6, "def_base": 21, "def_step": 3.15},
        {"hp_base": 116.16, "hp_step": 7.92, "atk_base": 52.8, "atk_step": 3.6, "def_base": 46.2, "def_step": 3.15},
        {"hp_base": 200.64, "hp_step": 7.92, "atk_base": 91.2, "atk_step": 3.6, "def_base": 79.8, "def_step": 3.15},
        {"hp_base": 285.12, "hp_step": 7.92, "atk_base": 129.6, "atk_step": 3.6, "def_base": 113.4, "def_step": 3.15},
        {"hp_base": 369.6, "hp_step": 7.92, "atk_base": 168, "atk_step": 3.6, "def_base": 147, "def_step": 3.15},
        {"hp_base": 454.08, "hp_step": 7.92, "atk_base": 206.4, "atk_step": 3.6, "def_base": 180.6, "def_step": 3.15},
        {"hp_base": 538.56, "hp_step": 7.92, "atk_base": 244.8, "atk_step": 3.6, "def_base": 214.2, "def_step": 3.15},
    ]

    def __init__(self, id: str = "", **kwargs):
        super().__init__(id=id, **kwargs)
        if self.effect is None:
            self.effect = ButBattleIsntOverEffect(self.superimpose)


class ButBattleIsntOverEffect(EquipmentEffect):
    _PARAMS = [[0.10, 0.30, 1], [0.12, 0.35, 1], [0.14, 0.40, 1], [0.16, 0.45, 1], [0.18, 0.50, 1]]
    _SOURCE = "LightCone_23003"

    def __init__(self, superimpose: int = 1) -> None:
        self.superimpose = max(1, min(superimpose, 5))
        self._character: Optional["Character"] = None
        self._state: Optional["GameState"] = None
        self._ult_count: int = 0
        self._cb_ult: Optional[callable] = None
        self._cb_after: Optional[callable] = None

    def on_equip(self, character: "Character") -> None:
        from core.enums import StatType, StatModifierType

        err_val = self._PARAMS[self.superimpose - 1][0]
        mod = StatModifier(
            stat_type=StatType.ERR,
            modifier_type=StatModifierType.PERCENT,
            value=err_val,
            source=self._SOURCE,
            dispellable=False,
        )
        character.stats.apply_modifier(mod, "refresh")

    def on_combat_start(self, state: "GameState", character: "Character") -> None:
        from core.events import EventType

        self._character = character
        self._state = state
        self._cb_ult = lambda **kw: self._on_ult(kw.get("character"), kw.get("target"))
        self._cb_after = lambda **kw: self._on_after(kw.get("unit"), kw.get("action_type"))
        state.event_bus.subscribe(EventType.ON_ULTIMATE_INSERTED, self._cb_ult)
        state.event_bus.subscribe(EventType.AFTER_ACTION, self._cb_after)

    def _on_ult(self, caster: "Character", target: "Fighter") -> None:
        if caster is not self._character:
            return
        if target is None or target not in self._state.characters:
            return
        self._ult_count += 1
        if self._ult_count >= 2:
            self._state.skill_points += 1
            self._ult_count = 0

    def _on_after(self, unit: "Character", action_type: object) -> None:
        from core.enums import ActionType, StatType, StatModifierType

        if unit is not self._character:
            return
        if action_type != ActionType.SKILL:
            return
        p = self._PARAMS[self.superimpose - 1]
        dmg_pct = p[1]
        duration = p[2]
        next_ally = None
        min_av = float("inf")
        for char in self._state.characters:
            if char is self._character:
                continue
            if hasattr(char, "is_memosprite") and char.is_memosprite:
                continue
            if char.current_av < min_av:
                min_av = char.current_av
                next_ally = char
        if next_ally is None:
            return
        mod = StatModifier(
            stat_type=StatType.DMG_BONUS,
            modifier_type=StatModifierType.PERCENT,
            value=dmg_pct,
            source=self._SOURCE,
            duration=duration,
            dispellable=False,
        )
        next_ally.stats.apply_modifier(mod, "refresh")

    def on_unequip(self, character: "Character") -> None:
        from core.events import EventType

        for c in getattr(self._state, "characters", []):
            if hasattr(c, "stats"):
                c.stats.purge_source(self._SOURCE)
        if character.event_bus is not None:
            bus = character.event_bus
            if self._cb_ult is not None:
                bus.unsubscribe(EventType.ON_ULTIMATE_INSERTED, self._cb_ult)
            if self._cb_after is not None:
                bus.unsubscribe(EventType.AFTER_ACTION, self._cb_after)

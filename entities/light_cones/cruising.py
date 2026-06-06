from __future__ import annotations
"""星海巡航 (Cruising in the Stellar Sea) — 5★ 巡猎光锥 (Herta Shop)。

三重特效:
  1. 永久暴击率 +#1[i]% (properties CriticalChanceBase → on_equip)
  2. HP≤#2[i]% 目标额外暴击率 +#3[i]% (per-target conditional)
  3. 消灭敌方目标后 ATK +#4[i]%，持续 #5[i] 回合

JSON对齐: Part2 OnBeforeHitAll:HP条件 → 额外 CRIT; Python: ACTION_START/AFTER_ACTION (KI-005 模式)."""

from typing import Optional

from entities.light_cones.base import BaseLightCone
from entities.base import EquipmentEffect, StatModifier


class Cruising(BaseLightCone):
    _default_id = "24001"
    _default_name = "星海巡航"
    _default_path_key = "Rogue"

    _PROMOTIONS = [
        {"hp_base": 43.2, "hp_step": 6.48, "atk_base": 24, "atk_step": 3.6, "def_base": 21, "def_step": 3.15},
        {"hp_base": 95.04, "hp_step": 6.48, "atk_base": 52.8, "atk_step": 3.6, "def_base": 46.2, "def_step": 3.15},
        {"hp_base": 164.16, "hp_step": 6.48, "atk_base": 91.2, "atk_step": 3.6, "def_base": 79.8, "def_step": 3.15},
        {"hp_base": 233.28, "hp_step": 6.48, "atk_base": 129.6, "atk_step": 3.6, "def_base": 113.4, "def_step": 3.15},
        {"hp_base": 302.4, "hp_step": 6.48, "atk_base": 168, "atk_step": 3.6, "def_base": 147, "def_step": 3.15},
        {"hp_base": 371.52, "hp_step": 6.48, "atk_base": 206.4, "atk_step": 3.6, "def_base": 180.6, "def_step": 3.15},
        {"hp_base": 440.64, "hp_step": 6.48, "atk_base": 244.8, "atk_step": 3.6, "def_base": 214.2, "def_step": 3.15},
    ]

    def __init__(self, id: str = "", **kwargs):
        super().__init__(id=id, **kwargs)
        if self.effect is None:
            self.effect = CruisingEffect(self.superimpose)


class CruisingEffect(EquipmentEffect):
    _PARAMS = [
        [0.08, 0.50, 0.08, 0.20, 2],
        [0.10, 0.50, 0.10, 0.25, 2],
        [0.12, 0.50, 0.12, 0.30, 2],
        [0.14, 0.50, 0.14, 0.35, 2],
        [0.16, 0.50, 0.16, 0.40, 2],
    ]
    _SOURCE = "LightCone_24001_CRIT"
    _ATK_SOURCE = "LightCone_24001_ATK"
    _COND_SOURCE = "LightCone_24001_COND"

    def __init__(self, superimpose: int = 1) -> None:
        self.superimpose = max(1, min(superimpose, 5))
        self._character: Optional["Character"] = None
        self._cb_action_start: Optional[callable] = None
        self._cb_after: Optional[callable] = None
        self._cb_kill: Optional[callable] = None

    # ── Part 1: 永久暴击率 ──

    def on_equip(self, character: "Character") -> None:
        from core.enums import StatType, StatModifierType

        val = self._PARAMS[self.superimpose - 1][0]
        mod = StatModifier(
            stat_type=StatType.CRIT_RATE,
            modifier_type=StatModifierType.PERCENT,
            value=val,
            source=self._SOURCE,
            dispellable=False,
        )
        character.stats.apply_modifier(mod, "refresh")

    # ── Part 2+3: 战斗注册 ──

    def on_combat_start(self, state: "GameState", character: "Character") -> None:
        from core.events import EventType

        self._character = character
        self._cb_action_start = lambda **kw: self._on_action_start(
            kw.get("unit"), kw.get("target"))
        self._cb_after = lambda **kw: self._on_after(kw.get("unit"))
        self._cb_kill = lambda **kw: self._on_kill(kw.get("source"))
        bus = state.event_bus
        bus.subscribe(EventType.ACTION_START, self._cb_action_start)
        bus.subscribe(EventType.AFTER_ACTION, self._cb_after)
        bus.subscribe(EventType.ON_KILL, self._cb_kill)

    # ── Part 2: per-target 条件暴击率 ──

    def _on_action_start(self, unit: "Character", target: "Fighter") -> None:
        if unit is not self._character:
            return
        if target is None or not hasattr(target, "max_hp"):
            return
        from core.enums import StatType, StatModifierType

        threshold = self._PARAMS[self.superimpose - 1][1]
        extra = self._PARAMS[self.superimpose - 1][2]
        if target.max_hp > 0 and target.hp / target.max_hp <= threshold:
            mod = StatModifier(
                stat_type=StatType.CRIT_RATE,
                modifier_type=StatModifierType.PERCENT,
                value=extra,
                source=self._COND_SOURCE,
                dispellable=False,
            )
            self._character.stats.apply_modifier(mod, "refresh")
        else:
            self._character.stats.purge_source(self._COND_SOURCE)

    def _on_after(self, unit: "Character") -> None:
        if unit is not self._character:
            return
        self._character.stats.purge_source(self._COND_SOURCE)

    # ── Part 3: ON_KILL → ATK ──

    def _on_kill(self, source: "Character") -> None:
        if source is not self._character:
            return
        from core.enums import StatType, StatModifierType

        atk = self._PARAMS[self.superimpose - 1][3]
        dur = int(self._PARAMS[self.superimpose - 1][4])
        mod = StatModifier(
            stat_type=StatType.ATK,
            modifier_type=StatModifierType.PERCENT,
            value=atk,
            source=self._ATK_SOURCE,
            duration=dur,
            dispellable=False,
        )
        self._character.stats.apply_modifier(mod, "refresh")

    # ── 卸载清理 ──

    def on_unequip(self, character: "Character") -> None:
        from core.events import EventType

        character.stats.purge_source(self._SOURCE)
        character.stats.purge_source(self._ATK_SOURCE)
        character.stats.purge_source(self._COND_SOURCE)
        if character.event_bus is not None:
            bus = character.event_bus
            if self._cb_action_start is not None:
                bus.unsubscribe(EventType.ACTION_START, self._cb_action_start)
            if self._cb_after is not None:
                bus.unsubscribe(EventType.AFTER_ACTION, self._cb_after)
            if self._cb_kill is not None:
                bus.unsubscribe(EventType.ON_KILL, self._cb_kill)

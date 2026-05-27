from __future__ import annotations
"""Night on the Milky Way (银河铁道之夜) — 5★ 智识光锥。

特效:
  #1: 敌方弱点被击破时，DMG提高#1[i]%，持续1回合 (ON_WEAKNESS_BREAK 驱动)
  #2: 场上每有1个敌方目标，ATK提高#2[f1]%，最多5层 (动态叠加)

已知问题: KI-001 — 分裂造物是否计入 enemy count 待实机验证。
"""

from typing import Optional

from entities.light_cones.base import BaseLightCone
from entities.base import EquipmentEffect, StatModifier


class NightOnTheMilkyWay(BaseLightCone):
    _default_id = "23000"
    _default_name = "银河铁道之夜"
    _default_path_key = "Mage"

    _PROMOTIONS = [
        {"hp_base": 52.8, "hp_step": 7.92, "atk_base": 26.4, "atk_step": 3.96, "def_base": 18, "def_step": 2.7},
        {"hp_base": 116.16, "hp_step": 7.92, "atk_base": 58.08, "atk_step": 3.96, "def_base": 39.6, "def_step": 2.7},
        {"hp_base": 200.64, "hp_step": 7.92, "atk_base": 100.32, "atk_step": 3.96, "def_base": 68.4, "def_step": 2.7},
        {"hp_base": 285.12, "hp_step": 7.92, "atk_base": 142.56, "atk_step": 3.96, "def_base": 97.2, "def_step": 2.7},
        {"hp_base": 369.6, "hp_step": 7.92, "atk_base": 184.8, "atk_step": 3.96, "def_base": 126, "def_step": 2.7},
        {"hp_base": 454.08, "hp_step": 7.92, "atk_base": 227.04, "atk_step": 3.96, "def_base": 154.8, "def_step": 2.7},
        {"hp_base": 538.56, "hp_step": 7.92, "atk_base": 269.28, "atk_step": 3.96, "def_base": 183.6, "def_step": 2.7},
    ]

    def __init__(self, id: str = "", **kwargs):
        super().__init__(id=id, **kwargs)
        if self.effect is None:
            self.effect = NightMilkyWayEffect(self.superimpose)


class NightMilkyWayEffect(EquipmentEffect):
    _PARAMS = [
        [0.30, 0.09],
        [0.35, 0.105],
        [0.40, 0.12],
        [0.45, 0.135],
        [0.50, 0.15],
    ]
    _SOURCE = "LightCone_23000"

    def __init__(self, superimpose: int = 1) -> None:
        self.superimpose = max(1, min(superimpose, 5))
        self._character: Optional["Character"] = None
        self._state: Optional["GameState"] = None
        self._cb_break: Optional[callable] = None
        self._cb_death: Optional[callable] = None
        self._cb_wave: Optional[callable] = None

    def on_equip(self, character: "Character") -> None:
        pass

    def on_combat_start(self, state: "GameState", character: "Character") -> None:
        from core.events import EventType

        self._character = character
        self._state = state

        self._cb_break = lambda **kw: self._on_break()
        self._cb_death = lambda **kw: self._recalc_stacks()
        self._cb_wave = lambda **kw: self._recalc_stacks()

        bus = state.event_bus
        bus.subscribe(EventType.ON_WEAKNESS_BREAK, self._cb_break)
        bus.subscribe(EventType.UNIT_DOWNED, self._cb_death)
        bus.subscribe(EventType.WAVE_START, self._cb_wave)

        self._recalc_stacks()

    def _recalc_stacks(self) -> None:
        from core.enums import StatType, StatModifierType

        n = len(self._state.alive_enemies) if self._state else 0
        stacks = min(n, 5)
        atk_pct = stacks * self._PARAMS[self.superimpose - 1][1]

        if atk_pct > 0:
            mod = StatModifier(
                stat_type=StatType.ATK,
                modifier_type=StatModifierType.PERCENT,
                value=atk_pct,
                source=self._SOURCE,
                dispellable=False,
            )
            self._character.stats.apply_modifier(mod, "refresh")
        else:
            self._character.stats.purge_source(self._SOURCE)

    def _on_break(self) -> None:
        from core.enums import StatType, StatModifierType

        dmg_pct = self._PARAMS[self.superimpose - 1][0]
        mod = StatModifier(
            stat_type=StatType.DMG_BONUS,
            modifier_type=StatModifierType.PERCENT,
            value=dmg_pct,
            source=f"{self._SOURCE}_DMG",
            duration=1,
            dispellable=False,
        )
        self._character.stats.apply_modifier(mod, "refresh")

    def on_unequip(self, character: "Character") -> None:
        from core.events import EventType

        character.stats.purge_source(self._SOURCE)
        character.stats.purge_source(f"{self._SOURCE}_DMG")

        if character.event_bus is not None:
            bus = character.event_bus
            if self._cb_break is not None:
                bus.unsubscribe(EventType.ON_WEAKNESS_BREAK, self._cb_break)
            if self._cb_death is not None:
                bus.unsubscribe(EventType.UNIT_DOWNED, self._cb_death)
            if self._cb_wave is not None:
                bus.unsubscribe(EventType.WAVE_START, self._cb_wave)

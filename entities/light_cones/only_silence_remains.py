from __future__ import annotations
"""唯有沉默 (Only Silence Remains) — 4★ 巡猎光锥。

特效: 攻击力提高#1[i]%。场上敌方目标≤2时，暴击率提高#2[i]%。
"""

from typing import Optional

from entities.light_cones.base import BaseLightCone
from entities.base import EquipmentEffect, StatModifier


class OnlySilenceRemains(BaseLightCone):
    _default_id = "21003"
    _default_name = "唯有沉默"
    _default_path_key = "Rogue"

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
            self.effect = OnlySilenceRemainsEffect(self.superimpose)


class OnlySilenceRemainsEffect(EquipmentEffect):
    _PARAMS = [[0.16, 0.12], [0.20, 0.15], [0.24, 0.18], [0.28, 0.21], [0.32, 0.24]]
    _SOURCE = "LightCone_21003"

    def __init__(self, superimpose: int = 1) -> None:
        self.superimpose = max(1, min(superimpose, 5))
        self._character: Optional["Character"] = None
        self._state: Optional["GameState"] = None
        self._cb_kill: Optional[callable] = None
        self._cb_wave: Optional[callable] = None

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

    def _recalc_crit(self) -> None:
        from core.enums import StatType, StatModifierType

        crit_val = self._PARAMS[self.superimpose - 1][1]
        n = len(self._state.alive_enemies) if self._state else 0

        if n <= 2 and n > 0:
            mod = StatModifier(
                stat_type=StatType.CRIT_RATE,
                modifier_type=StatModifierType.PERCENT,
                value=crit_val,
                source=self._SOURCE,
                dispellable=False,
            )
            self._character.stats.apply_modifier(mod, "refresh")
        else:
            self._character.stats.purge_source(self._SOURCE)

    def on_combat_start(self, state: "GameState", character: "Character") -> None:
        from core.events import EventType

        self._character = character
        self._state = state
        self._cb_kill = lambda **kw: self._recalc_crit()
        self._cb_wave = lambda **kw: self._recalc_crit()
        bus = state.event_bus
        bus.subscribe(EventType.UNIT_DOWNED, self._cb_kill)
        bus.subscribe(EventType.WAVE_START, self._cb_wave)
        self._recalc_crit()

    def on_unequip(self, character: "Character") -> None:
        from core.events import EventType

        character.stats.purge_source(self._SOURCE)
        if character.event_bus is not None:
            bus = character.event_bus
            if self._cb_kill is not None:
                bus.unsubscribe(EventType.UNIT_DOWNED, self._cb_kill)
            if self._cb_wave is not None:
                bus.unsubscribe(EventType.WAVE_START, self._cb_wave)

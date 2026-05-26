from __future__ import annotations
"""记忆中的模样 (Memories of the Past) — 4★ 同谐光锥。

特效: 击破特攻提高#1[i]%，施放攻击后额外恢复#2[i]点能量（1次/回合）。
"""

from typing import Optional

from entities.light_cones.base import BaseLightCone
from entities.base import EquipmentEffect, StatModifier


class MemoriesOfThePast(BaseLightCone):
    _default_id = "21004"
    _default_name = "记忆中的模样"
    _default_path_key = "Shaman"

    _PROMOTIONS = [
        {"hp_base": 43.2, "hp_step": 6.48, "atk_base": 19.2, "atk_step": 2.88, "def_base": 18, "def_step": 2.7},
        {"hp_base": 95.04, "hp_step": 6.48, "atk_base": 42.24, "atk_step": 2.88, "def_base": 39.6, "def_step": 2.7},
        {"hp_base": 164.16, "hp_step": 6.48, "atk_base": 72.96, "atk_step": 2.88, "def_base": 68.4, "def_step": 2.7},
        {"hp_base": 233.28, "hp_step": 6.48, "atk_base": 103.68, "atk_step": 2.88, "def_base": 97.2, "def_step": 2.7},
        {"hp_base": 302.4, "hp_step": 6.48, "atk_base": 134.4, "atk_step": 2.88, "def_base": 126, "def_step": 2.7},
        {"hp_base": 371.52, "hp_step": 6.48, "atk_base": 165.12, "atk_step": 2.88, "def_base": 154.8, "def_step": 2.7},
        {"hp_base": 440.64, "hp_step": 6.48, "atk_base": 195.84, "atk_step": 2.88, "def_base": 183.6, "def_step": 2.7},
    ]

    def __init__(self, id: str = "", **kwargs):
        super().__init__(id=id, **kwargs)
        if self.effect is None:
            self.effect = MemoriesOfThePastEffect(self.superimpose)


class MemoriesOfThePastEffect(EquipmentEffect):
    _PARAMS = [[0.28, 4], [0.35, 5], [0.42, 6], [0.49, 7], [0.56, 8]]
    _SOURCE = "LightCone_21004"

    def __init__(self, superimpose: int = 1) -> None:
        self.superimpose = max(1, min(superimpose, 5))
        self._character: Optional["Character"] = None
        self._triggered_this_turn: bool = False
        self._cb_turn_start: Optional[callable] = None
        self._cb_damage_dealt: Optional[callable] = None

    def on_equip(self, character: "Character") -> None:
        from core.enums import StatType, StatModifierType

        be_pct = self._PARAMS[self.superimpose - 1][0]
        mod = StatModifier(
            stat_type=StatType.BREAK_EFFECT,
            modifier_type=StatModifierType.PERCENT,
            value=be_pct,
            source=self._SOURCE,
            dispellable=False,
        )
        character.stats.apply_modifier(mod, "refresh")

    def on_combat_start(self, state: "GameState", character: "Character") -> None:
        from core.events import EventType

        self._character = character
        self._cb_turn_start = lambda **kw: self._on_turn_start(kw.get("unit"))
        self._cb_damage_dealt = lambda **kw: self._on_damage_dealt(kw.get("source"))
        bus = state.event_bus
        bus.subscribe(EventType.TURN_START, self._cb_turn_start)
        bus.subscribe(EventType.ON_DAMAGE_DEALT, self._cb_damage_dealt)

    def _on_turn_start(self, unit: "Fighter") -> None:
        if unit is self._character:
            self._triggered_this_turn = False

    def _on_damage_dealt(self, source: "Character") -> None:
        if source is not self._character:
            return
        if self._triggered_this_turn:
            return
        self._triggered_this_turn = True
        energy = self._PARAMS[self.superimpose - 1][1]
        self._character.gain_energy(energy)

    def on_unequip(self, character: "Character") -> None:
        from core.events import EventType

        character.stats.purge_source(self._SOURCE)
        if character.event_bus is not None:
            bus = character.event_bus
            if self._cb_turn_start is not None:
                bus.unsubscribe(EventType.TURN_START, self._cb_turn_start)
            if self._cb_damage_dealt is not None:
                bus.unsubscribe(EventType.ON_DAMAGE_DEALT, self._cb_damage_dealt)

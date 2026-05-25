from __future__ import annotations

"""戍卫风雪的铁卫 — 4件套装 (2件: 受伤害降低8%, 4件: 回合开始时HP≤50%则回8%生命+5能量)。"""

from typing import Optional

from core.enums import StatType, StatModifierType
from entities.base import StatModifier
from entities.relics.base import BaseRelic, RelicSetEffect
from starrail_combat import RelicPart


class GuardSnowHead(BaseRelic):
    _default_part = RelicPart.HEAD
    _default_set_id = "106"
    _default_main_stat = StatModifier(StatType.HP, StatModifierType.FLAT, 705.0)
    _default_sub_stats = []


class GuardSnowHands(BaseRelic):
    _default_part = RelicPart.HANDS
    _default_set_id = "106"
    _default_main_stat = StatModifier(StatType.ATK, StatModifierType.FLAT, 352.0)
    _default_sub_stats = []


class GuardSnowBody(BaseRelic):
    _default_part = RelicPart.BODY
    _default_set_id = "106"
    _default_main_stat = None
    _default_sub_stats = []


class GuardSnowFeet(BaseRelic):
    _default_part = RelicPart.FEET
    _default_set_id = "106"
    _default_main_stat = None
    _default_sub_stats = []


class GuardOfWutheringSnow(RelicSetEffect):
    set_id = "106"
    set_type = "cavern"

    _SOURCE_2PC = "RelicSet_106_2pc"
    _SOURCE_4PC = "RelicSet_106_4pc"

    def __init__(self) -> None:
        self._character: Optional["Character"] = None
        self._cb_turn: Optional[callable] = None

    def on_equip(self, character, piece_count):
        if piece_count >= 2:
            character.stats.add_modifier(StatModifier(
                StatType.DMG_MITIGATION, StatModifierType.PERCENT, 0.08,
                source=self._SOURCE_2PC, dispellable=False,
            ))

    def on_combat_start(self, state, character):
        from core.events import EventType

        self._character = character
        self._cb_turn = lambda **kw: self._on_turn_start(**kw)
        state.event_bus.subscribe(EventType.TURN_START, self._cb_turn)

    def _on_turn_start(self, **kwargs):
        if kwargs.get("unit") is not self._character:
            return
        if self._character.hp / self._character.max_hp > 0.50:
            return
        heal = int(self._character.max_hp * 0.08)
        self._character.receive_heal(heal)
        self._character.gain_energy(5.0, affected_by_err=True)

    def on_unequip(self, character):
        from core.events import EventType

        character.stats.purge_source(self._SOURCE_2PC)
        if self._cb_turn is not None and character.event_bus is not None:
            character.event_bus.unsubscribe(EventType.TURN_START, self._cb_turn)

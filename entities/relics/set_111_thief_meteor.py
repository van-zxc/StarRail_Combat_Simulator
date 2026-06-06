from __future__ import annotations

"""流星追迹的怪盗 — 4件套装 (2件: 击破特攻+16%, 4件: 击破特攻+16% & 击破弱点后恢复3能量)。"""

from typing import Optional

from core.enums import StatType, StatModifierType
from entities.base import StatModifier
from entities.relics.base import BaseRelic, RelicSetEffect
from starrail_combat import RelicPart


class ThiefMeteorHead(BaseRelic):
    _default_part = RelicPart.HEAD
    _default_set_id = "111"
    _default_main_stat = StatModifier(StatType.HP, StatModifierType.FLAT, 705.0)
    _default_sub_stats = []


class ThiefMeteorHands(BaseRelic):
    _default_part = RelicPart.HANDS
    _default_set_id = "111"
    _default_main_stat = StatModifier(StatType.ATK, StatModifierType.FLAT, 352.0)
    _default_sub_stats = []


class ThiefMeteorBody(BaseRelic):
    _default_part = RelicPart.BODY
    _default_set_id = "111"
    _default_main_stat = None
    _default_sub_stats = []


class ThiefMeteorFeet(BaseRelic):
    _default_part = RelicPart.FEET
    _default_set_id = "111"
    _default_main_stat = None
    _default_sub_stats = []


class ThiefOfShootingMeteor(RelicSetEffect):
    set_id = "111"
    set_type = "cavern"

    _SOURCE_2PC = "RelicSet_111_2pc"
    _SOURCE_4PC_BE = "RelicSet_111_4pc_be"

    def __init__(self) -> None:
        self._character: Optional["Character"] = None
        self._piece_count: int = 0
        self._cb_break: Optional[callable] = None

    def on_equip(self, character, piece_count):
        self._piece_count = piece_count
        if piece_count >= 2:
            character.stats.add_modifier(StatModifier(
                StatType.BREAK_EFFECT, StatModifierType.PERCENT, 0.16,
                source=self._SOURCE_2PC, dispellable=False,
            ))
        if piece_count >= 4:
            character.stats.add_modifier(StatModifier(
                StatType.BREAK_EFFECT, StatModifierType.PERCENT, 0.16,
                source=self._SOURCE_4PC_BE, dispellable=False,
            ))

    def on_combat_start(self, state, character):
        from core.events import EventType

        self._character = character
        if self._piece_count >= 4:
            self._cb_break = lambda **kw: self._on_weakness_break(**kw)
            state.event_bus.subscribe(EventType.ON_WEAKNESS_BREAK, self._cb_break)

    def _on_weakness_break(self, **kwargs):
        if kwargs.get("source") is not self._character:
            return
        self._character.gain_energy(3.0, affected_by_err=False)  # JSON: ModifySPNew bypasses ERR

    def on_unequip(self, character):
        from core.events import EventType

        character.stats.purge_source(self._SOURCE_2PC)
        character.stats.purge_source(self._SOURCE_4PC_BE)
        if self._cb_break is not None and character.event_bus is not None:
            character.event_bus.unsubscribe(EventType.ON_WEAKNESS_BREAK, self._cb_break)

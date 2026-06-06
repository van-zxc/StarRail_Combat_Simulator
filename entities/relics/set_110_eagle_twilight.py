from __future__ import annotations

"""晨昏交界的翔鹰 — 4件套装 (2件: 风属性伤害+10%, 4件: 施放终结技后行动提前25%)。"""

from typing import Optional

from core.enums import StatType, StatModifierType
from entities.base import StatModifier
from entities.relics.base import BaseRelic, RelicSetEffect
from starrail_combat import ActionType, RelicPart


class EagleTwilightHead(BaseRelic):
    _default_part = RelicPart.HEAD
    _default_set_id = "110"
    _default_main_stat = StatModifier(StatType.HP, StatModifierType.FLAT, 705.0)
    _default_sub_stats = []


class EagleTwilightHands(BaseRelic):
    _default_part = RelicPart.HANDS
    _default_set_id = "110"
    _default_main_stat = StatModifier(StatType.ATK, StatModifierType.FLAT, 352.0)
    _default_sub_stats = []


class EagleTwilightBody(BaseRelic):
    _default_part = RelicPart.BODY
    _default_set_id = "110"
    _default_main_stat = None
    _default_sub_stats = []


class EagleTwilightFeet(BaseRelic):
    _default_part = RelicPart.FEET
    _default_set_id = "110"
    _default_main_stat = None
    _default_sub_stats = []


class EagleOfTwilightLine(RelicSetEffect):
    set_id = "110"
    set_type = "cavern"

    _SOURCE_2PC = "RelicSet_110_2pc"

    def __init__(self) -> None:
        self._character: Optional["Character"] = None
        self._cb_after: Optional[callable] = None

    def on_equip(self, character, piece_count):
        if piece_count >= 2:
            character.stats.add_modifier(StatModifier(
                StatType.WIND_DMG_BONUS, StatModifierType.PERCENT, 0.10,
                source=self._SOURCE_2PC, dispellable=False,
            ))

    def on_combat_start(self, state, character):
        from core.events import EventType

        self._character = character
        self._cb_after = lambda **kw: self._on_after_action(**kw)
        state.event_bus.subscribe(EventType.AFTER_ACTION, self._cb_after)  # JSON: OnAfterSkillUse:Ultra

    def _on_after_action(self, **kwargs):
        if kwargs.get("unit") is not self._character:
            return
        if kwargs.get("action_type") is not ActionType.ULTIMATE:
            return
        self._character.advance_action(0.25)

    def on_unequip(self, character):
        from core.events import EventType

        character.stats.purge_source(self._SOURCE_2PC)
        if self._cb_after is not None and character.event_bus is not None:
            character.event_bus.unsubscribe(EventType.AFTER_ACTION, self._cb_after)

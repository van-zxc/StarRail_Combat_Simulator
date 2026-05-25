from __future__ import annotations

"""密林卧雪的猎人 — 4件套装 (2件: 冰伤+10%, 4件: 终结技后暴伤+25%持续2回合)。"""

from typing import Optional

from core.enums import StatType, StatModifierType
from entities.base import StatModifier
from entities.relics.base import BaseRelic, RelicSetEffect
from starrail_combat import ActionType, RelicPart


class GlacialForestHead(BaseRelic):
    _default_part = RelicPart.HEAD
    _default_set_id = "104"
    _default_main_stat = StatModifier(StatType.HP, StatModifierType.FLAT, 705.0)
    _default_sub_stats = []


class GlacialForestHands(BaseRelic):
    _default_part = RelicPart.HANDS
    _default_set_id = "104"
    _default_main_stat = StatModifier(StatType.ATK, StatModifierType.FLAT, 352.0)
    _default_sub_stats = []


class GlacialForestBody(BaseRelic):
    _default_part = RelicPart.BODY
    _default_set_id = "104"
    _default_main_stat = None
    _default_sub_stats = []


class GlacialForestFeet(BaseRelic):
    _default_part = RelicPart.FEET
    _default_set_id = "104"
    _default_main_stat = None
    _default_sub_stats = []


class HunterOfGlacialForest(RelicSetEffect):
    set_id = "104"
    set_type = "cavern"

    _SOURCE_2PC = "RelicSet_104_2pc"
    _SOURCE_4PC = "RelicSet_104_4pc"

    def __init__(self) -> None:
        self._character: Optional["Character"] = None
        self._cb_after: Optional[callable] = None
        self._cb_ultimate: Optional[callable] = None

    def on_equip(self, character, piece_count):
        if piece_count >= 2:
            character.stats.add_modifier(StatModifier(
                StatType.ICE_DMG_BONUS, StatModifierType.PERCENT, 0.10,
                source=self._SOURCE_2PC, dispellable=False,
            ))

    def on_combat_start(self, state, character):
        from core.events import EventType

        self._character = character
        self._cb_after = lambda **kw: self._on_after_action(**kw)
        self._cb_ultimate = lambda **kw: self._on_ultimate(**kw)
        state.event_bus.subscribe(EventType.AFTER_ACTION, self._cb_after)
        state.event_bus.subscribe(EventType.ON_ULTIMATE_INSERTED, self._cb_ultimate)

    def _on_after_action(self, **kwargs):
        if kwargs.get("unit") is not self._character:
            return
        if kwargs.get("action_type") is not ActionType.ULTIMATE:
            return
        self._apply_buff()

    def _on_ultimate(self, **kwargs):
        if kwargs.get("character") is not self._character:
            return
        self._apply_buff()

    def _apply_buff(self):
        mod = StatModifier(
            StatType.CRIT_DMG, StatModifierType.PERCENT, 0.25,
            source=self._SOURCE_4PC, duration=2, dispellable=False,
        )
        self._character.stats.apply_modifier(mod, "refresh")

    def on_unequip(self, character):
        from core.events import EventType

        character.stats.purge_source(self._SOURCE_2PC)
        character.stats.purge_source(self._SOURCE_4PC)
        if self._cb_after is not None and character.event_bus is not None:
            character.event_bus.unsubscribe(EventType.AFTER_ACTION, self._cb_after)
        if self._cb_ultimate is not None and character.event_bus is not None:
            character.event_bus.unsubscribe(EventType.ON_ULTIMATE_INSERTED, self._cb_ultimate)

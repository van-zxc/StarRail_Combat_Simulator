from __future__ import annotations

"""熔岩锻铸的火匠 — 4件套装 (2件: 火伤+10%, 4件: 战技伤+12% + 终结技后下一击火伤+12%)。"""

from typing import Optional

from core.enums import StatType, StatModifierType
from entities.base import StatModifier
from entities.relics.base import BaseRelic, RelicSetEffect
from starrail_combat import ActionType, RelicPart


class FiresmithHead(BaseRelic):
    _default_part = RelicPart.HEAD
    _default_set_id = "107"
    _default_main_stat = StatModifier(StatType.HP, StatModifierType.FLAT, 705.0)
    _default_sub_stats = []


class FiresmithHands(BaseRelic):
    _default_part = RelicPart.HANDS
    _default_set_id = "107"
    _default_main_stat = StatModifier(StatType.ATK, StatModifierType.FLAT, 352.0)
    _default_sub_stats = []


class FiresmithBody(BaseRelic):
    _default_part = RelicPart.BODY
    _default_set_id = "107"
    _default_main_stat = None
    _default_sub_stats = []


class FiresmithFeet(BaseRelic):
    _default_part = RelicPart.FEET
    _default_set_id = "107"
    _default_main_stat = None
    _default_sub_stats = []


class FiresmithOfLavaForging(RelicSetEffect):
    set_id = "107"
    set_type = "cavern"

    _SOURCE_2PC = "RelicSet_107_2pc"
    _SOURCE_4PC_SKILL = "RelicSet_107_4pc_skill"
    _SOURCE_4PC_ULT = "RelicSet_107_4pc_ult"

    def __init__(self) -> None:
        self._character: Optional["Character"] = None
        self._cb_after: Optional[callable] = None
        self._cb_ultimate: Optional[callable] = None
        self._buff_pending: bool = False

    def on_equip(self, character, piece_count):
        from core.enums import StatType, StatModifierType

        if piece_count >= 2:
            character.stats.add_modifier(StatModifier(
                StatType.FIRE_DMG_BONUS, StatModifierType.PERCENT, 0.10,
                source=self._SOURCE_2PC, dispellable=False,
            ))
        if piece_count >= 4:
            character.stats.add_modifier(StatModifier(
                StatType.SKILL_DMG, StatModifierType.PERCENT, 0.12,
                source=self._SOURCE_4PC_SKILL, dispellable=False,
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
        if self._buff_pending:
            self._remove_ult_buff()
        if kwargs.get("action_type") is ActionType.ULTIMATE:
            self._apply_ult_buff()

    def _on_ultimate(self, **kwargs):
        if kwargs.get("character") is not self._character:
            return
        if self._buff_pending:
            self._remove_ult_buff()
        self._apply_ult_buff()

    def _apply_ult_buff(self):
        mod = StatModifier(
            StatType.FIRE_DMG_BONUS, StatModifierType.PERCENT, 0.12,
            source=self._SOURCE_4PC_ULT, dispellable=False,
        )
        self._character.stats.apply_modifier(mod, "refresh")
        self._buff_pending = True

    def _remove_ult_buff(self):
        self._character.stats.purge_source(self._SOURCE_4PC_ULT)
        self._buff_pending = False

    def on_unequip(self, character):
        from core.events import EventType

        character.stats.purge_source(self._SOURCE_2PC)
        character.stats.purge_source(self._SOURCE_4PC_SKILL)
        character.stats.purge_source(self._SOURCE_4PC_ULT)
        if self._cb_after is not None and character.event_bus is not None:
            character.event_bus.unsubscribe(EventType.AFTER_ACTION, self._cb_after)
        if self._cb_ultimate is not None and character.event_bus is not None:
            character.event_bus.unsubscribe(EventType.ON_ULTIMATE_INSERTED, self._cb_ultimate)

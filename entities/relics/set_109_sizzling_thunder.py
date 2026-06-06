from __future__ import annotations

"""激奏雷电的乐队 — 4件套装 (2件: 雷属性伤害+10%, 4件: 施放战技后攻击力+20%持续1回合)。"""

from typing import Optional

from core.enums import StatType, StatModifierType
from entities.base import StatModifier
from entities.relics.base import BaseRelic, RelicSetEffect
from starrail_combat import ActionType, RelicPart


class SizzlingThunderHead(BaseRelic):
    _default_part = RelicPart.HEAD
    _default_set_id = "109"
    _default_main_stat = StatModifier(StatType.HP, StatModifierType.FLAT, 705.0)
    _default_sub_stats = []


class SizzlingThunderHands(BaseRelic):
    _default_part = RelicPart.HANDS
    _default_set_id = "109"
    _default_main_stat = StatModifier(StatType.ATK, StatModifierType.FLAT, 352.0)
    _default_sub_stats = []


class SizzlingThunderBody(BaseRelic):
    _default_part = RelicPart.BODY
    _default_set_id = "109"
    _default_main_stat = None
    _default_sub_stats = []


class SizzlingThunderFeet(BaseRelic):
    _default_part = RelicPart.FEET
    _default_set_id = "109"
    _default_main_stat = None
    _default_sub_stats = []


class BandOfSizzlingThunder(RelicSetEffect):
    set_id = "109"
    set_type = "cavern"

    def __init__(self) -> None:
        self._character: Optional["Character"] = None
        self._cb_skill: Optional[callable] = None

    def on_equip(self, character, piece_count):
        if piece_count >= 2:
            character.stats.add_modifier(StatModifier(
                StatType.THUNDER_DMG_BONUS, StatModifierType.PERCENT, 0.10,
                source="RelicSet_109_2pc", dispellable=False,
            ))

    def on_combat_start(self, state, character):
        from core.events import EventType

        self._character = character
        self._cb_skill = lambda **kw: self._on_action_start(**kw)
        state.event_bus.subscribe(EventType.ACTION_START, self._cb_skill)  # JSON: OnBeforeSkillUse:Skill

    def _on_action_start(self, **kwargs):
        if kwargs.get("unit") is not self._character:
            return
        if kwargs.get("action_type") is not ActionType.SKILL:
            return
        mod = StatModifier(
            StatType.ATK, StatModifierType.PERCENT, 0.20,
            source="RelicSet_109_4pc", duration=1, dispellable=False,
        )
        self._character.stats.apply_modifier(mod, "refresh")

    def on_unequip(self, character):
        from core.events import EventType

        character.stats.purge_source("RelicSet_109_2pc")
        character.stats.purge_source("RelicSet_109_4pc")
        if self._cb_skill is not None and character.event_bus is not None:
            character.event_bus.unsubscribe(EventType.ACTION_START, self._cb_skill)

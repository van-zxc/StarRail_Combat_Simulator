from __future__ import annotations

"""净庭教宗的圣骑士 — 4件套装 (2件: 防御力+15%, 4件: 护盾量+20%)。"""

from core.enums import StatType, StatModifierType
from entities.base import StatModifier
from entities.relics.base import BaseRelic, RelicSetEffect
from starrail_combat import RelicPart


class KnightPurityHead(BaseRelic):
    _default_part = RelicPart.HEAD
    _default_set_id = "103"
    _default_main_stat = StatModifier(StatType.HP, StatModifierType.FLAT, 705.0)
    _default_sub_stats = []


class KnightPurityHands(BaseRelic):
    _default_part = RelicPart.HANDS
    _default_set_id = "103"
    _default_main_stat = StatModifier(StatType.ATK, StatModifierType.FLAT, 352.0)
    _default_sub_stats = []


class KnightPurityBody(BaseRelic):
    _default_part = RelicPart.BODY
    _default_set_id = "103"
    _default_main_stat = None
    _default_sub_stats = []


class KnightPurityFeet(BaseRelic):
    _default_part = RelicPart.FEET
    _default_set_id = "103"
    _default_main_stat = None
    _default_sub_stats = []


class KnightOfPurityPalace(RelicSetEffect):
    set_id = "103"
    set_type = "cavern"

    _SOURCE_2PC = "RelicSet_103_2pc"
    _SOURCE_4PC = "RelicSet_103_4pc"

    def on_equip(self, character, piece_count):
        if piece_count >= 2:
            character.stats.add_modifier(StatModifier(
                StatType.DEF, StatModifierType.PERCENT, 0.15,
                source=self._SOURCE_2PC, dispellable=False,
            ))
        if piece_count >= 4:
            character.stats.add_modifier(StatModifier(
                StatType.SHIELD_BONUS, StatModifierType.PERCENT, 0.20,
                source=self._SOURCE_4PC, dispellable=False,
            ))

    def on_unequip(self, character):
        character.stats.purge_source(self._SOURCE_2PC)
        character.stats.purge_source(self._SOURCE_4PC)

from __future__ import annotations

"""野穗伴行的快枪手 — 4件套装 (2件: ATK+12%, 4件: SPD+6% & 普攻伤害+10%)。"""

from core.enums import StatType, StatModifierType
from entities.base import StatModifier
from entities.relics.base import BaseRelic, RelicSetEffect
from starrail_combat import RelicPart


class MusketeerHead(BaseRelic):
    _default_part = RelicPart.HEAD
    _default_set_id = "102"
    _default_main_stat = StatModifier(StatType.HP, StatModifierType.FLAT, 705.0)
    _default_sub_stats = [
        StatModifier(StatType.ATK, StatModifierType.PERCENT, 0.032),
        StatModifier(StatType.CRIT_RATE, StatModifierType.PERCENT, 0.025),
    ]


class MusketeerHands(BaseRelic):
    _default_part = RelicPart.HANDS
    _default_set_id = "102"
    _default_main_stat = StatModifier(StatType.ATK, StatModifierType.FLAT, 352.0)
    _default_sub_stats = []


class MusketeerBody(BaseRelic):
    _default_part = RelicPart.BODY
    _default_set_id = "102"
    _default_main_stat = StatModifier(StatType.ATK, StatModifierType.PERCENT, 0.432)
    _default_sub_stats = []


class MusketeerFeet(BaseRelic):
    _default_part = RelicPart.FEET
    _default_set_id = "102"
    _default_main_stat = StatModifier(StatType.ATK, StatModifierType.PERCENT, 0.432)
    _default_sub_stats = []


class MusketeerOfWildWheat(RelicSetEffect):
    set_id = "102"
    set_type = "cavern"

    def on_equip(self, character, piece_count):
        if piece_count >= 2:
            character.stats.add_modifier(StatModifier(
                StatType.ATK, StatModifierType.PERCENT, 0.12,
                source="RelicSet_102_2pc", dispellable=False,
            ))
        if piece_count >= 4:
            character.stats.add_modifier(StatModifier(
                StatType.SPD, StatModifierType.PERCENT, 0.06,
                source="RelicSet_102_4pc", dispellable=False,
            ))
            character.stats.add_modifier(StatModifier(
                StatType.BASIC_ATK_DMG, StatModifierType.PERCENT, 0.10,
                source="RelicSet_102_4pc", dispellable=False,
            ))

    def on_unequip(self, character):
        character.stats.purge_source("RelicSet_102_2pc")
        character.stats.purge_source("RelicSet_102_4pc")

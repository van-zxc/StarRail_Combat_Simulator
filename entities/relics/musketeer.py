from __future__ import annotations

"""快枪手的野穗 — 4件套装 (2件: ATK+12%, 4件: SPD+6% & 普攻伤害+10%)。"""

from starrail_combat import RelicPart, StatModifierType, StatType
from entities.base import StatModifier
from entities.relics.base import BaseRelic

SET_ID = "Musketeer"


class MusketeerHead(BaseRelic):
    _default_part = RelicPart.HEAD
    _default_set_id = SET_ID
    _default_main_stat = StatModifier(StatType.HP, StatModifierType.FLAT, 705.0)
    _default_sub_stats = [
        StatModifier(StatType.ATK, StatModifierType.PERCENT, 0.032),
        StatModifier(StatType.CRIT_RATE, StatModifierType.PERCENT, 0.025),
    ]


class MusketeerHands(BaseRelic):
    _default_part = RelicPart.HANDS
    _default_set_id = SET_ID
    _default_main_stat = StatModifier(StatType.ATK, StatModifierType.FLAT, 352.0)
    _default_sub_stats = []


class MusketeerBody(BaseRelic):
    _default_part = RelicPart.BODY
    _default_set_id = SET_ID
    _default_main_stat = StatModifier(StatType.ATK, StatModifierType.PERCENT, 0.432)
    _default_sub_stats = []


class MusketeerFeet(BaseRelic):
    _default_part = RelicPart.FEET
    _default_set_id = SET_ID
    _default_main_stat = StatModifier(StatType.ATK, StatModifierType.PERCENT, 0.432)
    _default_sub_stats = []


# 套装效果 (预留 — Phase 未来激活 RelicSetManager)
SET_EFFECTS = {
    2: [
        StatModifier(StatType.ATK, StatModifierType.PERCENT, 0.12, source="Musketeer_2pc"),
    ],
    4: [
        StatModifier(StatType.SPD, StatModifierType.PERCENT, 0.06, source="Musketeer_4pc"),
        # 普攻造成伤害提高 10% — 需特殊乘区，暂用 DMG_BONUS 近似
        StatModifier(StatType.DMG_BONUS, StatModifierType.FLAT, 0.10, source="Musketeer_4pc"),
    ],
}

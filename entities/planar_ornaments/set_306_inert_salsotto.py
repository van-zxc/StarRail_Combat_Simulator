from __future__ import annotations

"""停转的萨尔索图 — 2件套 (使装备者的暴击率提高8%。当装备者的当前暴击率
大于等于50%时，终结技和追加攻击造成的伤害提高15%)。"""

from typing import Optional

from core.enums import StatType, StatModifierType
from entities.base import StatModifier
from entities.relics.base import BaseRelic, RelicSetEffect
from starrail_combat import RelicPart


class InertSalsottoSphere(BaseRelic):
    _default_part = RelicPart.PLANAR_SPHERE
    _default_set_id = "306"


class InertSalsottoRope(BaseRelic):
    _default_part = RelicPart.LINK_ROPE
    _default_set_id = "306"


class InertSalsotto(RelicSetEffect):
    set_id = "306"
    set_type = "planar"

    _SOURCE_2PC = "RelicSet_306_2pc"
    _SOURCE_ULT = "RelicSet_306_2pc_ult"
    _SOURCE_FUA = "RelicSet_306_2pc_fua"

    def __init__(self) -> None:
        self._character: Optional["Character"] = None
        self._cb_after_action: Optional[callable] = None

    def on_equip(self, character, piece_count):
        if piece_count >= 2:
            character.stats.add_modifier(StatModifier(
                StatType.CRIT_RATE, StatModifierType.PERCENT, 0.08,
                source=self._SOURCE_2PC, dispellable=False,
            ))

    def on_combat_start(self, state, character):
        from core.events import EventType

        self._character = character
        self._check_condition()
        self._cb_after_action = lambda **kw: self._check_condition()
        state.event_bus.subscribe(EventType.AFTER_ACTION, self._cb_after_action)

    def _check_condition(self) -> None:
        cr = self._character.stats.get_total_stat(StatType.CRIT_RATE)
        has = any(
            m.source == self._SOURCE_ULT
            for m in self._character.stats.active_modifiers
        )
        if cr >= 0.50 and not has:
            self._character.stats.add_modifier(StatModifier(
                StatType.ULT_DMG, StatModifierType.PERCENT, 0.15,
                source=self._SOURCE_ULT, dispellable=False,
            ))
            self._character.stats.add_modifier(StatModifier(
                StatType.FUA_DMG, StatModifierType.PERCENT, 0.15,
                source=self._SOURCE_FUA, dispellable=False,
            ))
        elif cr < 0.50 and has:
            self._character.stats.purge_source(self._SOURCE_ULT)
            self._character.stats.purge_source(self._SOURCE_FUA)

    def on_unequip(self, character):
        from core.events import EventType

        character.stats.purge_source(self._SOURCE_2PC)
        character.stats.purge_source(self._SOURCE_ULT)
        character.stats.purge_source(self._SOURCE_FUA)
        if self._cb_after_action is not None and character.event_bus is not None:
            character.event_bus.unsubscribe(EventType.AFTER_ACTION, self._cb_after_action)

from __future__ import annotations

"""筑城者的贝洛伯格 — 2件套 (使装备者的防御力提高15%。当装备者的效果命中
大于等于50%时，防御力额外提高15%)。"""

from typing import Optional

from core.enums import StatType, StatModifierType
from entities.base import StatModifier
from entities.relics.base import BaseRelic, RelicSetEffect
from starrail_combat import RelicPart


class BelobogArchitectsSphere(BaseRelic):
    _default_part = RelicPart.PLANAR_SPHERE
    _default_set_id = "304"


class BelobogArchitectsRope(BaseRelic):
    _default_part = RelicPart.LINK_ROPE
    _default_set_id = "304"


class BelobogOfTheArchitects(RelicSetEffect):
    set_id = "304"
    set_type = "planar"

    _SOURCE_2PC = "RelicSet_304_2pc"
    _SOURCE_2PC_EXTRA = "RelicSet_304_2pc_extra"

    def __init__(self) -> None:
        self._character: Optional["Character"] = None
        self._cb_after_action: Optional[callable] = None

    def on_equip(self, character, piece_count):
        if piece_count >= 2:
            character.stats.add_modifier(StatModifier(
                StatType.DEF, StatModifierType.PERCENT, 0.15,
                source=self._SOURCE_2PC, dispellable=False,
            ))

    def on_combat_start(self, state, character):
        from core.events import EventType

        self._character = character
        self._check_condition()
        self._cb_after_action = lambda **kw: self._check_condition()
        state.event_bus.subscribe(EventType.ON_ABILITY_PROPERTY_CHANGE, self._cb_after_action)  # JSON: OnAbilityPropertyChange:StatusProbability

    def _check_condition(self) -> None:
        ehr = self._character.stats.get_total_stat(StatType.EFFECT_HIT_RATE)
        has_extra = any(
            m.source == self._SOURCE_2PC_EXTRA
            for m in self._character.stats.active_modifiers
        )
        if ehr >= 0.50 and not has_extra:
            self._character.stats.add_modifier(StatModifier(
                StatType.DEF, StatModifierType.PERCENT, 0.15,
                source=self._SOURCE_2PC_EXTRA, dispellable=False,
            ))
        elif ehr < 0.50 and has_extra:
            self._character.stats.purge_source(self._SOURCE_2PC_EXTRA)

    def on_unequip(self, character):
        from core.events import EventType

        character.stats.purge_source(self._SOURCE_2PC)
        character.stats.purge_source(self._SOURCE_2PC_EXTRA)
        if self._cb_after_action is not None and character.event_bus is not None:
            character.event_bus.unsubscribe(EventType.ON_ABILITY_PROPERTY_CHANGE, self._cb_after_action)  # JSON: OnAbilityPropertyChange:StatusProbability

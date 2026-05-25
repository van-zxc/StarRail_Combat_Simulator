from __future__ import annotations

"""街头出身的拳王 — 4件套装 (2件: 物理伤害+10%, 4件: 攻击/受击后攻击力+5%最多5层)。"""

from typing import Optional

from core.enums import StatType, StatModifierType
from entities.base import StatModifier
from entities.relics.base import BaseRelic, RelicSetEffect
from starrail_combat import RelicPart


class ChampionBoxingHead(BaseRelic):
    _default_part = RelicPart.HEAD
    _default_set_id = "105"
    _default_main_stat = StatModifier(StatType.HP, StatModifierType.FLAT, 705.0)
    _default_sub_stats = []


class ChampionBoxingHands(BaseRelic):
    _default_part = RelicPart.HANDS
    _default_set_id = "105"
    _default_main_stat = StatModifier(StatType.ATK, StatModifierType.FLAT, 352.0)
    _default_sub_stats = []


class ChampionBoxingBody(BaseRelic):
    _default_part = RelicPart.BODY
    _default_set_id = "105"
    _default_main_stat = None
    _default_sub_stats = []


class ChampionBoxingFeet(BaseRelic):
    _default_part = RelicPart.FEET
    _default_set_id = "105"
    _default_main_stat = None
    _default_sub_stats = []


class ChampionOfStreetwiseBoxing(RelicSetEffect):
    set_id = "105"
    set_type = "cavern"

    _SOURCE_2PC = "RelicSet_105_2pc"
    _SOURCE_4PC = "RelicSet_105_4pc"
    _STACK_VALUE = 0.05
    _MAX_TOTAL = 0.25

    def __init__(self) -> None:
        self._character: Optional["Character"] = None
        self._cb_action: Optional[callable] = None
        self._cb_hit: Optional[callable] = None

    def on_equip(self, character, piece_count):
        if piece_count >= 2:
            character.stats.add_modifier(StatModifier(
                StatType.PHYSICAL_DMG_BONUS, StatModifierType.PERCENT, 0.10,
                source=self._SOURCE_2PC, dispellable=False,
            ))

    def on_combat_start(self, state, character):
        from core.events import EventType

        self._character = character
        self._cb_action = lambda **kw: self._on_after_action(**kw)
        self._cb_hit = lambda **kw: self._on_hit(**kw)
        state.event_bus.subscribe(EventType.AFTER_ACTION, self._cb_action)
        state.event_bus.subscribe(EventType.ON_HIT, self._cb_hit)

    def _on_after_action(self, **kwargs):
        if kwargs.get("unit") is not self._character:
            return
        self._try_stack()

    def _on_hit(self, **kwargs):
        if kwargs.get("target") is not self._character:
            return
        self._try_stack()

    def _try_stack(self):
        total = sum(
            m.value for m in self._character.stats.active_modifiers
            if m.source == self._SOURCE_4PC and m.stat_type == StatType.ATK
        )
        if total >= self._MAX_TOTAL:
            return
        to_add = min(self._STACK_VALUE, self._MAX_TOTAL - total)
        mod = StatModifier(
            StatType.ATK, StatModifierType.PERCENT, to_add,
            source=self._SOURCE_4PC, dispellable=False,
        )
        self._character.stats.add_modifier(mod)

    def on_unequip(self, character):
        from core.events import EventType

        character.stats.purge_source(self._SOURCE_2PC)
        character.stats.purge_source(self._SOURCE_4PC)
        if self._cb_action is not None and character.event_bus is not None:
            character.event_bus.unsubscribe(EventType.AFTER_ACTION, self._cb_action)
        if self._cb_hit is not None and character.event_bus is not None:
            character.event_bus.unsubscribe(EventType.ON_HIT, self._cb_hit)

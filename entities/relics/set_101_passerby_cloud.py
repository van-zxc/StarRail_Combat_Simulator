from __future__ import annotations

"""云无留迹的过客 — 4件套装 (2件: 治疗量+10%, 4件: 战斗开始时恢复1个战技点)。"""

from typing import Optional

from core.enums import StatType, StatModifierType
from entities.base import StatModifier
from entities.relics.base import BaseRelic, RelicSetEffect
from starrail_combat import RelicPart


class PasserbyHead(BaseRelic):
    _default_part = RelicPart.HEAD
    _default_set_id = "101"
    _default_main_stat = StatModifier(StatType.HP, StatModifierType.FLAT, 705.0)
    _default_sub_stats = []


class PasserbyHands(BaseRelic):
    _default_part = RelicPart.HANDS
    _default_set_id = "101"
    _default_main_stat = StatModifier(StatType.ATK, StatModifierType.FLAT, 352.0)
    _default_sub_stats = []


class PasserbyBody(BaseRelic):
    _default_part = RelicPart.BODY
    _default_set_id = "101"
    _default_main_stat = None
    _default_sub_stats = []


class PasserbyFeet(BaseRelic):
    _default_part = RelicPart.FEET
    _default_set_id = "101"
    _default_main_stat = None
    _default_sub_stats = []


class PasserbyOfWanderingCloud(RelicSetEffect):
    set_id = "101"
    set_type = "cavern"

    _SOURCE_2PC = "RelicSet_101_2pc"

    def __init__(self) -> None:
        self._character: Optional["Character"] = None
        self._piece_count: int = 0
        self._cb_battle: Optional[callable] = None

    def on_equip(self, character, piece_count):
        self._piece_count = piece_count
        if piece_count >= 2:
            character.stats.add_modifier(StatModifier(
                StatType.OUTGOING_HEALING_BOOST, StatModifierType.PERCENT, 0.10,
                source=self._SOURCE_2PC, dispellable=False,
            ))

    def on_combat_start(self, state, character):
        from core.events import EventType

        self._character = character
        if self._piece_count >= 4:
            self._cb_battle = lambda **kw: self._on_battle_start(**kw)
            state.event_bus.subscribe(EventType.BATTLE_START, self._cb_battle)

    def _on_battle_start(self, **kwargs):
        engine = kwargs.get("engine")
        if engine is not None:
            engine.state.generate_sp()

    def on_unequip(self, character):
        from core.events import EventType

        character.stats.purge_source(self._SOURCE_2PC)
        if self._cb_battle is not None and character.event_bus is not None:
            character.event_bus.unsubscribe(EventType.BATTLE_START, self._cb_battle)

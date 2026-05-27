from __future__ import annotations

"""生命的翁瓦克 — 2件套 (使装备者的能量恢复效率提高5%。当装备者的速度
大于等于120时，进入战斗时立刻使行动提前40%)。

注意: 拉条仅 BATTLE_START 触发一次。用 _fired flag 防多波次重复触发。
"""

from typing import Optional

from core.enums import StatType, StatModifierType
from entities.base import StatModifier
from entities.relics.base import BaseRelic, RelicSetEffect
from starrail_combat import RelicPart


class SprightlyVonwacqSphere(BaseRelic):
    _default_part = RelicPart.PLANAR_SPHERE
    _default_set_id = "308"


class SprightlyVonwacqRope(BaseRelic):
    _default_part = RelicPart.LINK_ROPE
    _default_set_id = "308"


class SprightlyVonwacq(RelicSetEffect):
    set_id = "308"
    set_type = "planar"

    _SOURCE_2PC = "RelicSet_308_2pc"

    def __init__(self) -> None:
        self._character: Optional["Character"] = None
        self._cb_battle: Optional[callable] = None
        self._fired: bool = False

    def on_equip(self, character, piece_count):
        if piece_count >= 2:
            character.stats.add_modifier(StatModifier(
                StatType.ERR, StatModifierType.PERCENT, 0.05,
                source=self._SOURCE_2PC, dispellable=False,
            ))

    def on_combat_start(self, state, character):
        from core.events import EventType

        self._character = character
        self._cb_battle = lambda **kw: self._on_battle_start(**kw)
        state.event_bus.subscribe(EventType.BATTLE_START, self._cb_battle)

    def _on_battle_start(self, **kwargs):
        if self._fired:
            return
        self._fired = True
        if self._character.speed >= 120.0:
            self._character.advance_action(0.40)

    def on_unequip(self, character):
        from core.events import EventType

        character.stats.purge_source(self._SOURCE_2PC)
        if self._cb_battle is not None and character.event_bus is not None:
            character.event_bus.unsubscribe(EventType.BATTLE_START, self._cb_battle)

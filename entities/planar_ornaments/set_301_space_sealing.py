from __future__ import annotations

"""太空封印站 — 2件套 (使装备者的攻击力提高12%。当装备者的速度大于等于120时，攻击力额外提高12%)。

注意: 条件判定基于实时 speed (AFTER_ACTION 动态刷新), buff 施加/失效后立即响应。
由于 TURN_START emit 在 _decrement_modifiers 之前 (combat_engine.py:114-115),
不使用 TURN_START 以避免读到 modifier 过期前的旧值。
"""

from typing import Optional

from core.enums import StatType, StatModifierType
from entities.base import StatModifier
from entities.relics.base import BaseRelic, RelicSetEffect
from starrail_combat import RelicPart


class SpaceSealingSphere(BaseRelic):
    _default_part = RelicPart.PLANAR_SPHERE
    _default_set_id = "301"


class SpaceSealingRope(BaseRelic):
    _default_part = RelicPart.LINK_ROPE
    _default_set_id = "301"


class SpaceSealingStation(RelicSetEffect):
    set_id = "301"
    set_type = "planar"

    _SOURCE_2PC = "RelicSet_301_2pc"
    _SOURCE_2PC_EXTRA = "RelicSet_301_2pc_extra"

    def __init__(self) -> None:
        self._character: Optional["Character"] = None
        self._cb_after_action: Optional[callable] = None

    def on_equip(self, character, piece_count):
        if piece_count >= 2:
            character.stats.add_modifier(StatModifier(
                StatType.ATK, StatModifierType.PERCENT, 0.12,
                source=self._SOURCE_2PC, dispellable=False,
            ))

    def on_combat_start(self, state, character):
        from core.events import EventType

        self._character = character
        self._check_condition()
        self._cb_after_action = lambda **kw: self._check_condition()
        state.event_bus.subscribe(EventType.AFTER_ACTION, self._cb_after_action)

    def _check_condition(self) -> None:
        """检查 SPD 阈值 → 动态 add/remove 条件 ATK%。"""
        spd = self._character.speed
        has_extra = any(
            m.source == self._SOURCE_2PC_EXTRA
            for m in self._character.stats.active_modifiers
        )
        if spd >= 120.0 and not has_extra:
            self._character.stats.add_modifier(StatModifier(
                StatType.ATK, StatModifierType.PERCENT, 0.12,
                source=self._SOURCE_2PC_EXTRA, dispellable=False,
            ))
        elif spd < 120.0 and has_extra:
            self._character.stats.purge_source(self._SOURCE_2PC_EXTRA)

    def on_unequip(self, character):
        from core.events import EventType

        character.stats.purge_source(self._SOURCE_2PC)
        character.stats.purge_source(self._SOURCE_2PC_EXTRA)
        if self._cb_after_action is not None and character.event_bus is not None:
            character.event_bus.unsubscribe(EventType.AFTER_ACTION, self._cb_after_action)

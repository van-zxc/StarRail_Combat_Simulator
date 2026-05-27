from __future__ import annotations

"""星体差分机 — 2件套 (使装备者的暴击伤害提高16%。当装备者的暴击伤害
大于等于120%时，进入战斗后装备者的暴击率提高60%，持续到施放首次攻击后结束)。

注意: BATTLE_START 一次性判定，暴伤不达标则永不触发。
死亡清除该 buff (UNIT_DOWNED 监听)。首次攻击后通过 AFTER_ACTION 移除，
仅限攻击类动作 (BASIC_ATTACK / SKILL / ULTIMATE / FOLLOW_UP / COUNTER)。
"""

from typing import Optional

from core.enums import ActionType, StatType, StatModifierType
from entities.base import StatModifier
from entities.relics.base import BaseRelic, RelicSetEffect
from starrail_combat import RelicPart


_ATTACK_TYPES = {
    ActionType.BASIC_ATTACK,
    ActionType.ENHANCED_BASIC,
    ActionType.SKILL,
    ActionType.ULTIMATE,
    ActionType.FOLLOW_UP,
    ActionType.COUNTER,
}


class CelestialDiffSphere(BaseRelic):
    _default_part = RelicPart.PLANAR_SPHERE
    _default_set_id = "305"


class CelestialDiffRope(BaseRelic):
    _default_part = RelicPart.LINK_ROPE
    _default_set_id = "305"


class CelestialDifferentiator(RelicSetEffect):
    set_id = "305"
    set_type = "planar"

    _SOURCE_2PC = "RelicSet_305_2pc"
    _SOURCE_BATTLE = "RelicSet_305_2pc_battle"

    def __init__(self) -> None:
        self._character: Optional["Character"] = None
        self._cb_battle: Optional[callable] = None
        self._cb_after: Optional[callable] = None
        self._cb_death: Optional[callable] = None

    def on_equip(self, character, piece_count):
        if piece_count >= 2:
            character.stats.add_modifier(StatModifier(
                StatType.CRIT_DMG, StatModifierType.PERCENT, 0.16,
                source=self._SOURCE_2PC, dispellable=False,
            ))

    def on_combat_start(self, state, character):
        from core.events import EventType

        self._character = character
        self._cb_battle = lambda **kw: self._on_battle_start(**kw)
        state.event_bus.subscribe(EventType.BATTLE_START, self._cb_battle)

    def _on_battle_start(self, **kwargs):
        from core.events import EventType

        crit_dmg = self._character.stats.get_total_stat(StatType.CRIT_DMG)
        if crit_dmg < 1.20:
            return
        self._character.stats.add_modifier(StatModifier(
            StatType.CRIT_RATE, StatModifierType.PERCENT, 0.60,
            source=self._SOURCE_BATTLE, dispellable=False,
        ))
        self._cb_after = lambda **kw: self._on_after_action(**kw)
        self._cb_death = lambda **kw: self._on_unit_downed(**kw)
        bus = self._character.event_bus
        if bus is not None:
            bus.subscribe(EventType.AFTER_ACTION, self._cb_after)
            bus.subscribe(EventType.UNIT_DOWNED, self._cb_death)

    def _on_after_action(self, **kwargs):
        if kwargs.get("unit") is not self._character:
            return
        if kwargs.get("action_type") not in _ATTACK_TYPES:
            return
        self._cleanup_battle_buff()

    def _on_unit_downed(self, **kwargs):
        if kwargs.get("target") is not self._character:
            return
        self._cleanup_battle_buff()

    def _cleanup_battle_buff(self):
        from core.events import EventType

        self._character.stats.purge_source(self._SOURCE_BATTLE)
        bus = self._character.event_bus
        if bus is not None:
            if self._cb_after is not None:
                bus.unsubscribe(EventType.AFTER_ACTION, self._cb_after)
                self._cb_after = None
            if self._cb_death is not None:
                bus.unsubscribe(EventType.UNIT_DOWNED, self._cb_death)
                self._cb_death = None

    def on_unequip(self, character):
        from core.events import EventType

        character.stats.purge_source(self._SOURCE_2PC)
        character.stats.purge_source(self._SOURCE_BATTLE)
        bus = character.event_bus
        if bus is not None:
            if self._cb_battle is not None:
                bus.unsubscribe(EventType.BATTLE_START, self._cb_battle)
            if self._cb_after is not None:
                bus.unsubscribe(EventType.AFTER_ACTION, self._cb_after)
            if self._cb_death is not None:
                bus.unsubscribe(EventType.UNIT_DOWNED, self._cb_death)

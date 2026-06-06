from __future__ import annotations

"""繁星璀璨的天才 — 4件套装 (2件: 量子伤+10%, 4件: 造成伤害时无视10%防御, 量子弱点额外10%)。

JSON: OnBeforeHitAll → ModifyDamageData.Defender_DefenceAddedRatio + ByHasStanceWeak(Quantum) → extra.
Python: 永久 DEF_IGNORE +10%; ON_BEFORE_DAMAGE_CALC per-hit 检查 target 量子弱点 → toggle extra +10%.
"""

from typing import Optional

from core.enums import StatType, StatModifierType, ElementType
from entities.base import StatModifier
from entities.relics.base import BaseRelic, RelicSetEffect
from starrail_combat import RelicPart


class GeniusBrilliantHead(BaseRelic):
    _default_part = RelicPart.HEAD
    _default_set_id = "108"
    _default_main_stat = StatModifier(StatType.HP, StatModifierType.FLAT, 705.0)
    _default_sub_stats = []


class GeniusBrilliantHands(BaseRelic):
    _default_part = RelicPart.HANDS
    _default_set_id = "108"
    _default_main_stat = StatModifier(StatType.ATK, StatModifierType.FLAT, 352.0)
    _default_sub_stats = []


class GeniusBrilliantBody(BaseRelic):
    _default_part = RelicPart.BODY
    _default_set_id = "108"
    _default_main_stat = None
    _default_sub_stats = []


class GeniusBrilliantFeet(BaseRelic):
    _default_part = RelicPart.FEET
    _default_set_id = "108"
    _default_main_stat = None
    _default_sub_stats = []


class GeniusOfBrilliantStars(RelicSetEffect):
    set_id = "108"
    set_type = "cavern"

    _SOURCE_2PC = "RelicSet_108_2pc"
    _SOURCE_4PC_BASE = "RelicSet_108_4pc_base"
    _SOURCE_4PC_EXTRA = "RelicSet_108_4pc_extra"

    def __init__(self) -> None:
        self._character: Optional["Character"] = None
        self._cb_precalc: Optional[callable] = None
        self._cb_after: Optional[callable] = None

    def on_equip(self, character, piece_count):
        if piece_count >= 2:
            character.stats.add_modifier(StatModifier(
                StatType.QUANTUM_DMG_BONUS, StatModifierType.PERCENT, 0.10,
                source=self._SOURCE_2PC, dispellable=False,
            ))
        if piece_count >= 4:
            character.stats.add_modifier(StatModifier(
                StatType.DEF_IGNORE, StatModifierType.PERCENT, 0.10,
                source=self._SOURCE_4PC_BASE, dispellable=False,
            ))

    def on_combat_start(self, state, character):
        from core.events import EventType

        self._character = character
        self._cb_precalc = lambda **kw: self._on_before_damage_calc(**kw)
        self._cb_after = lambda **kw: self._on_after_action(**kw)
        state.event_bus.subscribe(EventType.ON_BEFORE_DAMAGE_CALC, self._cb_precalc)
        state.event_bus.subscribe(EventType.AFTER_ACTION, self._cb_after)

    def _on_before_damage_calc(self, **kwargs):
        """JSON ByHasStanceWeak(Quantum): 每段伤害计算前检查当前受击目标的量子弱点。"""
        source = kwargs.get("source")
        if source is not self._character:
            return
        target = kwargs.get("target")
        if target is None:
            return
        extra = ElementType.QUANTUM in getattr(target, "weaknesses", [])
        self._ensure_extra(extra)

    def _on_after_action(self, **kwargs):
        """清除 per-hit 临时贴的 quantum extra, 避免跨 action 残留。"""
        if kwargs.get("unit") is not self._character:
            return
        self._character.stats.purge_source(self._SOURCE_4PC_EXTRA)

    def _ensure_extra(self, active):
        has = any(m.source == self._SOURCE_4PC_EXTRA for m in self._character.stats.active_modifiers)
        if active and not has:
            self._character.stats.add_modifier(StatModifier(
                StatType.DEF_IGNORE, StatModifierType.PERCENT, 0.10,
                source=self._SOURCE_4PC_EXTRA, dispellable=False,
            ))
        elif not active and has:
            self._character.stats.purge_source(self._SOURCE_4PC_EXTRA)

    def on_unequip(self, character):
        from core.events import EventType

        character.stats.purge_source(self._SOURCE_2PC)
        character.stats.purge_source(self._SOURCE_4PC_BASE)
        character.stats.purge_source(self._SOURCE_4PC_EXTRA)
        if self._cb_precalc is not None and character.event_bus is not None:
            character.event_bus.unsubscribe(EventType.ON_BEFORE_DAMAGE_CALC, self._cb_precalc)
        if self._cb_after is not None and character.event_bus is not None:
            character.event_bus.unsubscribe(EventType.AFTER_ACTION, self._cb_after)

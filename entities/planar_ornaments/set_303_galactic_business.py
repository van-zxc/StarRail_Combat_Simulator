from __future__ import annotations

"""泛银河商业公司 — 2件套 (使装备者的效果命中提高10%。同时提高装备者
等同于当前效果命中25%的攻击力，最多提高25%)。

注意: ATK% = min(EHR_total × 0.25, 0.25)，EHR 含套装自身的 +10%。
使用 refresh 策略动态更新 ATK% 修饰器值。
"""

from typing import Optional

from core.enums import StatType, StatModifierType
from entities.base import StatModifier
from entities.relics.base import BaseRelic, RelicSetEffect
from starrail_combat import RelicPart


class GalacticBusinessSphere(BaseRelic):
    _default_part = RelicPart.PLANAR_SPHERE
    _default_set_id = "303"


class GalacticBusinessRope(BaseRelic):
    _default_part = RelicPart.LINK_ROPE
    _default_set_id = "303"


class PanCosmicCommercialEnterprise(RelicSetEffect):
    set_id = "303"
    set_type = "planar"

    _SOURCE_2PC = "RelicSet_303_2pc"
    _SOURCE_CONV = "RelicSet_303_2pc_conversion"

    def __init__(self) -> None:
        self._character: Optional["Character"] = None
        self._cb_after_action: Optional[callable] = None

    def on_equip(self, character, piece_count):
        if piece_count >= 2:
            character.stats.add_modifier(StatModifier(
                StatType.EFFECT_HIT_RATE, StatModifierType.PERCENT, 0.10,
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
        atk_pct = min(ehr * 0.25, 0.25)
        mod = StatModifier(
            StatType.ATK, StatModifierType.PERCENT, atk_pct,
            source=self._SOURCE_CONV, dispellable=False,
        )
        self._character.stats.apply_modifier(mod, "refresh")

    def on_unequip(self, character):
        from core.events import EventType

        character.stats.purge_source(self._SOURCE_2PC)
        character.stats.purge_source(self._SOURCE_CONV)
        if self._cb_after_action is not None and character.event_bus is not None:
            character.event_bus.unsubscribe(EventType.ON_ABILITY_PROPERTY_CHANGE, self._cb_after_action)  # JSON: OnAbilityPropertyChange:StatusProbability

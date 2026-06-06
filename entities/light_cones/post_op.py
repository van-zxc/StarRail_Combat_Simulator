from __future__ import annotations
"""Post-Op Conversation (一场术后对话) — 4★ 丰饶光锥。

特效:
  #1: 能量恢复效率提高#1[i]% (永久面板, 来自 properties/SPRatioBase)
  #2: 施放终结技时治疗量提高#2[i]% (ACTION_START→AFTER_ACTION 即时移除, 对齐 JSON OnBeforeDealHeal:Ultra)
"""

from typing import Optional

from entities.light_cones.base import BaseLightCone
from entities.base import EquipmentEffect, StatModifier


class PostOpConversation(BaseLightCone):
    _default_id = "21000"
    _default_name = "一场术后对话"
    _default_path_key = "Priest"

    _PROMOTIONS = [
        {"hp_base": 48, "hp_step": 7.2, "atk_base": 19.2, "atk_step": 2.88, "def_base": 15, "def_step": 2.25},
        {"hp_base": 105.6, "hp_step": 7.2, "atk_base": 42.24, "atk_step": 2.88, "def_base": 33, "def_step": 2.25},
        {"hp_base": 182.4, "hp_step": 7.2, "atk_base": 72.96, "atk_step": 2.88, "def_base": 57, "def_step": 2.25},
        {"hp_base": 259.2, "hp_step": 7.2, "atk_base": 103.68, "atk_step": 2.88, "def_base": 81, "def_step": 2.25},
        {"hp_base": 336, "hp_step": 7.2, "atk_base": 134.4, "atk_step": 2.88, "def_base": 105, "def_step": 2.25},
        {"hp_base": 412.8, "hp_step": 7.2, "atk_base": 165.12, "atk_step": 2.88, "def_base": 129, "def_step": 2.25},
        {"hp_base": 489.6, "hp_step": 7.2, "atk_base": 195.84, "atk_step": 2.88, "def_base": 153, "def_step": 2.25},
    ]

    def __init__(self, id: str = "", **kwargs):
        super().__init__(id=id, **kwargs)
        if self.effect is None:
            self.effect = PostOpEffect(self.superimpose)


class PostOpEffect(EquipmentEffect):
    _PARAMS = [
        [0.08, 0.12],
        [0.10, 0.15],
        [0.12, 0.18],
        [0.14, 0.21],
        [0.16, 0.24],
    ]
    _PERM_ERR = [0.08, 0.10, 0.12, 0.14, 0.16]
    _SOURCE_ERR = "LightCone_21000_ERR"
    _SOURCE_HEAL = "LightCone_21000_HEAL"

    def __init__(self, superimpose: int = 1) -> None:
        self.superimpose = max(1, min(superimpose, 5))
        self._character: Optional["Character"] = None
        self._cb_ult: Optional[callable] = None
        self._cb_after: Optional[callable] = None

    def on_equip(self, character: "Character") -> None:
        from core.enums import StatType, StatModifierType

        err_val = self._PERM_ERR[self.superimpose - 1]
        mod = StatModifier(
            stat_type=StatType.ERR,
            modifier_type=StatModifierType.PERCENT,
            value=err_val,
            source=self._SOURCE_ERR,
            dispellable=False,
        )
        character.stats.apply_modifier(mod, "refresh")

    def on_combat_start(self, state: "GameState", character: "Character") -> None:
        from core.events import EventType

        self._character = character
        self._cb_ult = lambda **kw: self._on_ult(kw.get("character"))
        self._cb_after = lambda **kw: self._on_after(kw.get("unit"), kw.get("action_type"))
        state.event_bus.subscribe(EventType.ON_ULTIMATE_INSERTED, self._cb_ult)
        state.event_bus.subscribe(EventType.AFTER_ACTION, self._cb_after)

    def _on_ult(self, caster: "Character") -> None:
        if caster is not self._character:
            return
        from core.enums import StatType, StatModifierType

        heal_pct = self._PARAMS[self.superimpose - 1][1]
        mod = StatModifier(
            stat_type=StatType.OUTGOING_HEALING_BOOST,
            modifier_type=StatModifierType.PERCENT,
            value=heal_pct,
            source=self._SOURCE_HEAL,
            dispellable=False,
        )  # JSON: OnBeforeDealHeal:Ultra 仅在终结技内生效, 无 duration
        self._character.stats.apply_modifier(mod, "refresh")

    def _on_after(self, unit: "Character", action_type: object) -> None:
        """JSON OnBeforeDealHeal 限定: 终结技结束后立即移除治疗加成。"""
        from core.enums import ActionType

        if unit is not self._character:
            return
        if action_type == ActionType.ULTIMATE:
            self._character.stats.purge_source(self._SOURCE_HEAL)

    def on_unequip(self, character: "Character") -> None:
        from core.events import EventType

        character.stats.purge_source(self._SOURCE_ERR)
        character.stats.purge_source(self._SOURCE_HEAL)
        if character.event_bus is not None:
            bus = character.event_bus
            if self._cb_ult is not None:
                bus.unsubscribe(EventType.ON_ULTIMATE_INSERTED, self._cb_ult)
            if self._cb_after is not None:
                bus.unsubscribe(EventType.AFTER_ACTION, self._cb_after)

from __future__ import annotations
"""鼹鼠党欢迎你 (The Moles Welcome You) — 4★ 毁灭光锥。

特效: 普攻/战技/终结技分别获取1层【淘气值】，每层攻击力提高#1[i]%（max 3）。
"""

from typing import Optional

from entities.light_cones.base import BaseLightCone
from entities.base import EquipmentEffect, StatModifier


class MolesWelcomeYou(BaseLightCone):
    _default_id = "21005"
    _default_name = "鼹鼠党欢迎你"
    _default_path_key = "Warrior"

    _PROMOTIONS = [
        {"hp_base": 48, "hp_step": 7.2, "atk_base": 21.6, "atk_step": 3.24, "def_base": 12, "def_step": 1.8},
        {"hp_base": 105.6, "hp_step": 7.2, "atk_base": 47.52, "atk_step": 3.24, "def_base": 26.4, "def_step": 1.8},
        {"hp_base": 182.4, "hp_step": 7.2, "atk_base": 82.08, "atk_step": 3.24, "def_base": 45.6, "def_step": 1.8},
        {"hp_base": 259.2, "hp_step": 7.2, "atk_base": 116.64, "atk_step": 3.24, "def_base": 64.8, "def_step": 1.8},
        {"hp_base": 336, "hp_step": 7.2, "atk_base": 151.2, "atk_step": 3.24, "def_base": 84, "def_step": 1.8},
        {"hp_base": 412.8, "hp_step": 7.2, "atk_base": 185.76, "atk_step": 3.24, "def_base": 103.2, "def_step": 1.8},
        {"hp_base": 489.6, "hp_step": 7.2, "atk_base": 220.32, "atk_step": 3.24, "def_base": 122.4, "def_step": 1.8},
    ]

    def __init__(self, id: str = "", **kwargs):
        super().__init__(id=id, **kwargs)
        if self.effect is None:
            self.effect = MolesWelcomeYouEffect(self.superimpose)


class MolesWelcomeYouEffect(EquipmentEffect):
    _PARAMS = [0.12, 0.15, 0.18, 0.21, 0.24]
    _SOURCE = "LightCone_21005"

    def __init__(self, superimpose: int = 1) -> None:
        self.superimpose = max(1, min(superimpose, 5))
        self._character: Optional["Character"] = None
        self._has_ba: bool = False
        self._has_skill: bool = False
        self._has_ult: bool = False
        self._cb_after: Optional[callable] = None

    def on_equip(self, character: "Character") -> None:
        pass

    def on_combat_start(self, state: "GameState", character: "Character") -> None:
        from core.events import EventType

        self._character = character
        self._cb_after = lambda **kw: self._on_after(kw.get("unit"), kw.get("action_type"))
        state.event_bus.subscribe(EventType.AFTER_ACTION, self._cb_after)

    def _on_after(self, unit: "Character", action_type: object) -> None:
        from core.enums import ActionType, StatType, StatModifierType

        if unit is not self._character:
            return
        if action_type == ActionType.BASIC_ATTACK:
            self._has_ba = True
        elif action_type == ActionType.SKILL:
            self._has_skill = True
        elif action_type == ActionType.ULTIMATE:
            self._has_ult = True
        else:
            return
        stacks = sum([self._has_ba, self._has_skill, self._has_ult])
        atk_val = stacks * self._PARAMS[self.superimpose - 1]
        mod = StatModifier(
            stat_type=StatType.ATK,
            modifier_type=StatModifierType.PERCENT,
            value=atk_val,
            source=self._SOURCE,
            dispellable=False,
        )
        self._character.stats.apply_modifier(mod, "refresh")

    def on_unequip(self, character: "Character") -> None:
        from core.events import EventType

        character.stats.purge_source(self._SOURCE)
        if self._cb_after is not None and character.event_bus is not None:
            character.event_bus.unsubscribe(EventType.AFTER_ACTION, self._cb_after)

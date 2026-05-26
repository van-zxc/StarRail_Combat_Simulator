from __future__ import annotations
"""匿影 (Hidden Shadow) — 3★ 虚无光锥。

特效: 施放战技后，使装备者的下一次普攻对敌方目标造成等同于自身#1[i]%攻击力的附加伤害。
"""

from typing import Optional

from entities.light_cones.base import BaseLightCone
from entities.base import EquipmentEffect


class HiddenShadow(BaseLightCone):
    _default_id = "20018"
    _default_name = "匿影"
    _default_path_key = "Warlock"

    _PROMOTIONS = [
        {"hp_base": 38.4, "hp_step": 5.76, "atk_base": 14.4, "atk_step": 2.16, "def_base": 12, "def_step": 1.8},
        {"hp_base": 84.48, "hp_step": 5.76, "atk_base": 31.68, "atk_step": 2.16, "def_base": 26.4, "def_step": 1.8},
        {"hp_base": 145.92, "hp_step": 5.76, "atk_base": 54.72, "atk_step": 2.16, "def_base": 45.6, "def_step": 1.8},
        {"hp_base": 207.36, "hp_step": 5.76, "atk_base": 77.76, "atk_step": 2.16, "def_base": 64.8, "def_step": 1.8},
        {"hp_base": 268.8, "hp_step": 5.76, "atk_base": 100.8, "atk_step": 2.16, "def_base": 84, "def_step": 1.8},
        {"hp_base": 330.24, "hp_step": 5.76, "atk_base": 123.84, "atk_step": 2.16, "def_base": 103.2, "def_step": 1.8},
        {"hp_base": 391.68, "hp_step": 5.76, "atk_base": 146.88, "atk_step": 2.16, "def_base": 122.4, "def_step": 1.8},
    ]

    def __init__(self, id: str = "", **kwargs):
        super().__init__(id=id, **kwargs)
        if self.effect is None:
            self.effect = HiddenShadowEffect(self.superimpose)


class HiddenShadowEffect(EquipmentEffect):
    _PARAMS = [0.60, 0.75, 0.90, 1.05, 1.20]
    _SOURCE = "LightCone_20018"

    def __init__(self, superimpose: int = 1) -> None:
        self.superimpose = max(1, min(superimpose, 5))
        self._character: Optional["Character"] = None
        self._state: Optional["GameState"] = None
        self._next_ba_buffed: bool = False
        self._cb_after: Optional[callable] = None

    def on_equip(self, character: "Character") -> None:
        pass

    def on_combat_start(self, state: "GameState", character: "Character") -> None:
        from core.events import EventType

        self._character = character
        self._state = state
        self._cb_after = lambda **kw: self._on_after(kw.get("unit"), kw.get("target"), kw.get("action_type"))
        state.event_bus.subscribe(EventType.AFTER_ACTION, self._cb_after)

    def _on_after(self, unit: "Character", target: "Fighter", action_type: object) -> None:
        from core.enums import ActionType, DamageType

        if unit is not self._character:
            return

        if action_type == ActionType.SKILL:
            self._next_ba_buffed = True
            return

        if action_type == ActionType.BASIC_ATTACK and self._next_ba_buffed:
            self._next_ba_buffed = False
            if target is None or not target.is_alive:
                return
            bonus_pct = self._PARAMS[self.superimpose - 1]
            self._state.execute_action(
                character=self._character,
                action_type=ActionType.BASIC_ATTACK,
                target=target,
                skill_multiplier=bonus_pct,
                damage_type=DamageType.ADDITIONAL_DMG,
            )

    def on_unequip(self, character: "Character") -> None:
        from core.events import EventType

        if self._cb_after is not None and character.event_bus is not None:
            character.event_bus.unsubscribe(EventType.AFTER_ACTION, self._cb_after)

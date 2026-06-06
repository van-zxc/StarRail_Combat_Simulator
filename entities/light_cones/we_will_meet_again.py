from __future__ import annotations
"""后会有期 (We Will Meet Again) — 4★ 虚无光锥。

特效: 普攻或战技后，对随机1个受攻击敌人生成ATK×#1[i]%附加伤害。

JSON对齐: OnBeforeSkillUse→flag + OnAfterAttack:Flag→Retarget(AttackTargetList) (引擎级 Retarget).
Python: AFTER_ACTION:BA|Skill→random.choice(alive)→execute_action (手动随机)."""

import random
from typing import Optional

from entities.light_cones.base import BaseLightCone
from entities.base import EquipmentEffect


class WeWillMeetAgain(BaseLightCone):
    _default_id = "21029"
    _default_name = "后会有期"
    _default_path_key = "Warlock"

    _PROMOTIONS = [
        {"hp_base": 38.4, "hp_step": 5.76, "atk_base": 24, "atk_step": 3.6, "def_base": 15, "def_step": 2.25},
        {"hp_base": 84.48, "hp_step": 5.76, "atk_base": 52.8, "atk_step": 3.6, "def_base": 33, "def_step": 2.25},
        {"hp_base": 145.92, "hp_step": 5.76, "atk_base": 91.2, "atk_step": 3.6, "def_base": 57, "def_step": 2.25},
        {"hp_base": 207.36, "hp_step": 5.76, "atk_base": 129.6, "atk_step": 3.6, "def_base": 81, "def_step": 2.25},
        {"hp_base": 268.8, "hp_step": 5.76, "atk_base": 168, "atk_step": 3.6, "def_base": 105, "def_step": 2.25},
        {"hp_base": 330.24, "hp_step": 5.76, "atk_base": 206.4, "atk_step": 3.6, "def_base": 129, "def_step": 2.25},
        {"hp_base": 391.68, "hp_step": 5.76, "atk_base": 244.8, "atk_step": 3.6, "def_base": 153, "def_step": 2.25},
    ]

    def __init__(self, id: str = "", **kwargs):
        super().__init__(id=id, **kwargs)
        if self.effect is None:
            self.effect = WeWillMeetAgainEffect(self.superimpose)


class WeWillMeetAgainEffect(EquipmentEffect):
    _PARAMS = [0.48, 0.60, 0.72, 0.84, 0.96]
    _SOURCE = "LightCone_21029"

    def __init__(self, superimpose: int = 1) -> None:
        self.superimpose = max(1, min(superimpose, 5))
        self._character: Optional["Character"] = None
        self._state: Optional["GameState"] = None
        self._cb_after: Optional[callable] = None

    def on_equip(self, character: "Character") -> None:
        pass

    def on_combat_start(self, state: "GameState", character: "Character") -> None:
        from core.events import EventType

        self._character = character
        self._state = state
        self._cb_after = lambda **kw: self._on_after(kw.get("unit"), kw.get("action_type"))
        state.event_bus.subscribe(EventType.AFTER_ACTION, self._cb_after)

    def _on_after(self, unit: "Character", action_type: object) -> None:
        from core.enums import ActionType, DamageType

        if unit is not self._character:
            return
        if action_type not in (ActionType.BASIC_ATTACK, ActionType.SKILL):
            return
        # Collect alive enemies
        alive = [e for e in self._state.alive_enemies if e.is_alive]
        if not alive:
            return
        chosen = random.choice(alive)
        bonus = self._PARAMS[self.superimpose - 1]
        self._state.execute_action(
            character=self._character,
            action_type=ActionType.BASIC_ATTACK,
            target=chosen,
            skill_multiplier=bonus,
            damage_type=DamageType.ADDITIONAL_DMG,
        )

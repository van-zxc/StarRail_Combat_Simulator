from __future__ import annotations
"""暖夜不会漫长 (Warmth Shortens Cold Nights) — 4★ 丰饶光锥。

特效: 生命上限提高#1[i]%，普攻或战技后全体回复各自生命上限#2[f1]%生命值。
"""

from typing import Optional

from entities.light_cones.base import BaseLightCone
from entities.base import EquipmentEffect, StatModifier


class WarmthShortensColdNights(BaseLightCone):
    _default_id = "21028"
    _default_name = "暖夜不会漫长"
    _default_path_key = "Priest"

    _PROMOTIONS = [
        {"hp_base": 48, "hp_step": 7.2, "atk_base": 16.8, "atk_step": 2.52, "def_base": 18, "def_step": 2.7},
        {"hp_base": 105.6, "hp_step": 7.2, "atk_base": 36.96, "atk_step": 2.52, "def_base": 39.6, "def_step": 2.7},
        {"hp_base": 182.4, "hp_step": 7.2, "atk_base": 63.84, "atk_step": 2.52, "def_base": 68.4, "def_step": 2.7},
        {"hp_base": 259.2, "hp_step": 7.2, "atk_base": 90.72, "atk_step": 2.52, "def_base": 97.2, "def_step": 2.7},
        {"hp_base": 336, "hp_step": 7.2, "atk_base": 117.6, "atk_step": 2.52, "def_base": 126, "def_step": 2.7},
        {"hp_base": 412.8, "hp_step": 7.2, "atk_base": 144.48, "atk_step": 2.52, "def_base": 154.8, "def_step": 2.7},
        {"hp_base": 489.6, "hp_step": 7.2, "atk_base": 171.36, "atk_step": 2.52, "def_base": 183.6, "def_step": 2.7},
    ]

    def __init__(self, id: str = "", **kwargs):
        super().__init__(id=id, **kwargs)
        if self.effect is None:
            self.effect = WarmthShortensColdNightsEffect(self.superimpose)


class WarmthShortensColdNightsEffect(EquipmentEffect):
    _PARAMS = [[0.16, 0.02], [0.20, 0.025], [0.24, 0.03], [0.28, 0.035], [0.32, 0.04]]
    _SOURCE = "LightCone_21028"

    def __init__(self, superimpose: int = 1) -> None:
        self.superimpose = max(1, min(superimpose, 5))
        self._character: Optional["Character"] = None
        self._state: Optional["GameState"] = None
        self._cb_after: Optional[callable] = None

    def on_equip(self, character: "Character") -> None:
        from core.enums import StatType, StatModifierType

        hp_pct = self._PARAMS[self.superimpose - 1][0]
        mod = StatModifier(
            stat_type=StatType.HP,
            modifier_type=StatModifierType.PERCENT,
            value=hp_pct,
            source=self._SOURCE,
            dispellable=False,
        )
        character.stats.apply_modifier(mod, "refresh")

    def on_combat_start(self, state: "GameState", character: "Character") -> None:
        from core.events import EventType

        self._character = character
        self._state = state
        self._cb_after = lambda **kw: self._on_after(kw.get("unit"), kw.get("action_type"))
        state.event_bus.subscribe(EventType.AFTER_ACTION, self._cb_after)

    def _on_after(self, unit: "Character", action_type: object) -> None:
        from core.enums import ActionType
        from core.events import EventType

        if unit is not self._character:
            return
        if action_type not in (ActionType.BASIC_ATTACK, ActionType.SKILL, ActionType.ENHANCED_BASIC):
            return
        heal_pct = self._PARAMS[self.superimpose - 1][1]
        for char in self._state.characters:
            if not hasattr(char, "receive_heal"):
                continue
            if hasattr(char, "is_memosprite") and char.is_memosprite:
                continue
            amount = int(char.max_hp * heal_pct)
            actual = char.receive_heal(amount)
            if actual > 0 and self._state.event_bus is not None:
                self._state.event_bus.emit(EventType.HEAL_DONE, healer=self._character,
                                            target=char, amount=actual)

    def on_unequip(self, character: "Character") -> None:
        from core.events import EventType

        character.stats.purge_source(self._SOURCE)
        if self._cb_after is not None and character.event_bus is not None:
            character.event_bus.unsubscribe(EventType.AFTER_ACTION, self._cb_after)

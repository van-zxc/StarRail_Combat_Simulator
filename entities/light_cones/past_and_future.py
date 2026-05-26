from __future__ import annotations
"""过往未来 (Past and Future) — 4★ 同谐光锥。

特效: 战技后，使下一个行动的我方其他目标伤害提高#1[i]%，持续#2[i]回合。
"""

from typing import Optional

from entities.light_cones.base import BaseLightCone
from entities.base import EquipmentEffect, StatModifier


class PastAndFuture(BaseLightCone):
    _default_id = "21025"
    _default_name = "过往未来"
    _default_path_key = "Shaman"

    _PROMOTIONS = [
        {"hp_base": 43.2, "hp_step": 6.48, "atk_base": 19.2, "atk_step": 2.88, "def_base": 18, "def_step": 2.7},
        {"hp_base": 95.04, "hp_step": 6.48, "atk_base": 42.24, "atk_step": 2.88, "def_base": 39.6, "def_step": 2.7},
        {"hp_base": 164.16, "hp_step": 6.48, "atk_base": 72.96, "atk_step": 2.88, "def_base": 68.4, "def_step": 2.7},
        {"hp_base": 233.28, "hp_step": 6.48, "atk_base": 103.68, "atk_step": 2.88, "def_base": 97.2, "def_step": 2.7},
        {"hp_base": 302.4, "hp_step": 6.48, "atk_base": 134.4, "atk_step": 2.88, "def_base": 126, "def_step": 2.7},
        {"hp_base": 371.52, "hp_step": 6.48, "atk_base": 165.12, "atk_step": 2.88, "def_base": 154.8, "def_step": 2.7},
        {"hp_base": 440.64, "hp_step": 6.48, "atk_base": 195.84, "atk_step": 2.88, "def_base": 183.6, "def_step": 2.7},
    ]

    def __init__(self, id: str = "", **kwargs):
        super().__init__(id=id, **kwargs)
        if self.effect is None:
            self.effect = PastAndFutureEffect(self.superimpose)


class PastAndFutureEffect(EquipmentEffect):
    _PARAMS = [[0.16, 1], [0.20, 1], [0.24, 1], [0.28, 1], [0.32, 1]]
    _SOURCE = "LightCone_21025"

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
        from core.enums import ActionType, StatType, StatModifierType

        if unit is not self._character:
            return
        if action_type != ActionType.SKILL:
            return
        p = self._PARAMS[self.superimpose - 1]
        dmg_pct = p[0]
        duration = p[1]
        # 查找下一个行动的我方其他目标（排除自身和 memosprite）
        next_ally = None
        min_av = float("inf")
        for char in self._state.characters:
            if char is self._character:
                continue
            if hasattr(char, "is_memosprite") and char.is_memosprite:
                continue
            if char.current_av < min_av:
                min_av = char.current_av
                next_ally = char
        if next_ally is None:
            return
        mod = StatModifier(
            stat_type=StatType.DMG_BONUS,
            modifier_type=StatModifierType.PERCENT,
            value=dmg_pct,
            source=self._SOURCE,
            duration=duration,
            dispellable=False,
        )
        next_ally.stats.apply_modifier(mod, "refresh")

    def on_unequip(self, character: "Character") -> None:
        from core.events import EventType

        character.stats.purge_source(self._SOURCE)
        if self._cb_after is not None and character.event_bus is not None:
            character.event_bus.unsubscribe(EventType.AFTER_ACTION, self._cb_after)

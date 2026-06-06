from __future__ import annotations
"""我们是地火 (We Are Wildfire) — 4★ 存护光锥。

特效: 战斗开始时，全体受到伤害降低#2[i]%（#3[i]回合）+ 回复已损失生命#1[i]%。
"""

from typing import Optional

from entities.light_cones.base import BaseLightCone
from entities.base import EquipmentEffect, StatModifier


class WeAreWildfire(BaseLightCone):
    _default_id = "21023"
    _default_name = "我们是地火"
    _default_path_key = "Knight"

    _PROMOTIONS = [
        {"hp_base": 33.6, "hp_step": 5.04, "atk_base": 21.6, "atk_step": 3.24, "def_base": 21, "def_step": 3.15},
        {"hp_base": 73.92, "hp_step": 5.04, "atk_base": 47.52, "atk_step": 3.24, "def_base": 46.2, "def_step": 3.15},
        {"hp_base": 127.68, "hp_step": 5.04, "atk_base": 82.08, "atk_step": 3.24, "def_base": 79.8, "def_step": 3.15},
        {"hp_base": 181.44, "hp_step": 5.04, "atk_base": 116.64, "atk_step": 3.24, "def_base": 113.4, "def_step": 3.15},
        {"hp_base": 235.2, "hp_step": 5.04, "atk_base": 151.2, "atk_step": 3.24, "def_base": 147, "def_step": 3.15},
        {"hp_base": 288.96, "hp_step": 5.04, "atk_base": 185.76, "atk_step": 3.24, "def_base": 180.6, "def_step": 3.15},
        {"hp_base": 342.72, "hp_step": 5.04, "atk_base": 220.32, "atk_step": 3.24, "def_base": 214.2, "def_step": 3.15},
    ]

    def __init__(self, id: str = "", **kwargs):
        super().__init__(id=id, **kwargs)
        if self.effect is None:
            self.effect = WeAreWildfireEffect(self.superimpose)


class WeAreWildfireEffect(EquipmentEffect):
    _PARAMS = [[0.30, 0.08, 5], [0.35, 0.10, 5], [0.40, 0.12, 5], [0.45, 0.14, 5], [0.50, 0.16, 5]]
    _SOURCE = "LightCone_21023"

    def __init__(self, superimpose: int = 1) -> None:
        self.superimpose = max(1, min(superimpose, 5))
        self._character: Optional["Character"] = None
        self._state: Optional["GameState"] = None
        self._cb_start: Optional[callable] = None

    def on_equip(self, character: "Character") -> None:
        pass

    def on_combat_start(self, state: "GameState", character: "Character") -> None:
        from core.events import EventType

        self._character = character
        self._state = state
        self._cb_start = lambda **kw: self._on_start()
        state.event_bus.subscribe(EventType.BATTLE_START, self._cb_start)

    def _on_start(self) -> None:
        from core.enums import StatType, StatModifierType
        from core.events import EventType

        p = self._PARAMS[self.superimpose - 1]
        heal_pct = p[0]
        dmg_mit = p[1]
        duration = p[2]

        # Team heal: recover lost_hp * pct for each ally
        for char in self._state.characters:
            if not hasattr(char, "receive_heal"):
                continue
            if hasattr(char, "is_memosprite") and char.is_memosprite:
                continue
            lost = char.max_hp - char.hp
            if lost > 0:
                amount = int(lost * heal_pct)
                actual = char.receive_heal(amount)
                if actual > 0 and self._state.event_bus is not None:
                    self._state.event_bus.emit(EventType.HEAL_DONE, healer=self._character,
                                                target=char, amount=actual)

        # Team DMG_MITIGATION
        mod = StatModifier(
            stat_type=StatType.DMG_MITIGATION,
            modifier_type=StatModifierType.PERCENT,
            value=dmg_mit,
            source=self._SOURCE,
            duration=duration,
            dispellable=False,
        )
        for char in self._state.characters:
            if not hasattr(char, "stats"):
                continue
            if hasattr(char, "is_memosprite") and char.is_memosprite:
                continue
            char.stats.apply_modifier(mod, "refresh")

    def on_unequip(self, character: "Character") -> None:
        from core.events import EventType

        for c in getattr(self._state, "characters", []):
            if hasattr(c, "stats"):
                c.stats.purge_source(self._SOURCE)
        if self._cb_start is not None and character.event_bus is not None:
            character.event_bus.unsubscribe(EventType.BATTLE_START, self._cb_start)

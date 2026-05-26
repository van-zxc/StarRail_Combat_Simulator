from __future__ import annotations
"""早餐的仪式感 (The Seriousness of Breakfast) — 4★ 智识光锥。

特效: 造成伤害提高#1[i]%，每消灭1个目标攻击力提高#2[i]%（最多#3[i]层）。
"""

from typing import Optional

from entities.light_cones.base import BaseLightCone
from entities.base import EquipmentEffect, StatModifier


class SeriousnessOfBreakfast(BaseLightCone):
    _default_id = "21027"
    _default_name = "早餐的仪式感"
    _default_path_key = "Mage"

    _PROMOTIONS = [
        {"hp_base": 38.4, "hp_step": 5.76, "atk_base": 21.6, "atk_step": 3.24, "def_base": 18, "def_step": 2.7},
        {"hp_base": 84.48, "hp_step": 5.76, "atk_base": 47.52, "atk_step": 3.24, "def_base": 39.6, "def_step": 2.7},
        {"hp_base": 145.92, "hp_step": 5.76, "atk_base": 82.08, "atk_step": 3.24, "def_base": 68.4, "def_step": 2.7},
        {"hp_base": 207.36, "hp_step": 5.76, "atk_base": 116.64, "atk_step": 3.24, "def_base": 97.2, "def_step": 2.7},
        {"hp_base": 268.8, "hp_step": 5.76, "atk_base": 151.2, "atk_step": 3.24, "def_base": 126, "def_step": 2.7},
        {"hp_base": 330.24, "hp_step": 5.76, "atk_base": 185.76, "atk_step": 3.24, "def_base": 154.8, "def_step": 2.7},
        {"hp_base": 391.68, "hp_step": 5.76, "atk_base": 220.32, "atk_step": 3.24, "def_base": 183.6, "def_step": 2.7},
    ]

    def __init__(self, id: str = "", **kwargs):
        super().__init__(id=id, **kwargs)
        if self.effect is None:
            self.effect = SeriousnessOfBreakfastEffect(self.superimpose)


class SeriousnessOfBreakfastEffect(EquipmentEffect):
    _PARAMS = [[0.12, 0.04, 3], [0.15, 0.05, 3], [0.18, 0.06, 3], [0.21, 0.07, 3], [0.24, 0.08, 3]]
    _SOURCE = "LightCone_21027"

    def __init__(self, superimpose: int = 1) -> None:
        self.superimpose = max(1, min(superimpose, 5))
        self._character: Optional["Character"] = None
        self._kill_count: int = 0
        self._cb_kill: Optional[callable] = None

    def on_equip(self, character: "Character") -> None:
        from core.enums import StatType, StatModifierType

        dmg_pct = self._PARAMS[self.superimpose - 1][0]
        mod = StatModifier(
            stat_type=StatType.DMG_BONUS,
            modifier_type=StatModifierType.PERCENT,
            value=dmg_pct,
            source=self._SOURCE,
            dispellable=False,
        )
        character.stats.apply_modifier(mod, "refresh")

    def on_combat_start(self, state: "GameState", character: "Character") -> None:
        from core.events import EventType

        self._character = character
        self._cb_kill = lambda **kw: self._on_kill(kw.get("source"))
        state.event_bus.subscribe(EventType.ON_KILL, self._cb_kill)

    def _recalc_atk_stacks(self) -> None:
        from core.enums import StatType, StatModifierType

        p = self._PARAMS[self.superimpose - 1]
        per_stack = p[1]
        max_stacks = p[2]
        stacks = min(self._kill_count, max_stacks)
        mod = StatModifier(
            stat_type=StatType.ATK,
            modifier_type=StatModifierType.PERCENT,
            value=per_stack * stacks,
            source=self._SOURCE,
            dispellable=False,
        )
        self._character.stats.apply_modifier(mod, "refresh")

    def _on_kill(self, source: "Character") -> None:
        if source is not self._character:
            return
        self._kill_count += 1
        self._recalc_atk_stacks()

    def on_unequip(self, character: "Character") -> None:
        from core.events import EventType

        character.stats.purge_source(self._SOURCE)
        if self._cb_kill is not None and character.event_bus is not None:
            character.event_bus.unsubscribe(EventType.ON_KILL, self._cb_kill)

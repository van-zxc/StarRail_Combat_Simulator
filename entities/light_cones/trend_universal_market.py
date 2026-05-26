from __future__ import annotations
"""宇宙市场趋势 (Trend of the Universal Market) — 4★ 存护光锥。

特效: 防御力提高#1[i]%，受击后#2[i]%基础概率使敌人灼烧（DEF×#3[i]%/回合，#4[i]回合）。
"""

import random
from typing import Optional

from entities.light_cones.base import BaseLightCone
from entities.base import EquipmentEffect, StatModifier, DoTStatus


class TrendUniversalMarket(BaseLightCone):
    _default_id = "21016"
    _default_name = "宇宙市场趋势"
    _default_path_key = "Knight"

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
            self.effect = TrendUniversalMarketEffect(self.superimpose)


class TrendUniversalMarketEffect(EquipmentEffect):
    _PARAMS = [[0.16, 1.00, 0.40, 2], [0.20, 1.05, 0.50, 2], [0.24, 1.10, 0.60, 2],
               [0.28, 1.15, 0.70, 2], [0.32, 1.20, 0.80, 2]]
    _SOURCE = "LightCone_21016"

    def __init__(self, superimpose: int = 1) -> None:
        self.superimpose = max(1, min(superimpose, 5))
        self._character: Optional["Character"] = None
        self._cb_hit: Optional[callable] = None

    def on_equip(self, character: "Character") -> None:
        from core.enums import StatType, StatModifierType

        def_pct = self._PARAMS[self.superimpose - 1][0]
        mod = StatModifier(
            stat_type=StatType.DEF,
            modifier_type=StatModifierType.PERCENT,
            value=def_pct,
            source=self._SOURCE,
            dispellable=False,
        )
        character.stats.apply_modifier(mod, "refresh")

    def on_combat_start(self, state: "GameState", character: "Character") -> None:
        from core.events import EventType

        self._character = character
        self._cb_hit = lambda **kw: self._on_hit(kw.get("target"), kw.get("source"))
        state.event_bus.subscribe(EventType.ON_HIT, self._cb_hit)

    def _on_hit(self, target: "Fighter", source: "Fighter") -> None:
        if target is not self._character:
            return
        if source is None or not hasattr(source, "dot_statuses"):
            return
        from core.enums import ElementType, StatType

        p = self._PARAMS[self.superimpose - 1]
        base_chance = p[1]
        def_coeff = p[2]
        duration = p[3]

        ehr = self._character.stats.get_total_stat(StatType.EFFECT_HIT_RATE)
        actual_chance = base_chance * (1.0 + ehr)
        if random.random() >= actual_chance:
            return

        def_total = self._character.stats.get_total_stat(StatType.DEF)
        burn_mult = def_total * def_coeff / self._character.atk

        dot = DoTStatus(
            source_character=self._character,
            element=ElementType.FIRE,
            dot_multiplier=burn_mult,
            duration=duration,
        )
        source.dot_statuses.append(dot)

    def on_unequip(self, character: "Character") -> None:
        from core.events import EventType

        character.stats.purge_source(self._SOURCE)
        if self._cb_hit is not None and character.event_bus is not None:
            character.event_bus.unsubscribe(EventType.ON_HIT, self._cb_hit)

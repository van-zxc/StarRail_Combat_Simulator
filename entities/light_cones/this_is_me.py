from __future__ import annotations
"""这就是我啦！ (This Is Me!) — 4★ 存护光锥。

特效: 防御力提高#1[i]%，终结技伤害提高=防御力×#2[i]%（加到基础伤害，后续乘区全吃）。
"""

from typing import Optional

from entities.light_cones.base import BaseLightCone
from entities.base import EquipmentEffect, StatModifier


class ThisIsMe(BaseLightCone):
    _default_id = "21030"
    _default_name = "这就是我啦！"
    _default_path_key = "Knight"

    _PROMOTIONS = [
        {"hp_base": 38.4, "hp_step": 5.76, "atk_base": 16.8, "atk_step": 2.52, "def_base": 24, "def_step": 3.6},
        {"hp_base": 84.48, "hp_step": 5.76, "atk_base": 36.96, "atk_step": 2.52, "def_base": 52.8, "def_step": 3.6},
        {"hp_base": 145.92, "hp_step": 5.76, "atk_base": 63.84, "atk_step": 2.52, "def_base": 91.2, "def_step": 3.6},
        {"hp_base": 207.36, "hp_step": 5.76, "atk_base": 90.72, "atk_step": 2.52, "def_base": 129.6, "def_step": 3.6},
        {"hp_base": 268.8, "hp_step": 5.76, "atk_base": 117.6, "atk_step": 2.52, "def_base": 168, "def_step": 3.6},
        {"hp_base": 330.24, "hp_step": 5.76, "atk_base": 144.48, "atk_step": 2.52, "def_base": 206.4, "def_step": 3.6},
        {"hp_base": 391.68, "hp_step": 5.76, "atk_base": 171.36, "atk_step": 2.52, "def_base": 244.8, "def_step": 3.6},
    ]

    def __init__(self, id: str = "", **kwargs):
        super().__init__(id=id, **kwargs)
        if self.effect is None:
            self.effect = ThisIsMeEffect(self.superimpose)


class ThisIsMeEffect(EquipmentEffect):
    _PARAMS = [[0.16, 0.60], [0.20, 0.75], [0.24, 0.90], [0.28, 1.05], [0.32, 1.20]]
    _SOURCE = "LightCone_21030"

    def __init__(self, superimpose: int = 1) -> None:
        self.superimpose = max(1, min(superimpose, 5))
        self._character: Optional["Character"] = None
        self._cb_ult: Optional[callable] = None
        self._cb_after: Optional[callable] = None

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
        self._cb_ult = lambda **kw: self._on_ult(kw.get("character"))
        self._cb_after = lambda **kw: self._on_after(kw.get("unit"), kw.get("action_type"))
        bus = state.event_bus
        bus.subscribe(EventType.ON_ULTIMATE_INSERTED, self._cb_ult)
        bus.subscribe(EventType.AFTER_ACTION, self._cb_after)

    def _on_ult(self, caster: "Character") -> None:
        if caster is not self._character:
            return
        from core.enums import StatType

        coeff = self._PARAMS[self.superimpose - 1][1]
        def_total = self._character.stats.get_total_stat(StatType.DEF)
        self._character._extra_base_dmg = def_total * coeff

    def _on_after(self, unit: "Character", action_type: object) -> None:
        from core.enums import ActionType

        if unit is not self._character:
            return
        if action_type != ActionType.ULTIMATE:
            return
        self._character._extra_base_dmg = 0.0

    def on_unequip(self, character: "Character") -> None:
        from core.events import EventType

        character.stats.purge_source(self._SOURCE)
        if hasattr(character, "_extra_base_dmg"):
            character._extra_base_dmg = 0.0
        if character.event_bus is not None:
            bus = character.event_bus
            if self._cb_ult is not None:
                bus.unsubscribe(EventType.ON_ULTIMATE_INSERTED, self._cb_ult)
            if self._cb_after is not None:
                bus.unsubscribe(EventType.AFTER_ACTION, self._cb_after)

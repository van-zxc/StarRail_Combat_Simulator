from __future__ import annotations
"""拂晓之前 (Before Dawn) — 5★ 智识光锥。

特效:
  1. 暴击伤害提高#1[i]%
  2. 战技和终结技伤害提高#2[i]%
  3. 战技/终结技后获得【梦身】，下次追加攻击消耗并提高#3[i]%伤害
"""

from typing import Optional

from entities.light_cones.base import BaseLightCone
from entities.base import EquipmentEffect, StatModifier


class BeforeDawn(BaseLightCone):
    _default_id = "23010"
    _default_name = "拂晓之前"
    _default_path_key = "Mage"

    _PROMOTIONS = [
        {"hp_base": 48, "hp_step": 7.2, "atk_base": 26.4, "atk_step": 3.96, "def_base": 21, "def_step": 3.15},
        {"hp_base": 105.6, "hp_step": 7.2, "atk_base": 58.08, "atk_step": 3.96, "def_base": 46.2, "def_step": 3.15},
        {"hp_base": 182.4, "hp_step": 7.2, "atk_base": 100.32, "atk_step": 3.96, "def_base": 79.8, "def_step": 3.15},
        {"hp_base": 259.2, "hp_step": 7.2, "atk_base": 142.56, "atk_step": 3.96, "def_base": 113.4, "def_step": 3.15},
        {"hp_base": 336, "hp_step": 7.2, "atk_base": 184.8, "atk_step": 3.96, "def_base": 147, "def_step": 3.15},
        {"hp_base": 412.8, "hp_step": 7.2, "atk_base": 227.04, "atk_step": 3.96, "def_base": 180.6, "def_step": 3.15},
        {"hp_base": 489.6, "hp_step": 7.2, "atk_base": 269.28, "atk_step": 3.96, "def_base": 214.2, "def_step": 3.15},
    ]

    def __init__(self, id: str = "", **kwargs):
        super().__init__(id=id, **kwargs)
        if self.effect is None:
            self.effect = BeforeDawnEffect(self.superimpose)


class BeforeDawnEffect(EquipmentEffect):
    _PARAMS = [
        [0.36, 0.18, 0.48],
        [0.42, 0.21, 0.56],
        [0.48, 0.24, 0.64],
        [0.54, 0.27, 0.72],
        [0.60, 0.30, 0.80],
    ]
    _SOURCE = "LightCone_23010_CDMG"
    _SKILL_ULT_SOURCE = "LightCone_23010_SKILL_ULT"
    _DREAM_SOURCE = "LightCone_23010_DREAM"

    def __init__(self, superimpose: int = 1) -> None:
        self.superimpose = max(1, min(superimpose, 5))
        self._character: Optional["Character"] = None
        self._dream_body: bool = False
        self._cb_action_start: Optional[callable] = None
        self._cb_after: Optional[callable] = None

    def on_equip(self, character: "Character") -> None:
        from core.enums import StatType, StatModifierType

        p = self._PARAMS[self.superimpose - 1]
        cd_mod = StatModifier(
            stat_type=StatType.CRIT_DMG,
            modifier_type=StatModifierType.PERCENT,
            value=p[0],
            source=self._SOURCE,
            dispellable=False,
        )
        sd_mod = StatModifier(
            stat_type=StatType.SKILL_DMG,
            modifier_type=StatModifierType.PERCENT,
            value=p[1],
            source=self._SKILL_ULT_SOURCE,
            dispellable=False,
        )
        ud_mod = StatModifier(
            stat_type=StatType.ULT_DMG,
            modifier_type=StatModifierType.PERCENT,
            value=p[1],
            source=self._SKILL_ULT_SOURCE,
            dispellable=False,
        )
        character.stats.apply_modifier(cd_mod, "refresh")
        character.stats.apply_modifier(sd_mod, "refresh")
        character.stats.apply_modifier(ud_mod, "refresh")

    def on_combat_start(self, state: "GameState", character: "Character") -> None:
        from core.events import EventType

        self._character = character
        self._cb_action_start = lambda **kw: self._on_action_start(
            kw.get("unit"), kw.get("tags"))
        self._cb_after = lambda **kw: self._on_after(
            kw.get("unit"), kw.get("action_type"), kw.get("tags"))
        state.event_bus.subscribe(EventType.ACTION_START, self._cb_action_start)
        state.event_bus.subscribe(EventType.AFTER_ACTION, self._cb_after)

    def _on_action_start(self, unit: "Character", tags: object) -> None:
        if unit is not self._character:
            return
        if not self._dream_body:
            return
        from core.enums import StatType, StatModifierType

        tag_set = tags or set()
        if "follow_up" in tag_set:
            fua_pct = self._PARAMS[self.superimpose - 1][2]
            mod = StatModifier(
                stat_type=StatType.FUA_DMG,
                modifier_type=StatModifierType.PERCENT,
                value=fua_pct,
                source=self._DREAM_SOURCE,
                dispellable=False,
            )
            self._character.stats.apply_modifier(mod, "refresh")

    def _on_after(self, unit: "Character", action_type: object, tags: object) -> None:
        from core.enums import ActionType

        if unit is not self._character:
            return

        tag_set = tags or set()
        if "follow_up" in tag_set and self._dream_body:
            self._character.stats.purge_source(self._DREAM_SOURCE)
            self._dream_body = False
            return

        if action_type in (ActionType.SKILL, ActionType.ULTIMATE):
            self._dream_body = True

    def on_unequip(self, character: "Character") -> None:
        from core.events import EventType

        character.stats.purge_source(self._SOURCE)
        character.stats.purge_source(self._SKILL_ULT_SOURCE)
        character.stats.purge_source(self._DREAM_SOURCE)
        self._dream_body = False
        if character.event_bus is not None:
            bus = character.event_bus
            if self._cb_action_start is not None:
                bus.unsubscribe(EventType.ACTION_START, self._cb_action_start)
            if self._cb_after is not None:
                bus.unsubscribe(EventType.AFTER_ACTION, self._cb_after)

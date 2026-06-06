from __future__ import annotations
"""Herta — 智识·冰属性角色 (lv80 满破数据, from 1013_herta.json)."""

from core.enums import ElementType, PathType, StatType, ActionType
from core.entity_stats import stats_defaults
from entities.characters.template_character.template_character import TemplateCharacter
from entities.characters.herta.skills import (
    HertaBasicAttack,
    HertaSkill,
    HertaUltimate,
    HertaTalent,
    HertaTechnique,
)
from entities.characters.herta.traces import TRACE_REGISTRY as HERTA_TRACES
from entities.characters.herta.eidolons import EIDOLON_REGISTRY as HERTA_EIDOLONS


class Herta(TemplateCharacter):
    _default_id = "Herta"
    _default_level = 80
    _default_element = ElementType.ICE
    _default_path = PathType.ERUDITION

    _base_stats = {
        **stats_defaults(),
        StatType.HP: 505.44,
        StatType.ATK: 308.88,
        StatType.DEF: 210.6,
        StatType.SPD: 100.0,
        StatType.CRIT_RATE: 0.05,
        StatType.CRIT_DMG: 0.50,
        StatType.ERR: 1.0,
        StatType.MAX_ENERGY: 110.0,
        StatType.AGGRO_MODIFIER: -0.25,
    }

    def __init__(self, character_id="", level=None, unlocked_traces=None, eidolon_level=0):
        self._has_efficiency: bool = False
        self._has_freeze: bool = False
        self._has_e1: bool = False
        self._has_e2: bool = False
        self._has_e4: bool = False
        self._has_e6: bool = False

        super().__init__(character_id, level, unlocked_traces, eidolon_level)

    def _init_skills(self) -> None:
        self._skills["basic"] = HertaBasicAttack(self)
        self._skills["skill"] = HertaSkill(self)
        self._skills["ultimate"] = HertaUltimate(self)
        self._skills["talent"] = HertaTalent(self)
        self._skills["technique"] = HertaTechnique(self)

    def _init_traces(self, unlocked: list[str]) -> None:
        self._has_efficiency = "Efficiency" in unlocked
        self._has_freeze = "Freeze" in unlocked
        for key in unlocked:
            fn = HERTA_TRACES.get(key)
            if fn:
                for mod in fn(self):
                    self.stats.add_modifier(mod)

    def _init_eidolons(self, level: int) -> None:
        for lv in range(1, level + 1):
            fn = HERTA_EIDOLONS.get(lv)
            if fn:
                for mod in fn(self):
                    self.stats.add_modifier(mod)

from __future__ import annotations
"""Silver Wolf — 虚无·量子 (lv80 满破数据, from 1006_silverwolf.json, Enhanced 11006xx)."""

from core.enums import ElementType, PathType, StatType
from core.entity_stats import stats_defaults
from entities.characters.template_character.template_character import TemplateCharacter
from entities.characters.silverwolf.skills import (
    SilverWolfBasicAttack,
    SilverWolfSkill,
    SilverWolfUltimate,
    SilverWolfTalent,
    SilverWolfTechnique,
)
from entities.characters.silverwolf.traces import TRACE_REGISTRY as SW_TRACES
from entities.characters.silverwolf.eidolons import EIDOLON_REGISTRY as SW_EIDOLONS


class SilverWolf(TemplateCharacter):
    _default_id = "SilverWolf"
    _default_level = 80
    _default_element = ElementType.QUANTUM
    _default_path = PathType.NIHILITY

    _base_stats = {
        **stats_defaults(),
        StatType.HP: 555.984,
        StatType.ATK: 339.768,
        StatType.DEF: 244.53,
        StatType.SPD: 107.0,
        StatType.CRIT_RATE: 0.05,
        StatType.CRIT_DMG: 0.50,
        StatType.ERR: 1.0,
        StatType.MAX_ENERGY: 110.0,
        StatType.AGGRO_MODIFIER: 0.0,
    }

    def __init__(self, character_id="", level=None, unlocked_traces=None, eidolon_level=0):
        self._has_generate: bool = False
        self._has_inject: bool = False
        self._has_annotation: bool = False

        self._has_e1: bool = False
        self._has_e2: bool = False
        self._has_e4: bool = False
        self._has_e6: bool = False

        super().__init__(character_id, level, unlocked_traces, eidolon_level)

    def _init_skills(self) -> None:
        self._skills["basic"] = SilverWolfBasicAttack(self)
        self._skills["skill"] = SilverWolfSkill(self)
        self._skills["ultimate"] = SilverWolfUltimate(self)
        self._skills["talent"] = SilverWolfTalent(self)
        self._skills["technique"] = SilverWolfTechnique(self)

    def _init_traces(self, unlocked: list[str]) -> None:
        self._has_generate = "Generate" in unlocked
        self._has_inject = "Inject" in unlocked
        self._has_annotation = "Annotation" in unlocked
        for key in unlocked:
            fn = SW_TRACES.get(key)
            if fn:
                for mod in fn(self):
                    self.stats.add_modifier(mod)

    def _init_eidolons(self, level: int) -> None:
        for lv in range(1, level + 1):
            fn = SW_EIDOLONS.get(lv)
            if fn:
                for mod in fn(self):
                    self.stats.add_modifier(mod)

from __future__ import annotations
"""Asta — 同谐·火 (lv80 满破数据, from 1009_asta.json)."""

from core.enums import ElementType, PathType, StatType, ActionType
from core.entity_stats import stats_defaults
from entities.characters.template_character.template_character import TemplateCharacter
from entities.characters.asta.skills import (
    AstaBasicAttack,
    AstaSkill,
    AstaUltimate,
    AstaTalent,
    AstaTechnique,
)
from entities.characters.asta.traces import TRACE_REGISTRY as A_TRACES
from entities.characters.asta.eidolons import EIDOLON_REGISTRY as A_EIDOLONS


class Asta(TemplateCharacter):
    _default_id = "Asta"
    _default_level = 80
    _default_element = ElementType.FIRE
    _default_path = PathType.HARMONY

    _toughness_map = {
        ActionType.TALENT: 20.0,
    }

    _base_stats = {
        **stats_defaults(),
        StatType.HP: 542.88,
        StatType.ATK: 271.44,
        StatType.DEF: 245.7,
        StatType.SPD: 106.0,
        StatType.CRIT_RATE: 0.05,
        StatType.CRIT_DMG: 0.50,
        StatType.ERR: 1.0,
        StatType.MAX_ENERGY: 120.0,
        StatType.AGGRO_MODIFIER: 0.0,
    }

    def __init__(self, character_id="", level=None, unlocked_traces=None, eidolon_level=0):
        self._charge_count: int = 0
        self._charge_max: int = 5
        self._turn_count: int = 0

        self._has_spark: bool = False
        self._has_ignite: bool = False
        self._has_constellation: bool = False

        self._has_e1: bool = False
        self._has_e2: bool = False
        self._e2_skip_decay: bool = False
        self._has_e4: bool = False
        self._has_e6: bool = False

        super().__init__(character_id, level, unlocked_traces, eidolon_level)

    def _init_skills(self) -> None:
        self._skills["basic"] = AstaBasicAttack(self)
        self._skills["skill"] = AstaSkill(self)
        self._skills["ultimate"] = AstaUltimate(self)
        self._skills["talent"] = AstaTalent(self)
        self._skills["technique"] = AstaTechnique(self)

    def _init_traces(self, unlocked: list[str]) -> None:
        self._has_spark = "Spark" in unlocked
        self._has_ignite = "Ignite" in unlocked
        self._has_constellation = "Constellation" in unlocked
        for key in unlocked:
            fn = A_TRACES.get(key)
            if fn:
                for mod in fn(self):
                    self.stats.add_modifier(mod)

    def _init_eidolons(self, level: int) -> None:
        for lv in range(1, level + 1):
            fn = A_EIDOLONS.get(lv)
            if fn:
                for mod in fn(self):
                    self.stats.add_modifier(mod)

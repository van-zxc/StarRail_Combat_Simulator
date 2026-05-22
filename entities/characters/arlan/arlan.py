from __future__ import annotations
"""Arlan — 毁灭·雷 (lv80 满破数据, from 1008_arlan.json)."""

from core.enums import ElementType, PathType, StatType, ActionType
from core.entity_stats import stats_defaults
from entities.characters.template_character.template_character import TemplateCharacter
from entities.characters.arlan.skills import (
    ArlanBasicAttack,
    ArlanSkill,
    ArlanUltimate,
    ArlanTalent,
    ArlanTechnique,
)
from entities.characters.arlan.traces import TRACE_REGISTRY as A_TRACES
from entities.characters.arlan.eidolons import EIDOLON_REGISTRY as A_EIDOLONS


class Arlan(TemplateCharacter):
    _default_id = "Arlan"
    _default_level = 80
    _default_element = ElementType.LIGHTNING
    _default_path = PathType.DESTRUCTION

    _toughness_map = {
        ActionType.BASIC_ATTACK: 10.0,
        ActionType.SKILL: 20.0,
        ActionType.ULTIMATE: 20.0,
    }
    _energy_map = {
        ActionType.BASIC_ATTACK: 20.0,
        ActionType.SKILL: 30.0,
        ActionType.ULTIMATE: 5.0,
    }

    _base_stats = {
        **stats_defaults(),
        StatType.HP: 636.48,
        StatType.ATK: 318.24,
        StatType.DEF: 175.5,
        StatType.SPD: 102.0,
        StatType.CRIT_RATE: 0.05,
        StatType.CRIT_DMG: 0.50,
        StatType.ERR: 1.0,
        StatType.MAX_ENERGY: 110.0,
        StatType.AGGRO_MODIFIER: 0.25,
    }

    def __init__(self, character_id="", level=None, unlocked_traces=None, eidolon_level=0):
        self._has_revival: bool = False
        self._has_endurance: bool = False
        self._has_repel: bool = False

        self._has_e1: bool = False
        self._has_e2: bool = False
        self._has_e4: bool = False
        self._has_e6: bool = False

        self._e4_active: bool = False
        self._e4_remaining: int = 0

        super().__init__(character_id, level, unlocked_traces, eidolon_level)

    def _init_skills(self) -> None:
        self._skills["basic"] = ArlanBasicAttack(self)
        self._skills["skill"] = ArlanSkill(self)
        self._skills["ultimate"] = ArlanUltimate(self)
        self._skills["talent"] = ArlanTalent(self)
        self._skills["technique"] = ArlanTechnique(self)

    def _init_traces(self, unlocked: list[str]) -> None:
        self._has_revival = "Revival" in unlocked
        self._has_endurance = "Endurance" in unlocked
        self._has_repel = "Repel" in unlocked
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

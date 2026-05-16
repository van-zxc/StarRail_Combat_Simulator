"""Welt — 虚无·虚数属性角色 (lv80 满破数据, from 1004_welt.json, Enhanced 11004xx)."""

from __future__ import annotations

from core.enums import ElementType, PathType, StatType, ActionType
from core.entity_stats import stats_defaults
from entities.characters.template_character.template_character import TemplateCharacter
from entities.characters.welt.skills import (
    WeltBasicAttack,
    WeltSkill,
    WeltUltimate,
    WeltTalent,
    WeltTechnique,
)
from entities.characters.welt.traces import TRACE_REGISTRY as W_TRACES
from entities.characters.welt.eidolons import EIDOLON_REGISTRY as W_EIDOLONS


class Welt(TemplateCharacter):
    _default_id = "Welt"
    _default_level = 80
    _default_element = ElementType.IMAGINARY
    _default_path = PathType.NIHILITY

    _toughness_map = {
        ActionType.ULTIMATE: 20.0,
    }

    _base_stats = {
        **stats_defaults(),
        StatType.HP: 597.168,
        StatType.ATK: 329.472,
        StatType.DEF: 270.27,
        StatType.SPD: 102.0,
        StatType.CRIT_RATE: 0.05,
        StatType.CRIT_DMG: 0.50,
        StatType.ERR: 1.0,
        StatType.MAX_ENERGY: 120.0,
        StatType.AGGRO_MODIFIER: 0.0,
    }

    def __init__(self, character_id="", level=None, unlocked_traces=None, eidolon_level=0):
        self._has_retribution: bool = False
        self._has_judgement: bool = False
        self._has_verdict: bool = False
        self._has_e1: bool = False
        self._e1_empower_remaining: int = 0
        self._has_e2: bool = False
        self._has_e4: bool = False
        self._has_e6: bool = False
        self._killing_action: str = ""

        super().__init__(character_id, level, unlocked_traces, eidolon_level)

    def _init_skills(self) -> None:
        self._skills["basic"] = WeltBasicAttack(self)
        self._skills["skill"] = WeltSkill(self)
        self._skills["ultimate"] = WeltUltimate(self)
        self._skills["talent"] = WeltTalent(self)
        self._skills["technique"] = WeltTechnique(self)

    def _init_traces(self, unlocked: list[str]) -> None:
        self._has_retribution = "Retribution" in unlocked
        self._has_judgement = "Judgement" in unlocked
        self._has_verdict = "Verdict" in unlocked
        for key in unlocked:
            fn = W_TRACES.get(key)
            if fn:
                for mod in fn(self):
                    self.stats.add_modifier(mod)

    def _init_eidolons(self, level: int) -> None:
        for lv in range(1, level + 1):
            fn = W_EIDOLONS.get(lv)
            if fn:
                for mod in fn(self):
                    self.stats.add_modifier(mod)

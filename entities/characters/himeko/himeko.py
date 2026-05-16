"""Himeko — 智识·火属性角色 (lv80 满破数据, from 1003_himeko.json)."""

from __future__ import annotations

from core.enums import ElementType, PathType, StatType, ActionType
from core.entity_stats import stats_defaults
from entities.characters.template_character.template_character import TemplateCharacter
from entities.characters.himeko.skills import (
    HimekoBasicAttack,
    HimekoSkill,
    HimekoUltimate,
    HimekoTalent,
    HimekoTechnique,
)
from entities.characters.himeko.traces import TRACE_REGISTRY as H_TRACES
from entities.characters.himeko.eidolons import EIDOLON_REGISTRY as H_EIDOLONS


class Himeko(TemplateCharacter):
    _default_id = "Himeko"
    _default_level = 80
    _default_element = ElementType.FIRE
    _default_path = PathType.ERUDITION

    _toughness_map = {
        ActionType.FOLLOW_UP: 10.0,
    }

    _base_stats = {
        **stats_defaults(),
        StatType.HP: 555.984,
        StatType.ATK: 401.544,
        StatType.DEF: 231.66,
        StatType.SPD: 96.0,
        StatType.CRIT_RATE: 0.05,
        StatType.CRIT_DMG: 0.50,
        StatType.ERR: 1.0,
        StatType.MAX_ENERGY: 120.0,
        StatType.AGGRO_MODIFIER: -0.25,
    }

    def __init__(self, character_id="", level=None, unlocked_traces=None, eidolon_level=0):
        self._charge_count: int = 0
        self._charge_max: int = 3
        self._has_starfire: bool = False
        self._has_scorch: bool = False
        self._has_beacon: bool = False
        self._has_e1: bool = False
        self._has_e2: bool = False
        self._has_e4: bool = False
        self._has_e6: bool = False
        self._killing_action: str = ""

        super().__init__(character_id, level, unlocked_traces, eidolon_level)

    def _init_skills(self) -> None:
        self._skills["basic"] = HimekoBasicAttack(self)
        self._skills["skill"] = HimekoSkill(self)
        self._skills["ultimate"] = HimekoUltimate(self)
        self._skills["talent"] = HimekoTalent(self)
        self._skills["technique"] = HimekoTechnique(self)

    def _init_traces(self, unlocked: list[str]) -> None:
        self._has_starfire = "StarFire" in unlocked
        self._has_scorch = "Scorch" in unlocked
        self._has_beacon = "Beacon" in unlocked
        for key in unlocked:
            fn = H_TRACES.get(key)
            if fn:
                for mod in fn(self):
                    self.stats.add_modifier(mod)

    def _init_eidolons(self, level: int) -> None:
        for lv in range(1, level + 1):
            fn = H_EIDOLONS.get(lv)
            if fn:
                for mod in fn(self):
                    self.stats.add_modifier(mod)

from __future__ import annotations
"""March7th — 存护·冰属性角色 (lv80 满破数据, from character_ranks + character_promotions + character_skills + character_skill_trees)."""

from core.enums import ElementType, PathType, StatType, ActionType
from core.entity_stats import stats_defaults
from entities.characters.template_character.template_character import TemplateCharacter
from entities.characters.march_7th.skills import (
    March7thBasicAttack,
    March7thSkill,
    March7thUltimate,
    March7thTalent,
    March7thTechnique,
)
from entities.characters.march_7th.traces import TRACE_REGISTRY as M7_TRACES
from entities.characters.march_7th.eidolons import EIDOLON_REGISTRY as M7_EIDOLONS


class March7th(TemplateCharacter):
    _default_id = "March7th"
    _default_level = 80
    _default_element = ElementType.ICE
    _default_path = PathType.PRESERVATION

    _toughness_map = {
        ActionType.FOLLOW_UP: 10.0,
    }

    # values[6].base + step*10 (lv80)
    _base_stats = {
        **stats_defaults(),
        StatType.HP: 561.6,
        StatType.ATK: 271.44,
        StatType.DEF: 304.2,
        StatType.SPD: 101.0,
        StatType.CRIT_RATE: 0.05,
        StatType.CRIT_DMG: 0.50,
        StatType.ERR: 1.0,
        StatType.MAX_ENERGY: 120.0,
        StatType.AGGRO_MODIFIER: 0.5,  # 存护基础 taunt=150 → 1.5x
    }

    # 天赋反击计数器
    _counter_used: int = 0
    _counter_max: int = 2

    def __init__(self, character_id="", level=None, unlocked_traces=None, eidolon_level=0):
        super().__init__(character_id, level, unlocked_traces, eidolon_level)
        self._counter_used = 0
        self._counter_max = 2
        # 行迹能力状态 (供 skills 查询)
        self._has_cleanse: bool = False
        self._has_shield_plus: bool = False
        self._has_freeze_plus: bool = False
        # E4 DEF 增伤
        self._e4_def_flat: float = 0.0
        # E6 回血状态
        self._has_e6: bool = False

    def _init_skills(self) -> None:
        self._skills["basic"] = March7thBasicAttack(self)
        self._skills["skill"] = March7thSkill(self)
        self._skills["ultimate"] = March7thUltimate(self)
        self._skills["talent"] = March7thTalent(self)
        self._skills["technique"] = March7thTechnique(self)

    def _init_traces(self, unlocked: list[str]) -> None:
        self._has_cleanse = "Cleanse" in unlocked
        self._has_shield_plus = "ShieldPlus" in unlocked
        self._has_freeze_plus = "FreezePlus" in unlocked
        for key in unlocked:
            fn = M7_TRACES.get(key)
            if fn:
                for mod in fn(self):
                    self.stats.add_modifier(mod)

    def _init_eidolons(self, level: int) -> None:
        for lv in range(1, level + 1):
            fn = M7_EIDOLONS.get(lv)
            if fn:
                for mod in fn(self):
                    self.stats.add_modifier(mod)

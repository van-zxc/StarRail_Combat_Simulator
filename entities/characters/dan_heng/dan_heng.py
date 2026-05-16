"""DanHeng — 巡猎·风属性角色 (lv80 满破数据, from 1002_danheng.json)."""

from __future__ import annotations

from core.enums import ElementType, PathType, StatType, ActionType
from core.entity_stats import stats_defaults
from entities.characters.template_character.template_character import TemplateCharacter
from entities.characters.dan_heng.skills import (
    DanHengBasicAttack,
    DanHengSkill,
    DanHengUltimate,
    DanHengTalent,
    DanHengTechnique,
)
from entities.characters.dan_heng.traces import TRACE_REGISTRY as DH_TRACES
from entities.characters.dan_heng.eidolons import EIDOLON_REGISTRY as DH_EIDOLONS


class DanHeng(TemplateCharacter):
    _default_id = "DanHeng"
    _default_level = 80
    _default_element = ElementType.WIND
    _default_path = PathType.HUNT

    _toughness_map = {
        ActionType.ULTIMATE: 30.0,
    }

    # promotions.values[6].base + step*10 (lv80)
    _base_stats = {
        **stats_defaults(),
        StatType.HP: 468.0,
        StatType.ATK: 290.16,
        StatType.DEF: 210.6,
        StatType.SPD: 110.0,
        StatType.CRIT_RATE: 0.05,
        StatType.CRIT_DMG: 0.50,
        StatType.ERR: 1.0,
        StatType.MAX_ENERGY: 100.0,
        StatType.AGGRO_MODIFIER: -0.25,
    }

    def __init__(self, character_id="", level=None, unlocked_traces=None, eidolon_level=0):
        self._talent_buff_active: bool = False
        self._talent_cooldown_remaining: int = 0
        self._has_dragon_hide: bool = False
        self._dragon_hide_active: bool = False
        self._has_shadow: bool = False
        self._has_wind: bool = False
        self._has_e1: bool = False
        self._has_e2: bool = False
        self._has_e4: bool = False
        self._has_e6: bool = False
        self._killing_action: str = ""

        super().__init__(character_id, level, unlocked_traces, eidolon_level)

    def _init_skills(self) -> None:
        self._skills["basic"] = DanHengBasicAttack(self)
        self._skills["skill"] = DanHengSkill(self)
        self._skills["ultimate"] = DanHengUltimate(self)
        self._skills["talent"] = DanHengTalent(self)
        self._skills["technique"] = DanHengTechnique(self)

    def _init_traces(self, unlocked: list[str]) -> None:
        self._has_dragon_hide = "DragonHide" in unlocked
        self._has_shadow = "Shadow" in unlocked
        self._has_wind = "Wind" in unlocked
        for key in unlocked:
            fn = DH_TRACES.get(key)
            if fn:
                for mod in fn(self):
                    self.stats.add_modifier(mod)

    def _init_eidolons(self, level: int) -> None:
        for lv in range(1, level + 1):
            fn = DH_EIDOLONS.get(lv)
            if fn:
                for mod in fn(self):
                    self.stats.add_modifier(mod)

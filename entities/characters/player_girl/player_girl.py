"""PlayerGirl — 毁灭·物理属性角色 (lv80 满破数据, from 8002_playergirl.json)."""

from __future__ import annotations

from core.enums import ElementType, PathType, StatType, ActionType
from core.entity_stats import stats_defaults
from entities.characters.template_character.template_character import TemplateCharacter
from entities.characters.player_girl.skills import (
    PlayerGirlBasicAttack,
    PlayerGirlSkill,
    PlayerGirlUltimate,
    PlayerGirlTalent,
    PlayerGirlTechnique,
)
from entities.characters.player_girl.traces import TRACE_REGISTRY as PG_TRACES
from entities.characters.player_girl.eidolons import EIDOLON_REGISTRY as PG_EIDOLONS


class PlayerGirl(TemplateCharacter):
    _default_id = "PlayerGirl"
    _default_level = 80
    _default_element = ElementType.PHYSICAL
    _default_path = PathType.DESTRUCTION

    _energy_map = {
        ActionType.ULTIMATE: 0.0,
        ActionType.ENHANCED_BASIC: 5.0,
    }

    _base_stats = {
        **stats_defaults(),
        StatType.HP: 638.352,
        StatType.ATK: 329.472,
        StatType.DEF: 244.53,
        StatType.SPD: 100.0,
        StatType.CRIT_RATE: 0.05,
        StatType.CRIT_DMG: 0.50,
        StatType.ERR: 1.0,
        StatType.MAX_ENERGY: 120.0,
        StatType.AGGRO_MODIFIER: 0.25,
    }

    def __init__(self, character_id="", level=None, unlocked_traces=None, eidolon_level=0):
        self._talent_stacks: int = 0
        self._has_a2_energy: bool = False
        self._has_tenacity: bool = False
        self._has_fighting_spirit: bool = False
        self._has_e1: bool = False
        self._e1_triggered_this_attack: bool = False
        self._has_e2: bool = False
        self._has_e4: bool = False
        self._has_e6: bool = False
        self._killing_action: str = ""

        super().__init__(character_id, level, unlocked_traces, eidolon_level)

    def _init_skills(self) -> None:
        self._skills["basic"] = PlayerGirlBasicAttack(self)
        self._skills["skill"] = PlayerGirlSkill(self)
        self._skills["ultimate"] = PlayerGirlUltimate(self)
        self._skills["talent"] = PlayerGirlTalent(self)
        self._skills["technique"] = PlayerGirlTechnique(self)

    def _init_traces(self, unlocked: list[str]) -> None:
        self._has_a2_energy = "A2Energy" in unlocked
        self._has_tenacity = "Tenacity" in unlocked
        self._has_fighting_spirit = "FightingSpirit" in unlocked
        for key in unlocked:
            fn = PG_TRACES.get(key)
            if fn:
                for mod in fn(self):
                    self.stats.add_modifier(mod)

    def _init_eidolons(self, level: int) -> None:
        for lv in range(1, level + 1):
            fn = PG_EIDOLONS.get(lv)
            if fn:
                for mod in fn(self):
                    self.stats.add_modifier(mod)

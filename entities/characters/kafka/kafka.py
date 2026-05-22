from __future__ import annotations
"""Kafka — 虚无·雷属性角色 (lv80 满破数据, from 1005_kafka.json, Enhanced 11005xx)."""

from core.enums import ElementType, PathType, StatType, ActionType
from core.entity_stats import stats_defaults
from entities.characters.template_character.template_character import TemplateCharacter
from entities.characters.kafka.skills import (
    KafkaBasicAttack,
    KafkaSkill,
    KafkaUltimate,
    KafkaTalent,
    KafkaTechnique,
)
from entities.characters.kafka.traces import TRACE_REGISTRY as K_TRACES
from entities.characters.kafka.eidolons import EIDOLON_REGISTRY as K_EIDOLONS


class Kafka(TemplateCharacter):
    _default_id = "Kafka"
    _default_level = 80
    _default_element = ElementType.LIGHTNING
    _default_path = PathType.NIHILITY

    _toughness_map = {
        ActionType.FOLLOW_UP: 10.0,
    }

    _base_stats = {
        **stats_defaults(),
        StatType.HP: 576.576,
        StatType.ATK: 360.36,
        StatType.DEF: 257.4,
        StatType.SPD: 100.0,
        StatType.CRIT_RATE: 0.05,
        StatType.CRIT_DMG: 0.50,
        StatType.ERR: 1.0,
        StatType.MAX_ENERGY: 120.0,
        StatType.AGGRO_MODIFIER: 0.0,
    }

    def __init__(self, character_id="", level=None, unlocked_traces=None, eidolon_level=0):
        self._talent_count: int = 2
        self._talent_max: int = 2

        self._has_torture: bool = False
        self._has_plunder: bool = False
        self._has_thorn: bool = False

        self._has_e1: bool = False
        self._has_e2: bool = False
        self._has_e4: bool = False
        self._has_e6: bool = False

        super().__init__(character_id, level, unlocked_traces, eidolon_level)

    def _init_skills(self) -> None:
        self._skills["basic"] = KafkaBasicAttack(self)
        self._skills["skill"] = KafkaSkill(self)
        self._skills["ultimate"] = KafkaUltimate(self)
        self._skills["talent"] = KafkaTalent(self)
        self._skills["technique"] = KafkaTechnique(self)

    def _init_traces(self, unlocked: list[str]) -> None:
        self._has_torture = "Torture" in unlocked
        self._has_plunder = "Plunder" in unlocked
        self._has_thorn = "Thorn" in unlocked
        for key in unlocked:
            fn = K_TRACES.get(key)
            if fn:
                for mod in fn(self):
                    self.stats.add_modifier(mod)

    def _init_eidolons(self, level: int) -> None:
        for lv in range(1, level + 1):
            fn = K_EIDOLONS.get(lv)
            if fn:
                for mod in fn(self):
                    self.stats.add_modifier(mod)

from __future__ import annotations
"""EnemyConfig — 数据驱动怪物配置。子类覆盖 _CONFIG 或 __init__ 传参。"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from entities.enemies.enemy_skill import EnemySkill
from entities.enemies.enemy_ai import EnemyAI, SimpleAI, PriorityAI, PriorityRule, SequenceAI


@dataclass
class EnemyConfig:
    name: str = ""
    element: "ElementType | None" = None
    level_stats: dict = field(default_factory=dict)
    weaknesses: list["ElementType"] = field(default_factory=list)
    max_toughness: float = 0.0
    skills: list[EnemySkill] = field(default_factory=list)
    base_res: float = 0.20
    max_energy: float | None = None
    ai: EnemyAI = field(default_factory=SimpleAI)
    attack_element: "ElementType | None" = None
    crit_rate: float = 0.0
    crit_dmg: float = 0.20
    hit_energy_bucket: float = 10.0
    damage_type_resistance: dict[str, float] = field(default_factory=dict)
    deathrattle: dict | None = None

    _LEVEL_STAT_MAP: dict[str, str] = field(
        default_factory=lambda: {
            "hp": "HP", "atk": "ATK", "def": "DEF",
            "spd": "SPD", "ehr": "EFFECT_HIT_RATE", "eres": "EFFECT_RES",
        },
        init=False,
    )


def _parse_effects(raw_effects: list[dict]) -> list["SkillEffect"]:
    """将 JSON effects 中的 type 字符串转换为对应的 SkillEffect 子类实例。"""
    # 延迟导入避免循环依赖
    from core.enums import StatType, StatModifierType, ElementType
    from entities.enemies.enemy_skill import (
        DamageEffect, DebuffEffect, DoTEffect,
        BuffEffect, HealEffect, ShieldEffect, SummonEffect, DispelEffect,
        SelfDestructEffect, MarkEffect, DeathrattleEffect, ActionDelayEffect, SkillEffect,
    )
    _CLASSES = {
        "damage": DamageEffect, "debuff": DebuffEffect, "dot": DoTEffect,
        "buff": BuffEffect, "heal": HealEffect, "shield": ShieldEffect,
        "summon": SummonEffect, "dispel": DispelEffect,
        "self_destruct": SelfDestructEffect,
        "mark": MarkEffect,
        "deathrattle": DeathrattleEffect,
        "action_delay": ActionDelayEffect,
    }
    _ENUM_FIELDS = {
        "stat_type": lambda v: StatType[v.upper()],
        "modifier_type": lambda v: StatModifierType[v.upper()],
        "element": lambda v: ElementType[v.upper()],
    }
    result: list[SkillEffect] = []
    for eff in raw_effects:
        eff_type = eff.get("type", "").lower()
        cls = _CLASSES.get(eff_type)
        if cls is not None:
            d = {}
            for k, v in eff.items():
                if k == "type":
                    continue
                if k in _ENUM_FIELDS and isinstance(v, str):
                    d[k] = _ENUM_FIELDS[k](v)
                else:
                    d[k] = v
            result.append(cls(**d))
    return result


def load_config_from_json(folder: str | Path) -> EnemyConfig:
    """从 data.json 加载 EnemyConfig。自动转换枚举字符串为 Enum 值。

    用法:
        _HERE = Path(__file__).parent
        config = load_config_from_json(_HERE)
    """
    from starrail_combat import ElementType

    fpath = Path(folder) / "data.json"
    raw = json.loads(fpath.read_text(encoding="utf-8"))

    def _elem(name: str) -> ElementType:
        return ElementType[name.upper()]

    element = _elem(raw["element"]) if "element" in raw else None
    weaknesses = [_elem(w) for w in raw.get("weaknesses", [])]

    skills = []
    for sd in raw.get("skills", []):
        sd = dict(sd)
        sd["element"] = _elem(sd["element"])
        sd["effects"] = _parse_effects(sd.get("effects", []))
        skills.append(EnemySkill(**sd))

    ai: EnemyAI
    ai_cfg = raw.get("ai", {})
    if ai_cfg.get("type") == "priority":
        rules = [PriorityRule(r["condition"], r["skill_id"], r.get("params", {}))
                  for r in ai_cfg.get("rules", [])]
        p_ai = PriorityAI()
        p_ai._rules = rules
        ai = p_ai
    elif ai_cfg.get("type") == "sequence":
        s_ai = SequenceAI()
        s_ai._sequence = list(ai_cfg.get("sequence", []))
        ai = s_ai
    else:
        ai = SimpleAI()

    level_stats = {int(k): v for k, v in raw.get("level_stats", {}).items()}

    damage_type_resistance = raw.get("damage_type_resistance", {})

    return EnemyConfig(
        name=raw.get("name", ""),
        element=element,
        level_stats=level_stats,
        weaknesses=weaknesses,
        max_toughness=raw.get("max_toughness", 0.0),
        skills=skills,
        base_res=raw.get("base_res", 0.20),
        max_energy=raw.get("max_energy"),
        ai=ai,
        attack_element=(
            _elem(raw["attack_element"]) if raw.get("attack_element") else None
        ),
        crit_rate=raw.get("crit_rate", 0.0),
        crit_dmg=raw.get("crit_dmg", 0.20),
        hit_energy_bucket=raw.get("hit_energy_bucket", 10.0),
        damage_type_resistance=damage_type_resistance,
        deathrattle=raw.get("deathrattle"),
    )

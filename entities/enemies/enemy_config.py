from __future__ import annotations
"""EnemyConfig — 数据驱动怪物配置。子类覆盖 _CONFIG 或 __init__ 传参。"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from entities.enemies.enemy_skill import EnemySkill
from entities.enemies.enemy_ai import EnemyAI, SimpleAI, PriorityAI, PriorityRule


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

    _LEVEL_STAT_MAP: dict[str, str] = field(
        default_factory=lambda: {
            "hp": "HP", "atk": "ATK", "def": "DEF",
            "spd": "SPD", "ehr": "EFFECT_HIT_RATE", "eres": "EFFECT_RES",
        },
        init=False,
    )


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
        skills.append(EnemySkill(**sd))

    ai: EnemyAI
    ai_cfg = raw.get("ai", {})
    if ai_cfg.get("type") == "priority":
        rules = [PriorityRule(r["condition"], r["skill_id"], r.get("params", {}))
                  for r in ai_cfg.get("rules", [])]
        p_ai = PriorityAI()
        p_ai._rules = rules
        ai = p_ai
    else:
        ai = SimpleAI()

    level_stats = {int(k): v for k, v in raw.get("level_stats", {}).items()}

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
    )

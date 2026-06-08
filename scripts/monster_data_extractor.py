from __future__ import annotations
"""MonsterDataExtractor — 从原始游戏数据提取怪物完整配置，生成 data.json。

用法:
    python scripts/monster_data_extractor.py --monster-id 1002011 --output entities/enemies/antibaryon/data.json
    python scripts/monster_data_extractor.py --monster-id 1002011 --level 80 --print
    python scripts/monster_data_extractor.py --list-templates  # 列出所有 MonsterTemplateID

数据源:
    combat_base = "original_data/turnbasedgamedata_combat/ExcelOutput"
    main_base   = "original_data/turnbasedgamedata-main/ExcelOutput"
    ability_base = "original_data/turnbasedgamedata_combat/Config/ConfigAbility/Monster"
"""

import json
import re
from pathlib import Path
from typing import Optional

# ── 元素名映射：游戏 DamageType 字符串 → data.json 元素名 ──
_DAMAGE_TYPE_TO_ELEMENT: dict[str, str] = {
    "Physical": "Physical", "Fire": "Fire", "Ice": "Ice",
    "Thunder": "Lightning", "Wind": "Wind",
    "Quantum": "Quantum", "Imaginary": "Imaginary",
}

# ── 弱点名映射：游戏中 StanceWeakList 字符串 → data.json 元素名 ──
_STANCE_TO_ELEMENT: dict[str, str] = {
    "Physical": "Physical", "Fire": "Fire", "Ice": "Ice",
    "Thunder": "Lightning", "Wind": "Wind",
    "Quantum": "Quantum", "Imaginary": "Imaginary",
}

# ── 标准等级节点 (data.json level_stats 的 key) ──
_STANDARD_LEVELS = [1, 10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 100, 120]

# ── Ability TargetType → targeting 映射 ──
_TARGET_TYPE_MAP: dict[str, str] = {
    "SkillTargetEntityList": "single",
    "InherentTargetEntity": "single",  # 自身也算 single（需要目标选择但通常指自己）
    "TeamFormation": "aoe",
    "CustomTarget": "single",
}

# ── SkillTriggerKey → targeting 启发式 (当 Ability 不可用时 fallback) ──
_SKILL_KEY_TARGETING_HEURISTICS: dict[str, str] = {
    "SkillP01": "aoe",   # 被动/特殊技能通常是 AoE
    "SkillP02": "aoe",
    "SkillP03": "aoe",
}

# ── 怪物名中英文映射 (从 Rank 推断) ──
_RANKS = {
    "Minion": "Minion", "MinionLv2": "Minion",
    "Elite": "Elite", "LittleBoss": "Boss",
    "BigBoss": "Boss",
}

# ── TemplateID → 显示名映射 (手动维护) ──
_TEMPLATE_NAME_OVERRIDE: dict[int, str] = {
    8011010: "Baryon",
    8011020: "Antibaryon",
    1012010: "Automaton Hound",
    1012020: "Automaton Spider",
    1012030: "Automaton Beetle",
    1022010: "Everwinter Shadewalker",
    1022020: "Incineration Shadewalker",
    2002010: "Cloud Knights Patroller",
    2011010: "Entranced Dracolion",
    2011020: "Entranced Toad",
    2012010: "Entranced Dragonfish",
    2022020: "Internal Alchemist",
    8001010: "Flamespawn",
    8001020: "Frostspawn",
    8001030: "Mask of No Thought",
    8002010: "Imaginary Weaver",
    1002011: "Antibaryon (W1 Weapon)",
    1002012: "Baryon (W1 Weapon)",
}


class MonsterDataExtractor:
    """从原始 JSON 数据中提取怪物完整游戏数据。"""

    def __init__(
        self,
        combat_dir: str = "original_data/turnbasedgamedata_combat",
        main_dir: str = "original_data/turnbasedgamedata-main",
        name_override: dict[int, str] | None = None,
    ) -> None:
        self._combat_dir = Path(combat_dir)
        self._main_dir = Path(main_dir)
        self._name_override = {**_TEMPLATE_NAME_OVERRIDE, **(name_override or {})}

        # ── 查找表 ──
        self._hard_level: dict[tuple[int, int], dict] = {}   # (group, level) → ratios
        self._templates: dict[int, dict] = {}                 # template_id → template
        self._configs: dict[int, dict] = {}                   # monster_id → config
        self._skills: dict[int, dict] = {}                    # skill_id → skill
        self._targeting: dict[str, str] = {}                  # "{template_name}_{skill_key}" → targeting

    # ================================================================
    #  加载
    # ================================================================

    def load_all(self) -> None:
        """一次性加载所有数据源。"""
        self._load_hard_level_group()
        self._load_templates()
        self._load_configs()
        self._load_skills()
        self._load_ability_targeting()

    def _load_hard_level_group(self) -> None:
        fpath = self._main_dir / "ExcelOutput" / "HardLevelGroup.json"
        raw = _read_json(fpath)
        for entry in raw:
            group = int(entry["HardLevelGroup"])
            level = int(entry["Level"])
            self._hard_level[(group, level)] = entry

    def _load_templates(self) -> None:
        fpath = self._combat_dir / "ExcelOutput" / "MonsterTemplateConfig.json"
        raw = _read_json(fpath)
        for entry in raw:
            self._templates[int(entry["MonsterTemplateID"])] = entry

    def _load_configs(self) -> None:
        fpath = self._combat_dir / "ExcelOutput" / "MonsterConfig.json"
        raw = _read_json(fpath)
        for entry in raw:
            self._configs[int(entry["MonsterID"])] = entry

    def _load_skills(self) -> None:
        # MonsterSkillConfig
        fpath = self._combat_dir / "ExcelOutput" / "MonsterSkillConfig.json"
        raw = _read_json(fpath)
        for entry in raw:
            self._skills[int(entry["SkillID"])] = entry
        # MonsterSkillUniqueConfig
        fpath = self._combat_dir / "ExcelOutput" / "MonsterSkillUniqueConfig.json"
        raw = _read_json(fpath)
        for entry in raw:
            self._skills[int(entry["SkillID"])] = entry

    def _load_ability_targeting(self) -> None:
        """扫描 ConfigAbility/Monster/*.json，提取 TemplateName + SkillKey → targeting。

        从 AbilityList[].Name 中提取模板前缀和 SkillKey (如 Skill04)，
        从 TargetInfo.TargetType 推断 targeting 类型。
        """
        ability_dir = self._combat_dir / "Config" / "ConfigAbility" / "Monster"
        if not ability_dir.exists():
            return

        for fpath in sorted(ability_dir.glob("*.json")):
            # 跳过 Camera 目录和 .layout 文件
            if "Camera" in fpath.name or ".layout" in fpath.name:
                continue
            raw = _read_json_safe(fpath)
            if not raw:
                continue
            abilities = raw.get("AbilityList") or []
            for ability in abilities:
                name = ability.get("Name", "")
                if not name:
                    continue
                # 提取 SkillKey (Skill04, SkillP01, etc.)
                m = re.search(r"(Skill\d+|SkillP\d+|SkillEX\d+)", name)
                if not m:
                    continue
                skill_key = m.group(1)
                # 提取模板前缀 (去掉 _SkillXX_PhaseXX 后面的部分)
                # 例如 Monster_W1_Colossus_00_Skill01_Phase01 → Monster_W1_Colossus_00
                prefix = re.sub(r"_Skill\d+.*", "", name)
                prefix = re.sub(r"_SkillP\d+.*", "", prefix)
                prefix = re.sub(r"_SkillEX\d+.*", "", prefix)
                prefix = re.sub(r"_Phase\d+$", "", prefix)

                target_info = ability.get("TargetInfo") or {}
                raw_target = target_info.get("TargetType", "")
                targeting = _TARGET_TYPE_MAP.get(raw_target, "single")
                key = f"{prefix}:{skill_key}"
                self._targeting[key] = targeting

    # ================================================================
    #  查询
    # ================================================================

    def get_level_ratio(self, group: int, level: int) -> dict:
        """获取指定组和等级的倍率。不存在时用最近等级插值。"""
        key = (group, level)
        if key in self._hard_level:
            return _ratio_to_dict(self._hard_level[key])
        # 查找最近的两个键做线性插值
        entries = sorted(
            [(l, r) for (g, l), r in self._hard_level.items() if g == group],
            key=lambda x: x[0],
        )
        if not entries:
            return {}
        if level <= entries[0][0]:
            return _ratio_to_dict(entries[0][1])
        if level >= entries[-1][0]:
            return _ratio_to_dict(entries[-1][1])
        for i in range(len(entries) - 1):
            lo_lv, lo_r = entries[i]
            hi_lv, hi_r = entries[i + 1]
            if lo_lv <= level <= hi_lv:
                ratio = (level - lo_lv) / (hi_lv - lo_lv)
                lo_d = _ratio_to_dict(lo_r)
                hi_d = _ratio_to_dict(hi_r)
                return {
                    k: lo_d[k] + (hi_d[k] - lo_d[k]) * ratio
                    for k in lo_d if k in hi_d
                }
        return _ratio_to_dict(entries[-1][1])

    def get_skill_data(self, skill_id: int) -> Optional[dict]:
        return self._skills.get(skill_id)

    def get_template(self, template_id: int) -> Optional[dict]:
        return self._templates.get(template_id)

    def get_config(self, monster_id: int) -> Optional[dict]:
        return self._configs.get(monster_id)

    def get_targeting(self, template_id: int, skill_key: str) -> str:
        """从 Ability 解析结果中获取 skill 的 targeting。

        Args:
            template_id: MonsterTemplateID
            skill_key: SkillTriggerKey (如 Skill04, SkillP01)
        Returns:
            targeting string: "single" | "aoe" | "random" | "self"
        """
        # 1. 精确匹配: template_name:skill_key
        template = self._templates.get(template_id)
        json_config = ""
        if template:
            json_config = template.get("JsonConfig", "")
        # 从 JsonConfig 提取名称前缀 (如 "Monster_W1_CocoliaP1_01_Config" → "Monster_W1_CocoliaP1_01")
        cfg_name = Path(json_config).stem.replace("_Config", "") if json_config else ""

        for prefix_key, target in self._targeting.items():
            prefix, key = prefix_key.rsplit(":", 1)
            if key == skill_key and prefix in cfg_name:
                return target

        # 2. 启发式 fallback
        return _SKILL_KEY_TARGETING_HEURISTICS.get(skill_key, "single")

    # ================================================================
    #  核心: 生成 data.json
    # ================================================================

    def generate_enemy_data(self, monster_id: int) -> dict:
        """根据 MonsterID 生成完整的 data.json 字典。"""
        cfg = self._configs.get(monster_id)
        if cfg is None:
            raise KeyError(f"MonsterID {monster_id} not found in MonsterConfig")

        template_id = int(cfg.get("MonsterTemplateID", 0))
        template = self._templates.get(template_id)
        if template is None:
            raise KeyError(f"MonsterTemplateID {template_id} not found")

        hard_group = cfg.get("HardLevelGroup", 1)

        # ── 基础信息 ──
        name = self._infer_name(template_id, template, cfg)
        rank = template.get("Rank", "")

        # ── 弱点 ──
        stance_weak = cfg.get("StanceWeakList") or []
        weaknesses = [
            _STANCE_TO_ELEMENT.get(w, w) for w in stance_weak
            if w in _STANCE_TO_ELEMENT
        ]

        # ── 面板: level_stats ──
        template_bases = {
            "hp": _val(template.get("HPBase")),
            "atk": _val(template.get("AttackBase")),
            "def": _val(template.get("DefenceBase")),
            "spd": _val(template.get("SpeedBase")),
        }
        stance_base = _val(template.get("StanceBase"))
        config_mods = {
            "hp": _val(cfg.get("HPModifyRatio")),
            "atk": _val(cfg.get("AttackModifyRatio")),
            "def": _val(cfg.get("DefenceModifyRatio")),
            "spd": _val(cfg.get("SpeedModifyRatio")),
            "stance": _val(cfg.get("StanceModifyRatio")),
        }

        level_stats: dict[str, dict] = {}
        for lv in _STANDARD_LEVELS:
            ratio = self.get_level_ratio(hard_group, lv)
            eh_base = ratio.get("ehr", 0.0)
            eres_base = ratio.get("eres", 0.0)
            stats = {
                "hp": round(template_bases["hp"] * ratio.get("hp", 1.0) * config_mods["hp"]),
                "atk": round(template_bases["atk"] * ratio.get("atk", 1.0) * config_mods["atk"]),
                "def": round(template_bases["def"] * ratio.get("def", 1.0) * config_mods["def"]),
                "spd": round(template_bases["spd"] * ratio.get("spd", 1.0) * config_mods["spd"], 2),
                "ehr": round(eh_base, 2),
                "eres": round(eres_base, 2),
            }
            level_stats[str(lv)] = stats

        # ── 韧性 ──
        lv95_ratio = self.get_level_ratio(hard_group, 95)
        max_toughness = round(
            stance_base * lv95_ratio.get("stance", 1.0) * config_mods.get("stance", 1.0),
            1,
        )

        # ── 暴击 ──
        crit_dmg = _val(template.get("CriticalDamageBase"), 0.20)
        crit_rate = 0.0

        # ── 抗性 ──
        damage_resistances = cfg.get("DamageTypeResistance") or []
        base_res = 0.20
        damage_type_resistance: dict[str, float] = {}
        for r in damage_resistances:
            dt = r.get("DamageType", "")
            val = r.get("Value", {}).get("Value", 0.0)
            elem_name = _DAMAGE_TYPE_TO_ELEMENT.get(dt, dt)
            damage_type_resistance[elem_name] = round(val, 2)
        if damage_type_resistance:
            res_values = list(damage_type_resistance.values())
            base_res = round(max(res_values) if len(set(res_values)) > 1
                             else res_values[0], 2)

        # ── 技能列表 ──
        skill_ids = cfg.get("SkillList") or []
        skills = []
        primary_element = None
        for sid in skill_ids:
            sdata = self._skills.get(int(sid))
            if sdata is None:
                continue
            skill_entry = self._build_skill_entry(sid, sdata, template_id)
            if skill_entry:
                skills.append(skill_entry)
                if primary_element is None and skill_entry.get("element"):
                    primary_element = skill_entry["element"]

        # ── 元素类型 (取第一个技能的 DamageType) ──
        element = primary_element or "Physical"

        # ── AI ──
        ai_seq = template.get("AISkillSequence") or []
        ai_cfg = self._build_ai(template, ai_seq)

        # ── 受击回能 ──
        hit_energy_bucket = 10.0

        return {
            "name": name,
            "element": element,
            "weaknesses": weaknesses,
            "max_toughness": max_toughness,
            "base_res": base_res,
            "crit_rate": crit_rate,
            "crit_dmg": crit_dmg,
            "hit_energy_bucket": hit_energy_bucket,
            "level_stats": level_stats,
            "skills": skills,
            "ai": ai_cfg,
            "damage_type_resistance": damage_type_resistance,
        }

    def _infer_name(self, template_id: int, template: dict, cfg: dict) -> str:
        """从模板名推断显示名。优先使用 name_override。"""
        # 1. 用户手动指定的名字
        if template_id in self._name_override:
            return self._name_override[template_id]

        # 2. 尝试从 PrefabPath 提取英文名
        prefab = template.get("PrefabPath", "")
        if prefab:
            parts = prefab.replace(".prefab", "").split("/")
            name_part = parts[-1] if parts else ""
            if "Monster_" in name_part:
                name_part = name_part.replace("Monster_", "")
            readable = re.sub(r"_\d+$", "", name_part)
            readable = readable.replace("_", " ")
            readable = re.sub(r"(\d+)", r" \1", readable).strip()
            if readable:
                return readable

        # 3. fallback: template ID
        return f"Monster_{template_id}"

    def _build_skill_entry(self, sid: int, sdata: dict, template_id: int) -> Optional[dict]:
        """将 MonsterSkillConfig 条目转换为 data.json skill 格式。"""
        trigger_key = sdata.get("SkillTriggerKey", "")
        damage_type = sdata.get("DamageType") or ""
        element = _DAMAGE_TYPE_TO_ELEMENT.get(damage_type, "Physical")

        # 倍率: ParamList[0].Value
        params = sdata.get("ParamList") or []
        multiplier = _val(params[0]) if len(params) > 0 else 1.0

        # 冷却
        ai_cd = sdata.get("AI_CD") or 0

        # SP Hit → energy gain (近似)
        sp_hit = _val(sdata.get("SPHitBase"), 10.0)

        # targeting
        targeting = self.get_targeting(template_id, trigger_key)

        # 是否是威胁技能
        is_threat = sdata.get("IsThreat", False)

        # 技能名
        skill_name = trigger_key or f"Skill_{sid}"

        entry: dict = {
            "skill_id": f"skill_{sid}",
            "name": skill_name,
            "multiplier": round(multiplier, 2),
            "element": element,
            "targeting": targeting,
            "cooldown": ai_cd,
            "energy_gain": round(sp_hit, 1),
        }

        # 额外效果 (从 ModifierList / ExtraEffectIDList)
        effects = self._parse_effects(sdata, is_threat)
        if effects:
            entry["effects"] = effects

        return entry

    def _parse_effects(self, sdata: dict, is_threat: bool) -> list[dict]:
        """从技能数据中解析附加效果。目前主要识别 Debuff/Buff 标记。"""
        effects: list[dict] = []
        modifier_list = sdata.get("ModifierList") or []

        # 简单标记: 有多余参数可能代表 debuff
        params = sdata.get("ParamList") or []
        num_params = len(params)

        # 如果 IsThreat=true 且有多个参数，标记为威胁技能效果
        if is_threat and num_params >= 2:
            # 第二个参数通常是某种概率/强度
            effects.append({
                "type": "debuff",
                "stat_type": "DEF",
                "modifier_type": "PERCENT",
                "value": -round(_val(params[1]) * 100 if _val(params[1]) < 1 else _val(params[1]), 1),
                "base_chance": 1.0,
                "duration": 2,
            })

        return effects

    def _build_ai(self, template: dict, ai_sequence: list[dict]) -> dict:
        """构建 AI 配置。

        如果 AISkillSequence 有多个条目，使用 SequenceAI；
        否则用 SimpleAI。
        """
        sequence = [int(e.get("MNAHFIGOHML", 0)) for e in ai_sequence]
        sequence = [s for s in sequence if s > 0]

        if len(sequence) <= 1:
            return {"type": "simple"}

        # 多技能序列 → SequenceAI
        return {
            "type": "sequence",
            "sequence": [f"skill_{s}" for s in sequence],
        }


# ================================================================
#  辅助函数
# ================================================================

def _read_json(fpath: Path) -> list:
    if not fpath.exists():
        raise FileNotFoundError(str(fpath))
    with open(fpath, encoding="utf-8") as f:
        return json.load(f)


def _read_json_safe(fpath: Path) -> Optional[dict]:
    try:
        with open(fpath, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return None


def _val(field, default: float = 1.0) -> float:
    """提取 {Value: number} 结构中的数值。"""
    if field is None:
        return default
    if isinstance(field, (int, float)):
        return float(field)
    if isinstance(field, dict):
        return float(field.get("Value", default))
    return default


def _ratio_to_dict(entry: dict) -> dict:
    """将 HardLevelGroup 条目转换为扁平的 ratio dict。"""
    d = {
        "hp": _val(entry.get("HPRatio"), 1.0),
        "atk": _val(entry.get("AttackRatio"), 1.0),
        "def": _val(entry.get("DefenceRatio"), 1.0),
        "spd": _val(entry.get("SpeedRatio"), 1.0),
        "stance": _val(entry.get("StanceRatio"), 1.0),
        "ehr": _val(entry.get("StatusProbability"), 0.0),
        "eres": _val(entry.get("StatusResistance"), 0.0),
    }
    return d


# ================================================================
#  CLI
# ================================================================

if __name__ == "__main__":
    import sys

    extractor = MonsterDataExtractor()
    extractor.load_all()

    # 解析命令行
    args = sys.argv[1:]
    monster_id_arg = None
    output_path = None
    level = 95
    list_templates = False
    print_mode = False

    i = 0
    while i < len(args):
        if args[i] == "--monster-id" and i + 1 < len(args):
            monster_id_arg = args[i + 1]
            i += 2
        elif args[i] == "--output" and i + 1 < len(args):
            output_path = args[i + 1]
            i += 2
        elif args[i] == "--level" and i + 1 < len(args):
            level = int(args[i + 1])
            i += 2
        elif args[i] == "--list-templates":
            list_templates = True
            i += 1
        elif args[i] == "--print":
            print_mode = True
            i += 1
        else:
            i += 1

    if list_templates:
        for tid in sorted(extractor._templates.keys()):
            t = extractor._templates[tid]
            name = extractor._infer_name(tid, t, {})
            print(f"  {tid:>7}  {t.get('Rank', '?'):12}  {name}")
        sys.exit(0)

    if monster_id_arg is None:
        print("Usage: python scripts/monster_data_extractor.py --monster-id <ID> [--output <path>] [--print]")
        print("       python scripts/monster_data_extractor.py --list-templates")
        sys.exit(1)

    mid = int(monster_id_arg)
    data = extractor.generate_enemy_data(mid)
    json_str = json.dumps(data, indent=2, ensure_ascii=False)

    if print_mode:
        print(json_str)
        print(f"\n  [Level {level}: HP={data['level_stats'][str(level)]['hp']}, ATK={data['level_stats'][str(level)]['atk']}]")
    elif output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(json_str + "\n", encoding="utf-8")
        print(f"  Written to {output_path}")
    else:
        print(json_str)

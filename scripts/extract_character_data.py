#!/usr/bin/env python3
"""Extract per-character consolidated data from StarRailRes raw JSON files.

Reads the 6 character-related JSON files from original_data/StarRailRes/index_new/cn/
and produces one JSON per character in character_data/ with all stats and mechanics.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
SOURCE_DIR = ROOT.parent / "original_data" / "StarRailRes" / "index_new" / "cn"
OUTPUT_DIR = ROOT.parent / "character_data"


def load_json(filename: str) -> dict[str, Any]:
    path = SOURCE_DIR / filename
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_path_map(paths: dict[str, Any]) -> dict[str, dict[str, str]]:
    """Map internal path key → {en, zh}."""
    mapping: dict[str, dict[str, str]] = {}
    for key, val in paths.items():
        mapping[key] = {
            "en": val.get("text", key),
            "zh": val.get("name", key),
        }
    return mapping


def build_element_map(elements: dict[str, Any]) -> dict[str, str]:
    """Map element key → Chinese name."""
    return {k: v["name"] for k, v in elements.items()}


def build_property_map(properties: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Map property type → {name, ...}."""
    return {k: v for k, v in properties.items()}


def classify_skill_tree_node(node: dict[str, Any]) -> str:
    """Classify a skill tree node into one of three categories."""
    if node.get("level_up_skills"):
        return "skill_upgrade"
    if node.get("desc"):
        return "ability_bonus"
    return "stat_bonus"


def extract_promotions(
    promotions: dict[str, Any], character_id: str
) -> dict[str, Any] | None:
    """Extract promotion (ascension) data for a character."""
    entry = promotions.get(character_id)
    if not entry:
        return None
    values = []
    for v in entry.get("values", []):
        values.append({
            "hp": v.get("hp", {}).get("base", 0),
            "hp_step": v.get("hp", {}).get("step", 0),
            "atk": v.get("atk", {}).get("base", 0),
            "atk_step": v.get("atk", {}).get("step", 0),
            "def_": v.get("def", {}).get("base", 0),
            "def_step": v.get("def", {}).get("step", 0),
            "spd": v.get("spd", {}).get("base", 0),
            "spd_step": v.get("spd", {}).get("step", 0),
            "taunt": v.get("taunt", {}).get("base", 0),
            "taunt_step": v.get("taunt", {}).get("step", 0),
            "crit_rate": v.get("crit_rate", {}).get("base", 0),
            "crit_rate_step": v.get("crit_rate", {}).get("step", 0),
            "crit_dmg": v.get("crit_dmg", {}).get("base", 0),
            "crit_dmg_step": v.get("crit_dmg", {}).get("step", 0),
        })
    return {
        "levels": values,
        "materials": entry.get("materials", []),
    }


def extract_skills(
    skills_db: dict[str, Any], skill_ids: list[str]
) -> list[dict[str, Any]]:
    """Extract skill definitions for a list of skill IDs."""
    result: list[dict[str, Any]] = []
    for sid in skill_ids:
        entry = skills_db.get(sid)
        if not entry:
            print(f"  [WARNING] Skill {sid} not found in character_skills.json")
            continue
        result.append({
            "id": entry.get("id", ""),
            "name": entry.get("name", ""),
            "type": entry.get("type", ""),
            "type_text": entry.get("type_text", ""),
            "effect": entry.get("effect", ""),
            "effect_text": entry.get("effect_text", ""),
            "max_level": entry.get("max_level", 1),
            "element": entry.get("element", None),
            "params": entry.get("params", []),
            "desc": entry.get("desc", ""),
        })
    return result


def extract_traces(
    skill_trees_db: dict[str, Any],
    tree_ids: list[str],
    property_map: dict[str, dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Extract trace tree data, classified by node type."""
    skill_upgrades: list[dict[str, Any]] = []
    ability_bonuses: list[dict[str, Any]] = []
    stat_bonuses: list[dict[str, Any]] = []

    for tid in tree_ids:
        node = skill_trees_db.get(tid)
        if not node:
            print(f"  [WARNING] Skill tree node {tid} not found in character_skill_trees.json")
            continue

        category = classify_skill_tree_node(node)

        if category == "skill_upgrade":
            skill_upgrades.append({
                "id": node.get("id", ""),
                "name": node.get("name", ""),
                "desc": node.get("desc", ""),
                "anchor": node.get("anchor", ""),
                "pre_points": node.get("pre_points", []),
                "level_up_skills": node.get("level_up_skills", []),
                "levels": node.get("levels", []),
            })
        elif category == "ability_bonus":
            ability_bonuses.append({
                "id": node.get("id", ""),
                "name": node.get("name", ""),
                "desc": node.get("desc", ""),
                "anchor": node.get("anchor", ""),
                "pre_points": node.get("pre_points", []),
                "max_level": node.get("max_level", 1),
                "levels": node.get("levels", []),
                "params": node.get("params", []),
            })
        else:
            props_simple: list[dict[str, Any]] = []
            for lvl in node.get("levels", []):
                for prop in lvl.get("properties", []):
                    ptype = prop.get("type", "")
                    pinfo = property_map.get(ptype, {})
                    pname = pinfo.get("name", ptype) if pinfo else ptype
                    props_simple.append({
                        "type": ptype,
                        "name": pname,
                        "value": prop.get("value", 0),
                    })
            stat_bonuses.append({
                "id": node.get("id", ""),
                "name": node.get("name", ""),
                "anchor": node.get("anchor", ""),
                "pre_points": node.get("pre_points", []),
                "properties": props_simple,
            })

    return {
        "skill_upgrades": skill_upgrades,
        "ability_bonuses": ability_bonuses,
        "stat_bonuses": stat_bonuses,
    }


def extract_eidolons(
    ranks_db: dict[str, Any], rank_ids: list[str]
) -> list[dict[str, Any]]:
    """Extract eidolon data."""
    result: list[dict[str, Any]] = []
    for rid in rank_ids:
        entry = ranks_db.get(rid)
        if not entry:
            print(f"  [WARNING] Rank {rid} not found in character_ranks.json")
            continue
        result.append({
            "id": entry.get("id", ""),
            "name": entry.get("name", ""),
            "rank": entry.get("rank", 0),
            "desc": entry.get("desc", ""),
            "level_up_skills": entry.get("level_up_skills", []),
            "max_level": entry.get("max_level", 1),
        })
    return result


def main() -> None:
    print("=" * 60)
    print("StarRailRes → character_data extractor")
    print("=" * 60)

    # Load source data
    print("\n[1/3] Loading source JSON files...")
    characters = load_json("characters.json")
    skills_db = load_json("character_skills.json")
    skill_trees_db = load_json("character_skill_trees.json")
    ranks_db = load_json("character_ranks.json")
    promotions = load_json("character_promotions.json")
    paths = load_json("paths.json")
    elements = load_json("elements.json")
    properties = load_json("properties.json")

    path_map = build_path_map(paths)
    element_map = build_element_map(elements)
    property_map = build_property_map(properties)

    print(f"  Characters: {len(characters)}")
    print(f"  Skills:     {len(skills_db)}")
    print(f"  Skill tree: {len(skill_trees_db)}")
    print(f"  Ranks:      {len(ranks_db)}")
    print(f"  Promotions: {len(promotions)}")

    # Prepare output
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    char_count = 0
    warn_count = 0
    index: dict[str, dict[str, Any]] = {}

    print(f"\n[2/3] Extracting per-character data...")
    for uid, char_data in characters.items():
        char_count += 1
        name = char_data["name"]
        tag = char_data.get("tag", uid)
        rarity = char_data.get("rarity", 0)
        path_key = char_data.get("path", "")
        element_key = char_data.get("element", "")
        max_sp = char_data.get("max_sp", None)
        skill_ids = char_data.get("skills", [])
        rank_ids = char_data.get("ranks", [])
        tree_ids = char_data.get("skill_trees", [])

        path_info = path_map.get(path_key, {"en": path_key, "zh": path_key})
        element_zh = element_map.get(element_key, element_key)

        # Build per-character data
        output: dict[str, Any] = {
            "id": uid,
            "name": name,
            "tag": tag,
            "rarity": rarity,
            "path": path_info["zh"],
            "path_key": path_key,
            "path_en": path_info["en"],
            "element": element_zh,
            "element_key": element_key,
            "max_sp": max_sp,
            "preview": char_data.get("preview", ""),
            "portrait": char_data.get("portrait", ""),
        }

        # Promotions
        output["promotions"] = extract_promotions(promotions, uid)

        # Skills
        output["skills"] = extract_skills(skills_db, skill_ids)

        # Traces
        output["traces"] = extract_traces(skill_trees_db, tree_ids, property_map)

        # Eidolons
        output["eidolons"] = extract_eidolons(ranks_db, rank_ids)

        # Write file
        filename = f"{uid}_{tag}.json"
        filepath = OUTPUT_DIR / filename
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        # Update index
        index[uid] = {
            "name": name,
            "tag": tag,
            "rarity": rarity,
            "path": path_info["zh"],
            "element": element_zh,
            "file": filename,
        }

        if char_count % 10 == 0:
            print(f"  ... {char_count}/{len(characters)} processed")

    # Write index
    index_path = OUTPUT_DIR / "_index.json"
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    print(f"\n[3/3] Done!")
    print(f"  Characters extracted: {char_count}")
    print(f"  Output directory:     {OUTPUT_DIR}")
    print(f"  Index file:           {index_path}")

    # Quick stats
    rarity_4 = sum(1 for v in index.values() if v["rarity"] == 4)
    rarity_5 = sum(1 for v in index.values() if v["rarity"] == 5)
    print(f"\n  Rarity breakdown: 4★={rarity_4}, 5★={rarity_5}, other={char_count - rarity_4 - rarity_5}")


if __name__ == "__main__":
    main()

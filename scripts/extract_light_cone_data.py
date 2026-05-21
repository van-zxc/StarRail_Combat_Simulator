#!/usr/bin/env python3
"""Extract per-light-cone consolidated data from StarRailRes raw JSON files.

Reads the 3 light-cone-related JSON files from original_data/StarRailRes/index_new/cn/
and produces one JSON per light cone in light_cone_data/.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = ROOT / "original_data" / "StarRailRes" / "index_new" / "cn"
OUTPUT_DIR = ROOT / "light_cone_data"


def load_json(filename: str) -> dict[str, Any]:
    path = SOURCE_DIR / filename
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_path_map(paths: dict[str, Any]) -> dict[str, dict[str, str]]:
    mapping: dict[str, dict[str, str]] = {}
    for key, val in paths.items():
        mapping[key] = {
            "en": val.get("text", key),
            "zh": val.get("name", key),
        }
    return mapping


def build_property_map(properties: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {k: v for k, v in properties.items()}


def extract_promotions(
    promotions: dict[str, Any], lc_id: str
) -> dict[str, Any] | None:
    entry = promotions.get(lc_id)
    if not entry:
        return None
    values: list[dict[str, float]] = []
    for v in entry.get("values", []):
        values.append({
            "hp_base": v.get("hp", {}).get("base", 0.0),
            "hp_step": v.get("hp", {}).get("step", 0.0),
            "atk_base": v.get("atk", {}).get("base", 0.0),
            "atk_step": v.get("atk", {}).get("step", 0.0),
            "def_base": v.get("def", {}).get("base", 0.0),
            "def_step": v.get("def", {}).get("step", 0.0),
        })
    return {
        "levels": values,
        "materials": entry.get("materials", []),
    }


def extract_ranks(
    ranks_db: dict[str, Any], lc_id: str
) -> dict[str, Any] | None:
    entry = ranks_db.get(lc_id)
    if not entry:
        return None
    return {
        "skill_name": entry.get("skill", ""),
        "skill_desc": entry.get("desc", ""),
        "params": entry.get("params", []),
        "properties": entry.get("properties", []),
    }


def slugify_zh(name: str) -> str:
    """Generate a simple ASCII tag from a Chinese name by removing non-ASCII."""
    tag = re.sub(r"[^\w]", "_", name.lower()).strip("_")
    tag = re.sub(r"_+", "_", tag)
    return tag or "unknown"


# Manual English name mappings for light cones we know.
# Populate more as needed; used for filename tag generation.
_NAME_EN_MAP: dict[str, str] = {
    "24001": "Cruising_in_the_Stellar_Sea",
}


def get_lc_tag(lc_id: str, name: str) -> str:
    """Return a readable English slug for the light cone."""
    if lc_id in _NAME_EN_MAP:
        return _NAME_EN_MAP[lc_id]
    return lc_id


def main() -> None:
    print("=" * 60)
    print("StarRailRes -> light_cone_data extractor")
    print("=" * 60)

    print("\n[1/3] Loading source JSON files...")
    light_cones = load_json("light_cones.json")
    promotions = load_json("light_cone_promotions.json")
    ranks_db = load_json("light_cone_ranks.json")
    paths = load_json("paths.json")
    properties = load_json("properties.json")

    path_map = build_path_map(paths)
    property_map = build_property_map(properties)

    print(f"  Light cones:     {len(light_cones)}")
    print(f"  Promotions:      {len(promotions)}")
    print(f"  Ranks:           {len(ranks_db)}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    lc_count = 0
    warn_count = 0
    index: dict[str, dict[str, Any]] = {}

    print(f"\n[2/3] Extracting per-light-cone data...")
    for lc_id, lc_data in light_cones.items():
        lc_count += 1
        name = lc_data.get("name", "")
        rarity = lc_data.get("rarity", 0)
        path_key = lc_data.get("path", "")

        path_info = path_map.get(path_key, {"en": path_key, "zh": path_key})

        tag = get_lc_tag(lc_id, name)

        output: dict[str, Any] = {
            "id": lc_id,
            "name": name,
            "tag": tag,
            "rarity": rarity,
            "path": path_info["zh"],
            "path_key": path_key,
            "path_en": path_info["en"],
            "icon": lc_data.get("icon", ""),
            "preview": lc_data.get("preview", ""),
            "portrait": lc_data.get("portrait", ""),
        }

        promotions_data = extract_promotions(promotions, lc_id)
        if promotions_data is None:
            print(f"  [WARNING] No promotion data for {lc_id} ({name})")
            warn_count += 1
        output["promotions"] = promotions_data

        ranks_data = extract_ranks(ranks_db, lc_id)
        if ranks_data is None:
            ranks_data = {}
        output["skill_name"] = ranks_data.get("skill_name", "")
        output["skill_desc"] = ranks_data.get("skill_desc", "")
        output["params"] = ranks_data.get("params", [])
        output["properties"] = ranks_data.get("properties", [])

        filename = f"{lc_id}.json"
        filepath = OUTPUT_DIR / filename
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        index[lc_id] = {
            "name": name,
            "tag": tag,
            "rarity": rarity,
            "path": path_info["zh"],
            "path_key": path_key,
            "file": filename,
        }

        if lc_count % 20 == 0:
            print(f"  ... {lc_count}/{len(light_cones)} processed")

    index_path = OUTPUT_DIR / "_index.json"
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    print(f"\n[3/3] Done!")
    print(f"  Light cones extracted: {lc_count}")
    print(f"  Warnings:              {warn_count}")
    print(f"  Output directory:      {OUTPUT_DIR}")
    print(f"  Index file:            {index_path}")

    rarity_3 = sum(1 for v in index.values() if v["rarity"] == 3)
    rarity_4 = sum(1 for v in index.values() if v["rarity"] == 4)
    rarity_5 = sum(1 for v in index.values() if v["rarity"] == 5)
    print(f"\n  Rarity: 3*={rarity_3}, 4*={rarity_4}, 5*={rarity_5}")


if __name__ == "__main__":
    main()

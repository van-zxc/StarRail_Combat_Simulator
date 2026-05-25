"""Build relic_data/ from StarRailRes JSON sources (5-star relics only)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
SRC = ROOT / "original_data" / "StarRailRes" / "index_new" / "cn"
OUT = ROOT / "relic_data"

SET_TYPE_MAP = {"HEAD": "HEAD", "HAND": "HANDS", "BODY": "BODY", "FOOT": "FEET", "NECK": "PLANAR_SPHERE", "OBJECT": "LINK_ROPE"}


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build():
    properties = load_json(SRC / "properties.json")
    relic_sets = load_json(SRC / "relic_sets.json")
    relics = load_json(SRC / "relics.json")
    main_affixes_all = load_json(SRC / "relic_main_affixes.json")
    sub_affixes_all = load_json(SRC / "relic_sub_affixes.json")

    def resolve_property(prop_type: str, value: float) -> dict:
        entry = properties.get(prop_type, {})
        return {
            "type": prop_type,
            "value": value,
            "field": entry.get("field", ""),
            "ratio": entry.get("ratio", False),
            "percent": entry.get("percent", False),
        }

    idx_entries: dict[str, dict] = {}

    for set_id_str, set_data in relic_sets.items():
        set_type = "cavern" if int(set_id_str) < 200 else "planar"

        effects: dict[str, list[dict]] = {}
        piece_count = 4 if set_type == "cavern" else 2
        if set_type == "cavern":
            effects["2"] = [resolve_property(p["type"], p["value"]) for p in set_data["properties"][0]]
            effects["4"] = [resolve_property(p["type"], p["value"]) for p in set_data["properties"][1]]
        else:
            face = set_data["properties"][0]
            effects["2"] = [resolve_property(p["type"], p["value"]) for p in face]

        pieces = []
        for relic_id, relic in relics.items():
            if relic.get("set_id") != set_id_str:
                continue
            if relic.get("rarity") != 5:
                continue
            pieces.append({
                "id": relic["id"],
                "name": relic["name"],
                "rarity": 5,
                "type": SET_TYPE_MAP.get(relic["type"], relic["type"]),
                "max_level": relic["max_level"],
                "main_affix_group": relic["main_affix_id"],
                "sub_affix_group": relic["sub_affix_id"],
            })

        used_affix_groups: set[str] = set()
        for p in pieces:
            used_affix_groups.add(p["main_affix_group"])

        main_affixes: dict[str, list[dict]] = {}
        for gid in sorted(used_affix_groups):
            group = main_affixes_all.get(gid, {})
            entries = []
            for affix_entry in group.get("affixes", {}).values():
                entries.append(resolve_property(
                    affix_entry["property"],
                    affix_entry["base"],
                ))
                entries[-1]["step"] = affix_entry.get("step", 0)
            main_affixes[gid] = entries

        sub_affix_gid = pieces[0]["sub_affix_group"] if pieces else "5"
        sub_entries = []
        sub_group = sub_affixes_all.get(sub_affix_gid, {})
        for affix_entry in sorted(sub_group.get("affixes", {}).values(), key=lambda x: int(x["affix_id"])):
            sub_entries.append(resolve_property(
                affix_entry["property"],
                affix_entry["base"],
            ))
            sub_entries[-1]["step"] = affix_entry.get("step", 0)
            sub_entries[-1]["step_num"] = affix_entry.get("step_num", 0)

        set_record = {
            "id": set_data["id"],
            "name": set_data["name"],
            "set_type": set_type,
            "desc": set_data["desc"],
            "set_effects": effects,
            "pieces": pieces,
            "main_affixes": main_affixes,
            "sub_affixes": sub_entries,
        }

        out_path = OUT / f"{set_data['id']}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(set_record, f, ensure_ascii=False, indent=2)
        print(f"  wrote {out_path.name} ({len(pieces)} pieces)")

        idx_entries[set_data["id"]] = {
            "id": set_data["id"],
            "name": set_data["name"],
            "set_type": set_type,
            "file": f"{set_data['id']}.json",
        }

    idx_path = OUT / "_index.json"
    with open(idx_path, "w", encoding="utf-8") as f:
        json.dump(idx_entries, f, ensure_ascii=False, indent=2)
    print(f"\n  wrote _index.json ({len(idx_entries)} sets)")

    print("\nDone.")


if __name__ == "__main__":
    build()

"""Extract EquipmentSkillConfig data for implemented light cone IDs."""
from __future__ import annotations

import json

TARGET_IDS = {
    20000, 20001, 20002, 20003, 20004, 20005, 20006, 20007, 20008, 20009,
    20010, 20011, 20012, 20013, 20014, 20015, 20016, 20017, 20018, 20019, 20020,
    21000, 21001, 21002, 21003, 21004, 21005, 21006, 21007, 21008, 21009,
    21010, 21011, 21012, 21013, 21014, 21015, 21016, 21017, 21018, 21019, 21020,
    21021, 21022, 21023, 21024, 21025, 21026, 21027, 21028, 21029, 21030,
    21031, 21032, 21033, 21034,
    23000, 23003, 23010, 24001,
}

with open(
    "original_data/turnbasedgamedata_combat/ExcelOutput/EquipmentSkillConfig.json",
    encoding="utf-8",
) as f:
    data = json.load(f)

# Filter and keep only needed fields
result = {}
for entry in data:
    sid = entry["SkillID"]
    if sid in TARGET_IDS:
        if sid not in result:
            result[sid] = []
        result[sid].append({
            "Level": entry["Level"],
            "AbilityName": entry.get("AbilityName", ""),
            "ParamList": entry.get("ParamList", []),
            "AbilityProperty": entry.get("AbilityProperty", []),
        })

# Sort each SkillID's levels
for sid in result:
    result[sid].sort(key=lambda x: x["Level"])

# Sort by SkillID
sorted_result = dict(sorted(result.items()))

output_path = "scripts/equipment_skill_extracted.json"
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(sorted_result, f, indent=2, ensure_ascii=False)

# Print summary
print(f"Extracted {len(sorted_result)} SkillIDs with {sum(len(v) for v in sorted_result.values())} total entries")
for sid, levels in sorted_result.items():
    level_nums = [l["Level"] for l in levels]
    has_props = any(l["AbilityProperty"] for l in levels)
    prop_flag = " +AbilityProperty" if has_props else ""
    print(f"  SkillID {sid}: levels {level_nums}{prop_flag}")

print(f"\nOutput written to: {output_path}")

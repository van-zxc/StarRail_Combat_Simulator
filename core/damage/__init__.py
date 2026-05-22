from __future__ import annotations

"""可插拔乘区链 — 按 DamageType 映射乘区函数列表。

新增伤害类型只需在此表中增加一行，无需修改 execute_action。
"""

from core.damage import multipliers
from core.enums import DamageType

# DamageType → [(标签, 函数), ...]  — 按应用顺序排列
MULTIPLIER_CHAIN: dict[DamageType, list[tuple[str, callable]]] = {
    DamageType.DIRECT: [
        ("dmg_bonus", multipliers.apply_dmg_bonus),
        ("weaken", multipliers.apply_weaken),
        ("vuln", multipliers.apply_vulnerability),
        ("def", multipliers.apply_defense),
        ("res", multipliers.apply_resistance),
        ("mitigation", multipliers.apply_mitigation),
        ("true_dmg", multipliers.apply_true_dmg),
        ("toughness", multipliers.apply_toughness),
        ("crit", multipliers.apply_crit),
    ],
    DamageType.DOT: [
        ("dmg_bonus", multipliers.apply_dmg_bonus),
        ("weaken", multipliers.apply_weaken),
        ("vuln", multipliers.apply_vulnerability),
        ("def", multipliers.apply_defense),
        ("res", multipliers.apply_resistance),
        ("mitigation", multipliers.apply_mitigation),
        ("true_dmg", multipliers.apply_true_dmg),
        ("toughness", multipliers.apply_toughness),
        # 无 crit
    ],
    DamageType.BREAK: [
        ("break_effect", multipliers.apply_break_effect),
        ("break_dmg_increase", multipliers.apply_break_dmg_increase),
        ("vuln", multipliers.apply_vulnerability),
        ("def", multipliers.apply_defense),
        ("res", multipliers.apply_resistance),
        ("mitigation", multipliers.apply_mitigation),
        ("true_dmg", multipliers.apply_true_dmg),
        ("toughness", multipliers.apply_toughness),
    ],
    DamageType.SUPER_BREAK: [
        ("break_effect", multipliers.apply_break_effect),
        ("break_dmg_increase", multipliers.apply_break_dmg_increase),
        ("vuln", multipliers.apply_vulnerability),
        ("def", multipliers.apply_defense),
        ("res", multipliers.apply_resistance),
        ("mitigation", multipliers.apply_mitigation),
        ("true_dmg", multipliers.apply_true_dmg),
        ("toughness", multipliers.apply_toughness),
    ],
    DamageType.ADDITIONAL_DMG: [
        # 附加伤害: 通用增伤 (无动作标签) + 可暴击 + 不削韧
        ("dmg_bonus", multipliers.apply_dmg_bonus),
        ("weaken", multipliers.apply_weaken),
        ("vuln", multipliers.apply_vulnerability),
        ("def", multipliers.apply_defense),
        ("res", multipliers.apply_resistance),
        ("mitigation", multipliers.apply_mitigation),
        ("true_dmg", multipliers.apply_true_dmg),
        ("toughness", multipliers.apply_toughness),
        ("crit", multipliers.apply_crit),
    ],
    DamageType.ELATION: [
        # 欢愉伤害: 跳过 DMG_BONUS / WEAKEN / TRUE_DMG
        ("elation_mult", multipliers.apply_elation_mult),
        ("punchline", multipliers.apply_punchline_mult),
        ("merrymake", multipliers.apply_merrymake_mult),
        ("def", multipliers.apply_defense),
        ("res", multipliers.apply_resistance),
        ("elation_vuln", multipliers.apply_elation_vuln),
        ("mitigation", multipliers.apply_mitigation),
        ("toughness", multipliers.apply_toughness),
        ("crit", multipliers.apply_crit),
    ],
}

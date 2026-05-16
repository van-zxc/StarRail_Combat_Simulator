"""基础伤害计算 — 按 DamageType 返回不同基础值。"""

from core.enums import DamageType

# Elation 专用 Level Multiplier 表 (Lv 1-80)
_ELATION_LM: dict[int, float] = {
    1: 108.00000, 2: 116.00000, 3: 124.00000, 4: 135.05276,
    5: 141.01880, 6: 147.04564, 7: 153.13210, 8: 159.27693,
    9: 165.47893, 10: 171.73688, 11: 182.98882, 12: 194.13596,
    13: 205.17833, 14: 216.11589, 15: 226.94867, 16: 237.67665,
    17: 248.29984, 18: 258.81824, 19: 269.23184, 20: 279.54068,
    21: 298.66458, 22: 317.60223, 23: 336.35364, 24: 354.91880,
    25: 373.29770, 26: 391.49036, 27: 409.49677, 28: 427.31693,
    29: 444.95080, 30: 462.39847, 31: 492.85513, 32: 522.36194,
    33: 550.94666, 34: 578.63580, 35: 605.45496, 36: 631.42880,
    37: 656.58093, 38: 680.93427, 39: 704.51074, 40: 727.33160,
    41: 816.24800, 42: 903.57660, 43: 989.35956, 44: 1073.6376,
    45: 1156.4498, 46: 1237.8344, 47: 1317.8276, 48: 1396.4651,
    49: 1473.7810, 50: 1549.8082, 51: 1742.1199, 52: 1929.7411,
    53: 2112.8413, 54: 2291.5820, 55: 2466.1170, 56: 2636.5930,
    57: 2803.1501, 58: 2965.9216, 59: 3125.0356, 60: 3280.6135,
    61: 3504.6430, 62: 3723.8022, 63: 3938.2483, 64: 4148.1320,
    65: 4353.5967, 66: 4554.7810, 67: 4751.8170, 68: 4944.8320,
    69: 5133.9478, 70: 5319.2812, 71: 5560.6090, 72: 5797.2046,
    73: 6029.2060, 74: 6256.7460, 75: 6479.9517, 76: 6698.9463,
    77: 6913.8470, 78: 7124.7686, 79: 7331.8200, 80: 7535.1070,
}


def _get_elation_level_multiplier(level: int) -> float:
    return _ELATION_LM.get(level, _ELATION_LM[1])


def compute_base_damage(
    damage_type: DamageType,
    attacker: "Character",
    skill_multiplier: float,
    override: int | None = None,
    dot_source: "DoTStatus | None" = None,
) -> int:
    """根据伤害类型计算基础伤害值。

    DIRECT / ADDITIONAL_DMG: ATK * skill_multiplier
    ELATION: LevelMultiplier(level) * skill_multiplier
    DOT: ATK * dot_multiplier * stacks (由覆盖值传入)
    BREAK / SUPER_BREAK: 预留, 目前返回 0
    """
    if override is not None:
        return override
    if damage_type in (DamageType.DIRECT, DamageType.ADDITIONAL_DMG):
        return int(attacker.atk * skill_multiplier)
    if damage_type == DamageType.ELATION:
        lm = _get_elation_level_multiplier(attacker.level)
        return int(lm * skill_multiplier)
    return 0

"""战斗系统枚举定义。"""

from enum import Enum, auto


# ============================================================
#  ActionType — 动作枚举
# ============================================================
class ActionType(Enum):
    BASIC_ATTACK = auto()
    ENHANCED_BASIC = auto()
    SKILL = auto()
    ULTIMATE = auto()
    TALENT = auto()
    FOLLOW_UP = auto()
    COUNTER = auto()
    SUMMON = auto()
    EXTRA_TURN = auto()


# ============================================================
#  DamageType — 伤害类型枚举
# ============================================================
class DamageType(Enum):
    DIRECT = auto()
    DOT = auto()
    BREAK = auto()
    SUPER_BREAK = auto()
    ADDITIONAL_DMG = auto()
    ELATION = auto()


# ============================================================
#  StatType — 属性枚举
# ============================================================
class StatType(Enum):
    ATK = auto()
    DEF = auto()
    HP = auto()
    DEF_REDUCTION = auto()
    SPD = auto()
    CRIT_RATE = auto()
    CRIT_DMG = auto()
    ERR = auto()
    MAX_ENERGY = auto()
    EFFECT_RES = auto()
    EFFECT_HIT_RATE = auto()
    RES_PEN = auto()
    RES = auto()
    DMG_TAKEN = auto()
    DMG_BONUS = auto()
    VULNERABILITY = auto()
    WEAKEN = auto()
    BASIC_ATK_DMG = auto()
    SKILL_DMG = auto()
    ULT_DMG = auto()
    FUA_DMG = auto()
    AGGRO_MODIFIER = auto()
    BREAK_EFFECT = auto()
    BREAK_DMG_INCREASE = auto()
    DMG_MITIGATION = auto()
    OUTGOING_HEALING_BOOST = auto()
    INCOMING_HEALING_BOOST = auto()
    INCOMING_HEALING_REDUCTION = auto()
    SHIELD_BONUS = auto()
    TRUE_DMG_BONUS = auto()
    DEBUFF_RES_BLEED = auto()
    DEBUFF_RES_BURN = auto()
    DEBUFF_RES_FREEZE = auto()
    DEBUFF_RES_SHOCK = auto()
    DEBUFF_RES_WIND_SHEAR = auto()
    DEBUFF_RES_ENTANGLE = auto()
    DEBUFF_RES_IMPRISON = auto()
    PHYSICAL_DMG_BONUS = auto()
    FIRE_DMG_BONUS = auto()
    ICE_DMG_BONUS = auto()
    THUNDER_DMG_BONUS = auto()
    WIND_DMG_BONUS = auto()
    QUANTUM_DMG_BONUS = auto()
    IMAGINARY_DMG_BONUS = auto()
    ELATION = auto()
    MERRYMAKE = auto()
    ELATION_VULN = auto()
    FIRE_VULN = auto()
    ICE_VULN = auto()
    THUNDER_VULN = auto()
    PHYSICAL_VULN = auto()
    WIND_VULN = auto()
    QUANTUM_VULN = auto()
    IMAGINARY_VULN = auto()


# debuff_type → StatType 映射
DEBUFF_RES_MAP: dict[str, "StatType"] = {
    "Bleed": StatType.DEBUFF_RES_BLEED,
    "Burn": StatType.DEBUFF_RES_BURN,
    "Freeze": StatType.DEBUFF_RES_FREEZE,
    "Shock": StatType.DEBUFF_RES_SHOCK,
    "WindShear": StatType.DEBUFF_RES_WIND_SHEAR,
    "Entanglement": StatType.DEBUFF_RES_ENTANGLE,
    "Imprison": StatType.DEBUFF_RES_IMPRISON,
}


# ============================================================
#  ElementType / PathType — 属性 & 命途枚举
# ============================================================
class ElementType(Enum):
    PHYSICAL = auto()
    FIRE = auto()
    ICE = auto()
    LIGHTNING = auto()
    WIND = auto()
    QUANTUM = auto()
    IMAGINARY = auto()


# ElementType → 元素专属增伤 StatType 映射
_ELEMENT_DMG_STAT: dict[ElementType, StatType] = {
    ElementType.PHYSICAL: StatType.PHYSICAL_DMG_BONUS,
    ElementType.FIRE: StatType.FIRE_DMG_BONUS,
    ElementType.ICE: StatType.ICE_DMG_BONUS,
    ElementType.LIGHTNING: StatType.THUNDER_DMG_BONUS,
    ElementType.WIND: StatType.WIND_DMG_BONUS,
    ElementType.QUANTUM: StatType.QUANTUM_DMG_BONUS,
    ElementType.IMAGINARY: StatType.IMAGINARY_DMG_BONUS,
}


# ============================================================
#  ElementType / PathType — 属性 & 命途枚举
# ============================================================
class ElementType(Enum):
    PHYSICAL = auto()
    FIRE = auto()
    ICE = auto()
    LIGHTNING = auto()
    WIND = auto()
    QUANTUM = auto()
    IMAGINARY = auto()


class PathType(Enum):
    DESTRUCTION = auto()
    HUNT = auto()
    ERUDITION = auto()
    HARMONY = auto()
    NIHILITY = auto()
    PRESERVATION = auto()
    ABUNDANCE = auto()
    REMEMBRANCE = auto()
    ELATION = auto()


# ============================================================
#  RelicPart / StatModifierType — 遗器部位 & 加成类型
# ============================================================
class RelicPart(Enum):
    HEAD = auto()
    HANDS = auto()
    BODY = auto()
    FEET = auto()
    PLANAR_SPHERE = auto()
    LINK_ROPE = auto()


class StatModifierType(Enum):
    FLAT = auto()
    PERCENT = auto()

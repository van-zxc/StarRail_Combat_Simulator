"""Silver Wolf Eidolons — 星魂 1-6 (Enhanced).

来源: 1006_silverwolf.json eidolons
"""


def eidolon_1(owner) -> list:
    owner._has_e1 = True
    return []


def eidolon_2(owner) -> list:
    owner._has_e2 = True
    return []


def eidolon_3(owner) -> list:
    skill = owner._skills.get("skill")
    if skill:
        skill.skill_multiplier += 0.196
        skill.implant_base_chance += 0.08
        skill.alltype_res_value += 0.005
    talent = owner._skills.get("talent")
    if talent:
        talent.bug_atk_down += 0.01
        talent.bug_def_down += 0.012
        talent.bug_spd_down += 0.006
        talent.bug_base_chance += 0.08
    return []


def eidolon_4(owner) -> list:
    owner._has_e4 = True
    return []


def eidolon_5(owner) -> list:
    ult = owner._skills.get("ultimate")
    if ult:
        ult.skill_multiplier += 0.304
        ult.def_reduce_base_chance += 0.08
        ult.def_reduce_value += 0.018
    basic = owner._skills.get("basic")
    if basic:
        basic.skill_multiplier += 0.10
    return []


def eidolon_6(owner) -> list:
    owner._has_e6 = True
    return []


EIDOLON_REGISTRY: dict[int, callable] = {
    1: eidolon_1, 2: eidolon_2, 3: eidolon_3,
    4: eidolon_4, 5: eidolon_5, 6: eidolon_6,
}

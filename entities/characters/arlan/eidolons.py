from __future__ import annotations

"""Arlan Eidolons — 星魂 1-6。

来源: 1008_arlan.json eidolons
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
        skill.skill_multiplier += 0.24
    basic = owner._skills.get("basic")
    if basic:
        basic.skill_multiplier += 0.10
    return []


def eidolon_4(owner) -> list:
    owner._has_e4 = True
    owner._e4_active = False
    owner._e4_remaining = 0
    return []


def eidolon_5(owner) -> list:
    ult = owner._skills.get("ultimate")
    if ult:
        ult.skill_multiplier += 0.256
        ult.skill_adjacent += 0.128
    talent = owner._skills.get("talent")
    if talent:
        talent.talent_max += 0.072
    return []


def eidolon_6(owner) -> list:
    owner._has_e6 = True
    return []


EIDOLON_REGISTRY: dict[int, callable] = {
    1: eidolon_1, 2: eidolon_2, 3: eidolon_3,
    4: eidolon_4, 5: eidolon_5, 6: eidolon_6,
}

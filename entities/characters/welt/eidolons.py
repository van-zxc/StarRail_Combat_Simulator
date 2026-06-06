from __future__ import annotations
"""Welt Eidolons — 星魂 1-6 (Enhanced)。

来源: 1004_welt.json eidolons
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
        skill.skill_multiplier += 0.072
    basic = owner._skills.get("basic")
    if basic:
        basic.skill_multiplier += 0.10
    return []


def eidolon_4(owner) -> list:
    owner._has_e4 = True
    return []


def eidolon_5(owner) -> list:
    ult = owner._skills.get("ultimate")
    if ult:
        ult.skill_multiplier += 0.12
    return []


def eidolon_6(owner) -> list:
    owner._has_e6 = True
    return []


EIDOLON_REGISTRY: dict[int, callable] = {
    1: eidolon_1, 2: eidolon_2, 3: eidolon_3,
    4: eidolon_4, 5: eidolon_5, 6: eidolon_6,
}

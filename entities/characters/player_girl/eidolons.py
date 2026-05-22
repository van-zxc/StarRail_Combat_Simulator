from __future__ import annotations
"""PlayerGirl Eidolons — 星魂 1-6。

来源: 8002_playergirl.json eidolons
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
        skill.skill_multiplier += 0.125
    talent = owner._skills.get("talent")
    if talent:
        talent.atk_per_stack += 0.02
    return []


def eidolon_4(owner) -> list:
    owner._has_e4 = True
    return []


def eidolon_5(owner) -> list:
    ult = owner._skills.get("ultimate")
    if ult:
        ult.skill_multiplier += 0.30
        ult.blast_primary += 0.18
        ult.blast_adjacent += 0.108
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

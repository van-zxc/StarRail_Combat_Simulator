from __future__ import annotations
"""TemplateSkills — 标准技能类（普攻 / 战技 / 终结技）。

每个技能对象持有角色引用，调用 GameState.execute_action。
子类可覆写 execute() 以附加 DoT / Buff 等额外效果。
"""

from core.enums import ActionType, DamageType


# ============================================================
#  TemplateBasicAttack — 普攻模板
# ============================================================
class TemplateBasicAttack:
    action_type = ActionType.BASIC_ATTACK
    skill_multiplier = 1.0
    damage_type = DamageType.DIRECT
    energy_gain: float = 20

    def __init__(self, owner: "BaseCharacter") -> None:
        self.owner = owner

    def execute(self, target: "Enemy", state: "GameState") -> tuple[int, bool, float, bool]:
        """执行普攻：基伤 + 可附加效果（子类覆写）。"""
        return state.execute_action(
            self.owner, self.action_type, target,
            self.skill_multiplier, damage_type=self.damage_type,
        )


# ============================================================
#  TemplateSkill — 战技模板
# ============================================================
class TemplateSkill:
    action_type = ActionType.SKILL
    skill_multiplier = 2.0
    damage_type = DamageType.DIRECT
    energy_gain: float = 30

    def __init__(self, owner: "BaseCharacter") -> None:
        self.owner = owner

    def execute(self, target: "Enemy", state: "GameState") -> tuple[int, bool, float, bool]:
        """执行战技：基伤 + 可附加效果（子类覆写）。"""
        return state.execute_action(
            self.owner, self.action_type, target,
            self.skill_multiplier, damage_type=self.damage_type,
        )


# ============================================================
#  TemplateUltimate — 终结技模板
# ============================================================
class TemplateUltimate:
    action_type = ActionType.ULTIMATE
    skill_multiplier = 3.0
    damage_type = DamageType.DIRECT
    energy_gain: float = 5  # 大招释放后固定回能 (如停云)

    def __init__(self, owner: "BaseCharacter") -> None:
        self.owner = owner

    def execute(self, target: "Enemy", state: "GameState") -> tuple[int, bool, float, bool]:
        """执行终结技：基伤 + 可附加效果（子类覆写）。"""
        return state.execute_action(
            self.owner, self.action_type, target,
            self.skill_multiplier, damage_type=self.damage_type,
        )

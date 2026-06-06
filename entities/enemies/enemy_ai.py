from __future__ import annotations
"""敌人 AI — SimpleAI / PriorityAI / 行为树骨架。"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PriorityRule:
    condition: str
    skill_id: str
    params: dict = field(default_factory=dict)


class EnemyAI(ABC):
    @abstractmethod
    def select_skill(self, enemy: "BaseEnemy", state: "GameState") -> "EnemySkill":
        ...


class SimpleAI(EnemyAI):
    """Minion 用：返回第一个可用技能。"""

    def select_skill(self, enemy: "BaseEnemy", state: "GameState") -> "EnemySkill":
        for skill in enemy._skills.values():
            if skill.available and enemy.energy >= skill.energy_cost:
                return skill
        return enemy._default_skill


class PriorityAI(EnemyAI):
    """Elite 用：按优先级规则选择技能。

    _rules 中每条规则按顺序检查 condition。
    支持的 condition 字符串:
      - "always" — 永远命中
      - "hp_below:<pct>" — 自身 HP 百分比低于阈值
      - "cd_ready:<skill_id>" — 指定技能冷却完毕
      - "energy_ready:<threshold>" — 能量超过阈值
      - "no_other_skill" — 没有其他满足规则的技能
    """

    _rules: list[PriorityRule] = []

    def select_skill(self, enemy: "BaseEnemy", state: "GameState") -> "EnemySkill":
        for rule in self._rules:
            if self._evaluate(enemy, state, rule):
                skill = enemy._skills.get(rule.skill_id)
                if skill is not None and skill.available and enemy.energy >= skill.energy_cost:
                    return skill
        return enemy._default_skill

    def _evaluate(self, enemy: "BaseEnemy", state: "GameState", rule: PriorityRule) -> bool:
        cond = rule.condition
        if cond == "always":
            return True
        if cond == "no_other_skill":
            return False
        if cond.startswith("hp_below:"):
            pct = float(cond.split(":", 1)[1])
            return enemy.hp / enemy.max_hp < pct
        if cond.startswith("cd_ready:"):
            sid = cond.split(":", 1)[1]
            skill = enemy._skills.get(sid)
            return skill is not None and skill.available
        if cond.startswith("energy_ready:"):
            threshold = float(cond.split(":", 1)[1])
            return enemy.energy >= threshold
        return False


class SequenceAI(EnemyAI):
    """Minion/Elite 用：按固定序列循环使用技能。

    与游戏中 Monster_Common_SequenceThree AI 对应。
    _sequence 是 skill_id 列表，按顺序尝试每个技能（跳过冷却/能量不足的）。
    一轮序列完成后重置从头开始。
    """

    _sequence: list[str] = []
    _index: int = 0

    def select_skill(self, enemy: "BaseEnemy", state: "GameState") -> "EnemySkill":
        if not self._sequence:
            return enemy._default_skill

        n = len(self._sequence)
        for _ in range(n):
            sid = self._sequence[self._index]
            skill = enemy._skills.get(sid)
            if skill is not None and skill.available and enemy.energy >= skill.energy_cost:
                self._index = (self._index + 1) % n
                return skill
            self._index = (self._index + 1) % n

        return enemy._default_skill


# ── 行为树骨架 (Boss 用, 预留) ──

class BTNode(ABC):
    @abstractmethod
    def tick(self, ctx: "BTContext") -> bool:
        ...


class BTContext:
    __slots__ = ("enemy", "state", "blackboard")

    def __init__(self, enemy: "BaseEnemy", state: "GameState") -> None:
        self.enemy = enemy
        self.state = state
        self.blackboard: dict[str, object] = {}


class BTSelector(BTNode):
    """选择器：依次执行子节点，第一个成功则返回 True。"""

    def __init__(self, *children: BTNode) -> None:
        self._children = children

    def tick(self, ctx: BTContext) -> bool:
        for child in self._children:
            if child.tick(ctx):
                return True
        return False


class BTSequence(BTNode):
    """序列：依次执行子节点，全部成功返回 True。"""

    def __init__(self, *children: BTNode) -> None:
        self._children = children

    def tick(self, ctx: BTContext) -> bool:
        for child in self._children:
            if not child.tick(ctx):
                return False
        return True


class BTCondition(BTNode):
    """条件叶子：检查条件，直接返回布尔值。"""

    def __init__(self, condition: str, **params: object) -> None:
        self._condition = condition
        self._params = params

    def tick(self, ctx: BTContext) -> bool:
        cond = self._condition
        enemy = ctx.enemy
        state = ctx.state
        if cond == "always":
            return True
        if cond == "hp_below":
            return enemy.hp / enemy.max_hp < float(self._params.get("pct", 0.5))
        if cond == "phase_is":
            return int(self._params.get("phase", 1)) == ctx.blackboard.get("phase", 1)
        if cond == "skill_ready":
            sid = str(self._params.get("skill_id", ""))
            skill = enemy._skills.get(sid)
            return skill is not None and skill.available
        return False


class BTAction(BTNode):
    """动作叶子：将选中的技能写入 blackboard。"""

    def __init__(self, skill_id: str) -> None:
        self._skill_id = skill_id

    def tick(self, ctx: BTContext) -> bool:
        skill = ctx.enemy._skills.get(self._skill_id)
        if skill is not None and skill.available and ctx.enemy.energy >= skill.energy_cost:
            ctx.blackboard["selected_skill"] = skill
            return True
        return False

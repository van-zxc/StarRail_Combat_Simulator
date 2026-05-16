"""TargetManager — 统一索敌管理器。

支持五级优先级: 退场 → 嘲讽 → 锁定 → 弹射 → 仇恨概率。
"""

from __future__ import annotations

import random

from core.enums import PathType, StatType
from config.game_config import BASE_AGGRO


class TargetManager:
    """统一索敌入口，所有攻击行为必须通过此接口获取目标。"""

    @staticmethod
    def get_base_aggro(character: "Character") -> float:
        return BASE_AGGRO.get(character.path, 4.0)

    @staticmethod
    def get_total_aggro(character: "Character") -> float:
        base = TargetManager.get_base_aggro(character)
        mod = 1.0 + character.stats.get_total_stat(StatType.AGGRO_MODIFIER)
        ext = getattr(character, "external_taunt_factor", 1.0)
        return base * mod * ext

    @staticmethod
    def select_target(
        attacker: "Fighter",
        candidates: list["Fighter"],
        is_bounce: bool = False,
    ) -> "Fighter" | None:
        """统一索敌入口。

        1. 退场/死亡自动排除
        2. 弹射 → 均匀随机 (无视 Taunt/LockOn)
        3. 锁定 (attacker 上的 lock_on_target)
        4. 嘲讽 (attacker 上的 taunt_source)
        5. 仇恨加权随机
        """
        alive = [f for f in candidates if f.is_alive and not f.is_departed]
        if not alive:
            return None

        # Priority 2: 弹射 (不受嘲讽/锁定影响)
        if is_bounce:
            return random.choice(alive)

        # TODO(#17): LockOn 与 Taunt 的正式优先级尚未完全锁定 (§11.5)
        # Priority 3: 锁定
        lo = getattr(attacker, "lock_on_target", None)
        if lo is not None and lo in alive:
            return lo

        # Priority 4: 嘲讽
        ts = getattr(attacker, "taunt_source", None)
        if ts is not None and ts in alive:
            return ts

        # Priority 5: 仇恨概率
        weights: list[float] = []
        for f in alive:
            if hasattr(f, "path"):
                weights.append(TargetManager.get_total_aggro(f))
            else:
                weights.append(1.0)
        total = sum(weights)
        if total <= 0:
            return random.choice(alive)
        r = random.random() * total
        cumulative = 0.0
        for i, f in enumerate(alive):
            cumulative += weights[i]
            if r <= cumulative:
                return f
        return alive[-1]

    # ── 扩散 / 群攻 / 随机 ──

    @staticmethod
    def _filter_alive(candidates: list["Fighter"]) -> list["Fighter"]:
        return [f for f in candidates if f.is_alive and not f.is_departed]

    @staticmethod
    def select_blast(
        candidates: list["Fighter"],
        primary: "Fighter",
    ) -> list["Fighter"]:
        """扩散: 主目标 + 相邻 1 格内的目标 (总上限 3)。"""
        alive = TargetManager._filter_alive(candidates)
        if primary not in alive:
            return []
        idx = alive.index(primary)
        result: list["Fighter"] = [primary]
        if idx > 0:
            result.append(alive[idx - 1])
        if idx < len(alive) - 1:
            result.append(alive[idx + 1])
        return result

    @staticmethod
    def select_aoe(candidates: list["Fighter"]) -> list["Fighter"]:
        """群攻: 返回所有存活且未退场的目标。"""
        return TargetManager._filter_alive(candidates)

    @staticmethod
    def select_random(
        candidates: list["Fighter"],
        count: int = 1,
    ) -> list["Fighter"]:
        """随机: 从候选池无放回抽取指定数量。"""
        alive = TargetManager._filter_alive(candidates)
        count = min(count, len(alive))
        return random.sample(alive, count)

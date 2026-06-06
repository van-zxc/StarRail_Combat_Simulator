from __future__ import annotations
"""事件系统 — 发布订阅模式, 替代硬编码流程分支。"""

from enum import Enum, auto
from typing import Callable


class EventType(Enum):
    # 战斗/波次
    BATTLE_START = auto()
    BATTLE_END = auto()
    WAVE_START = auto()
    # 行动条
    ON_BEFORE_ACTION_ORDER_RESOLVE = auto()
    # 回合
    TURN_START = auto()
    TURN_END = auto()
    # 动作
    ACTION_START = auto()
    ON_BEFORE_PAY_COST = auto()
    ON_AFTER_PAY_COST = auto()
    ON_BEFORE_TARGET_SELECT = auto()
    ON_AFTER_TARGET_SELECT = auto()
    ON_BEFORE_HIT = auto()
    ON_HIT = auto()
    ON_DAMAGE_CALCULATED = auto()
    ON_DAMAGE_DEALT = auto()
    AFTER_ACTION = auto()
    # 终极技
    ON_ULTIMATE_QUEUED = auto()
    ON_ULTIMATE_INSERTED = auto()
    # 韧性/击破
    ON_TOUGHNESS_DAMAGE = auto()
    ON_WEAKNESS_BREAK = auto()
    # 状态
    ON_STATUS_APPLY = auto()
    ON_STATUS_EXPIRE = auto()
    ON_SHIELD_APPLIED = auto()
    # 属性变化 (SPD/EHR/CRIT 等关键属性)
    ON_ABILITY_PROPERTY_CHANGE = auto()
    # 致死/击杀/复活
    BEFORE_DEATH = auto()
    ON_LIMBO = auto()               # 濒死等待复活阶段
    UNIT_DOWNED = auto()
    ON_KILL = auto()
    ON_REVIVE = auto()
    ON_LEAVE_FIELD = auto()
    # 治疗
    HEAL_DONE = auto()
    # HP 变化
    ON_HP_CHANGE = auto()
    # 敌人生命周期
    CHARACTER_CREATED = auto()
    # 伤害计算前 (per-hit 条件增伤钩子)
    ON_BEFORE_DAMAGE_CALC = auto()


class EventBus:
    """轻量事件总线: subscribe 注册监听, emit 触发回调。"""

    def __init__(self) -> None:
        self._listeners: dict[EventType, list[Callable[..., None]]] = {}

    def subscribe(self, event_type: EventType, callback: Callable[..., None]) -> None:
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        self._listeners[event_type].append(callback)

    def unsubscribe(self, event_type: EventType, callback: Callable[..., None]) -> None:
        if event_type in self._listeners:
            self._listeners[event_type] = [
                cb for cb in self._listeners[event_type] if cb is not callback
            ]

    def clear_all(self) -> None:
        """清除所有事件监听器，用于战斗结束时清理订阅。"""
        self._listeners.clear()

    def emit(self, event_type: EventType, **kwargs: object) -> None:
        for cb in self._listeners.get(event_type, []):
            cb(**kwargs)

"""entities 通用基类 — Fighter, StatModifier, EquipmentEffect, DoTStatus。

注意: EntityStats 保留在 starrail_combat.py 中（依赖 StatType 枚举类级常量）。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


# ============================================================
#  StatModifier — 属性修正数据
# ============================================================
@dataclass
class StatModifier:
    stat_type: "StatType"
    modifier_type: "StatModifierType"
    value: float
    source: str = ""
    applied_this_turn: bool = False
    cc_type: str = ""
    duration: int | None = None
    dispellable: bool = True
    stack_policy: str = "independent"
    tick_timing: str = "owner_turn_end"
    duration_mode: str = "turns"
    tags: tuple = ()


# ============================================================
#  EquipmentEffect — 装备特效抽象接口
# ============================================================
class EquipmentEffect(ABC):
    """装备特效基类：装备时 / 进入战斗时触发。"""

    @abstractmethod
    def on_equip(self, character: "Character") -> None:
        """装备时触发，用于直接修改面板或挂载永久被动。"""
        ...

    @abstractmethod
    def on_combat_start(self, game_state: "GameState", character: "Character") -> None:
        """进入战斗时触发，用于注册事件监听器。"""
        ...


# ============================================================
#  Fighter — 抽象战斗实体
# ============================================================
class Fighter(ABC):
    """战斗实体基类：己方角色与敌方目标共享的属性与接口。"""

    _av_zero_counter: int = 0  # 全局 AV 归零计数器, LIFO 排序用

    def __init__(self, name: str, hp: int, speed: int) -> None:
        self.name = name
        self.max_hp = hp
        self.hp = hp
        self._base_speed = speed
        self.current_av: float = self.base_av
        self._av_zero_ts: float = 0.0  # AV 归零时间戳, LIFO 同 AV 排序用
        # 波次切换时 AV 是否保留
        self.av_keep_on_wave: bool = False
        # 索敌状态
        self.is_departed: bool = False
        self.taunt_source: Optional["Fighter"] = None
        self.lock_on_target: Optional["Fighter"] = None
        # 外部嘲讽因子 (外部嘲讽独立乘区, 默认 1.0)
        self.external_taunt_factor: float = 1.0
        # 护盾
        self.shield_statuses: list["ShieldStatus"] = []
        # 冻结附加伤害
        self.freeze_dot_statuses: list["FreezeDotStatus"] = []
        # 受击计数
        self.hit_count: int = 0
        # 控制状态
        self.cc_statuses: list["CCStatus"] = []
        # 欢愉 Certified Banger buff
        self.certified_bangers: list["CertifiedBanger"] = []
        # 事件总线引用 (由 CombatEngine 注入)
        self.event_bus: "EventBus | None" = None
        # 免疫非 DoT 伤害直到首次受击 (Arlan A3)
        self._nullify_direct_dmg: bool = False
        self._before_death_emitted: bool = False  # 防止 BEFORE_DEATH 重复 emit

    @property
    def speed(self) -> float:
        """从装饰器池读取当前速度（若有 stats），否则用构造初始值。"""
        if hasattr(self, "stats") and self.stats is not None:
            from core.enums import StatType
            spd = self.stats.get_total_stat(StatType.SPD)
            if spd > 0:
                return spd
        return self._base_speed

    @property
    def base_av(self) -> float:
        return 10000.0 / self.speed

    @property
    def current_ag(self) -> float:
        """当前 Action Gauge，文档基准值 10000。"""
        return self.current_av * self.speed

    @property
    def is_alive(self) -> bool:
        return self.hp > 0

    @property
    def can_act(self) -> bool:
        """是否能行动（未被控制类状态阻止）。"""
        return not self.is_cc_blocked

    def take_damage(self, amount: int, *, bypass_shield: bool = False) -> int:
        """扣除生命值，返回实际造成的伤害值。

        bypass_shield=True 时跳过护盾吸收（如 DoT）。
        """
        if amount > 0 and not bypass_shield and self._nullify_direct_dmg:
            self._nullify_direct_dmg = False
            return 0
        if not bypass_shield and amount > 0 and self.shield_statuses:
            remaining = []
            for s in self.shield_statuses:
                if amount <= 0:
                    remaining.append(s)
                    continue
                absorbed = min(s.shield_value, amount)
                s.shield_value -= absorbed
                amount -= absorbed
                if s.shield_value > 0:
                    remaining.append(s)
            self.shield_statuses = remaining
        actual = min(self.hp, amount) if amount > 0 else 0
        self.hp -= actual
        if self.hp <= 0 and self.event_bus is not None and not self._before_death_emitted:
            from core.events import EventType
            self._before_death_emitted = True
            self.event_bus.emit(EventType.BEFORE_DEATH, target=self)
        return actual

    def apply_shield(self, shield: "ShieldStatus") -> None:
        """挂载护盾并 emit ON_SHIELD_APPLIED 事件。"""
        self.shield_statuses.append(shield)
        if self.event_bus is not None:
            from core.events import EventType
            self.event_bus.emit(EventType.ON_SHIELD_APPLIED, target=self, shield=shield)

    def receive_heal(self, amount: int) -> int:
        """接收治疗，返回实际恢复的生命值（不超过 max_hp）。"""
        actual = min(amount, self.max_hp - self.hp)
        self.hp += actual
        return actual

    def reset_av(self) -> None:
        self.current_av = self.base_av

    # -- AV 操作 --

    def modify_action_gauge(self, advance: float = 0.0, delay: float = 0.0) -> None:
        """拉条/推条统一公式:
        NewAG = max(0, CurrentAG - 10000 × (Adv% - Delay%))
        NewAV = NewAG / CurrentSPD
        """
        new_ag = max(0.0, self.current_ag - 10000.0 * (advance - delay))
        self.current_av = new_ag / self.speed
        if self.current_av == 0.0:
            Fighter._av_zero_counter += 1  # type: ignore[attr-defined]
            self._av_zero_ts = Fighter._av_zero_counter  # type: ignore[attr-defined]

    def advance_action(self, pct: float) -> None:
        """拉条: 等效于 modify_action_gauge(advance=pct)。"""
        self.modify_action_gauge(advance=pct)

    def delay_action(self, pct: float) -> None:
        """推后: 等效于 modify_action_gauge(delay=pct)。"""
        self.modify_action_gauge(delay=pct)

    def immediate_action(self) -> None:
        """立即行动: current_av = 0。"""
        self.current_av = 0.0
        Fighter._av_zero_counter += 1  # type: ignore[attr-defined]
        self._av_zero_ts = Fighter._av_zero_counter  # type: ignore[attr-defined]

    def recalc_av_for_spd(self, old_spd: float, new_spd: float) -> None:
        """动态 SPD 折算: av_new = av_old * (spd_old / spd_new)。"""
        if old_spd > 0:
            self.current_av = self.current_av * (old_spd / new_spd)

    # -- 控制状态 --

    @property
    def is_cc_blocked(self) -> bool:
        """是否有生效中的控制类负面状态。"""
        if not hasattr(self, "stats"):
            return False
        for m in self.stats.active_modifiers:
            if getattr(m, "cc_type", ""):
                return True
        return False


# ============================================================
#  DoTStatus — 持续伤害状态对象
# ============================================================
@dataclass
class DoTStatus:
    source_character: "Character"
    element: "ElementType"
    dot_multiplier: float
    stacks: int = 1
    duration: int = 1
    is_break_induced: bool = False
    break_effect_snapshot: float = 0.0


# ============================================================
#  ShieldStatus — 护盾状态对象 (值制, 溢出穿透)
# ============================================================
@dataclass
class ShieldStatus:
    shield_value: float = 0.0
    max_shield_value: float = 0.0
    source_name: str = ""
    duration: int | None = None  # None=永久, N=剩余回合数


# ============================================================
#  CCStatus — 控制类状态 (冻结/禁锢/纠缠)
# ============================================================
@dataclass
class CCStatus:
    cc_type: str = ""      # "Freeze", "Imprison", "Entanglement"
    remaining_turns: int = 1
    stacks: int = 1        # 纠缠层数
    break_effect_snapshot: float = 0.0  # 快照 BE


# ============================================================
#  FreezeDotStatus — 冻结附加伤害状态
# ============================================================
@dataclass
class FreezeDotStatus:
    attacker: "Fighter"
    multiplier: float = 0.0
    remaining_turns: int = 1


# ============================================================
#  CertifiedBanger — Aha Instant 后发放的欢愉 Buff
# ============================================================
@dataclass
class CertifiedBanger:
    value: int = 0        # Aha Instant 初始 Punchline 快照值
    duration: int = 2     # 独立追踪回合 (每次 Aha Instant 创建新实例)


# ============================================================
#  ToughnessDamagePacket — 削韧参数包
# ============================================================
@dataclass
class ToughnessDamagePacket:
    amount: float = 0.0
    element: "ElementType | None" = None
    ignores_weakness: bool = False
    efficiency_multiplier: float = 1.0


# ============================================================
#  HitPacket — 多段攻击的单一段描述
# ============================================================
@dataclass
class HitPacket:
    target: "Fighter | None" = None
    skill_multiplier: float = 1.0
    element_override: "ElementType | None" = None
    toughness_packet: "ToughnessDamagePacket | None" = None


# ============================================================
#  ImplantedWeakness — 银狼弱点植入状态
# ============================================================
@dataclass
class ImplantedWeakness:
    element: "ElementType"
    source: "Fighter"
    remaining_turns: int
    res_reduction: float = 0.0


# ============================================================
#  Memosprite — 忆灵 (独立战斗实体, 继承主人基础面板)
# ============================================================
class Memosprite(Fighter):
    """忆灵: 拥有独立 AV、独立修饰器池、可被敌方选中。

    基础面板继承自 Memomaster, 但 HP 可缩放。
    """

    def __init__(
        self,
        name: str,
        master: "Character",
        speed: int,
        hp_scale: float = 1.0,
    ) -> None:
        self.master = master
        self.hp_scale = hp_scale
        self.is_memosprite: bool = True

        from core.entity_stats import EntityStats
        from core.enums import StatType as ST

        # 基础属性继承主人白值 (HP 可缩放)
        base_data: dict["ST", float] = {
            ST.HP: master.max_hp * hp_scale,
            ST.ATK: master.stats.get_base_stat(ST.ATK),
            ST.DEF: master.stats.get_base_stat(ST.DEF),
            ST.SPD: float(speed),
            ST.CRIT_RATE: master.stats.get_base_stat(ST.CRIT_RATE),
            ST.CRIT_DMG: master.stats.get_base_stat(ST.CRIT_DMG),
            ST.ERR: 1.0,
            ST.MAX_ENERGY: 0.0,
        }
        self.stats = EntityStats(base_data)
        self.stats.bind(self)

        hp = int(self.stats.get_base_stat(ST.HP))
        super().__init__(name, hp, speed)

    # 属性代理 (从自身 modifier pool 读取)
    @property
    def atk(self) -> float:
        from core.enums import StatType as ST
        return self.stats.get_total_stat(ST.ATK)

    @property
    def element(self):
        return self.master.element

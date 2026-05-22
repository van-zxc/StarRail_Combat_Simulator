from __future__ import annotations
"""EntityStats — 属性面板（白值 / 绿值分离）。"""

from typing import Optional

from core.enums import StatType, StatModifierType


class EntityStats:
    """实体属性面板：白值（角色 + 光锥）→ 绿值（修饰器池驱动）。"""

    _MULTIPLICATIVE_STATS: set[StatType] = {
        StatType.HP, StatType.ATK, StatType.DEF, StatType.SPD,
    }

    def __init__(self, base_data: dict[StatType, float]) -> None:
        self._base_stats: dict[StatType, float] = dict(base_data)
        self._owner: Optional["Fighter"] = None
        self.active_modifiers: list["StatModifier"] = []

    def bind(self, entity: "Fighter") -> None:
        self._owner = entity

    def add_modifier(self, modifier: "StatModifier") -> None:
        """向后兼容入口，等效于 apply_modifier(mod, 'independent')。"""
        self.apply_modifier(modifier, "independent")

    def _recalc_spd_if_changed(self, old_spd: float) -> None:
        """SPD 变化时通知 owner 重算 AV。"""
        if self._owner and old_spd > 0:
            new_spd = self.get_total_stat(StatType.SPD)
            if old_spd != new_spd:
                self._owner.recalc_av_for_spd(old_spd, new_spd)

    def apply_modifier(self, modifier: "StatModifier", stack_policy: str) -> None:
        """统一修饰器施加入口，按 stack_policy 处理同源冲突。

        策略: refresh / independent / add_stacks / replace_weaker /
               replace_stronger / no_stack
        """
        old_spd = self.get_total_stat(StatType.SPD) if self._owner else 0.0

        existing = [
            m for m in self.active_modifiers
            if m.stat_type == modifier.stat_type
            and m.source == modifier.source
        ]

        if stack_policy == "refresh":
            if existing:
                for old in existing:
                    old.value = modifier.value
                    if modifier.duration is not None:
                        old.duration = modifier.duration
            else:
                self.active_modifiers.append(modifier)
        elif stack_policy == "independent":
            self.active_modifiers.append(modifier)
        elif stack_policy == "add_stacks":
            if existing:
                existing[0].value += modifier.value
            else:
                self.active_modifiers.append(modifier)
        elif stack_policy == "replace_weaker":
            if existing and modifier.value > existing[0].value:
                existing[0].value = modifier.value
            elif not existing:
                self.active_modifiers.append(modifier)
        elif stack_policy == "replace_stronger":
            if existing and modifier.value < existing[0].value:
                existing[0].value = modifier.value
            elif not existing:
                self.active_modifiers.append(modifier)
        elif stack_policy == "no_stack":
            if not existing:
                self.active_modifiers.append(modifier)
        else:
            self.active_modifiers.append(modifier)

        if modifier.stat_type == StatType.SPD:
            self._recalc_spd_if_changed(old_spd)

        if self._owner is not None and self._owner.event_bus is not None:
            from core.events import EventType
            self._owner.event_bus.emit(EventType.ON_STATUS_APPLY,
                                        target=self._owner, modifier=modifier,
                                        stack_policy=stack_policy)

    def remove_modifier(self, modifier: "StatModifier") -> None:
        old_spd = self.get_total_stat(StatType.SPD) if self._owner else 0.0
        self.active_modifiers = [m for m in self.active_modifiers if m is not modifier]
        if modifier.stat_type == StatType.SPD:
            self._recalc_spd_if_changed(old_spd)

    def remove_modifier_by_source(self, source: str) -> None:
        """移除所有来源为 source 且可驱散的修饰器。"""
        old_spd = self.get_total_stat(StatType.SPD) if self._owner else 0.0
        self.active_modifiers = [
            m for m in self.active_modifiers
            if m.source != source or not m.dispellable
        ]
        self._recalc_spd_if_changed(old_spd)

    def purge_source(self, source: str) -> None:
        """移除所有 source 匹配的修饰器 (无视 dispellable，用于卸载装备)。"""
        old_spd = self.get_total_stat(StatType.SPD) if self._owner else 0.0
        self.active_modifiers = [
            m for m in self.active_modifiers if m.source != source
        ]
        self._recalc_spd_if_changed(old_spd)

    def remove_modifier_by_tag(self, tag: str) -> None:
        """移除所有包含 tag 且可驱散的修饰器。"""
        old_spd = self.get_total_stat(StatType.SPD) if self._owner else 0.0
        self.active_modifiers = [
            m for m in self.active_modifiers
            if tag not in m.tags or not m.dispellable
        ]
        self._recalc_spd_if_changed(old_spd)

    def get_base_stat(self, stat_type: StatType) -> float:
        base = self._base_stats.get(stat_type, 0.0)
        if self._owner is not None and hasattr(self._owner, "light_cone"):
            lc = getattr(self._owner, "light_cone", None)
            if lc is not None:
                if stat_type == StatType.HP:
                    base += lc.base_hp
                elif stat_type == StatType.ATK:
                    base += lc.base_atk
                elif stat_type == StatType.DEF:
                    base += lc.base_def
        return base

    def get_total_stat(self, stat_type: StatType) -> float:
        base_val = self.get_base_stat(stat_type)
        flat_total = 0.0
        percent_total = 0.0
        for mod in self.active_modifiers:
            if mod.stat_type == stat_type:
                if mod.modifier_type == StatModifierType.FLAT:
                    flat_total += mod.value
                else:
                    percent_total += mod.value
        if stat_type in self._MULTIPLICATIVE_STATS:
            return base_val * (1.0 + percent_total) + flat_total
        else:
            return base_val + percent_total + flat_total

    def get_mitigation_values(self) -> list[float]:
        """返回所有 DMG_MITIGATION 修饰器的独立数值（累乘用，非累加）。"""
        from core.enums import StatType as ST
        return [m.value for m in self.active_modifiers if m.stat_type == ST.DMG_MITIGATION]

    def get_element_dmg_bonus(self, element: "ElementType") -> float:
        """返回通用增伤 + 元素专属增伤的总和。"""
        from core.enums import _ELEMENT_DMG_STAT, StatType as ST
        generic = self.get_total_stat(ST.DMG_BONUS)
        elem_stat = _ELEMENT_DMG_STAT.get(element)
        elemental = self.get_total_stat(elem_stat) if elem_stat else 0.0
        return generic + elemental

    def find_dispellable(self) -> list["StatModifier"]:
        """返回所有可驱散的修饰器 (dispellable=True)。"""
        return [m for m in self.active_modifiers if m.dispellable]


def stats_defaults() -> dict[StatType, float]:
    """返回所有 StatType → 0.0 的字典，供各实体初始化时覆盖非零值。"""
    return {stat: 0.0 for stat in StatType}

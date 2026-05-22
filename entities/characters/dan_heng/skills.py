from __future__ import annotations
"""DanHeng Skills — 普攻140% / 战技325%+减速 / 终结技480%(+144%减速) / 天赋RES_PEN / 秘技ATK+40%。"""

from core.enums import ActionType, DamageType, StatType, StatModifierType
from entities.base import StatModifier
from entities.characters.template_character.skills import (
    TemplateBasicAttack,
    TemplateSkill,
    TemplateUltimate,
)


def _target_is_slowed(target) -> bool:
    for mod in target.stats.active_modifiers:
        if mod.stat_type == StatType.SPD and mod.value < 0:
            return True
    return False


class DanHengBasicAttack(TemplateBasicAttack):
    skill_multiplier = 1.40
    energy_gain = 20

    def execute(self, target, state) -> tuple[int, bool, float, bool]:
        e1_applied = False
        if getattr(self.owner, "_has_e1", False):
            if target.max_hp > 0 and target.hp / target.max_hp >= 0.5:
                mod = StatModifier(StatType.CRIT_RATE, StatModifierType.FLAT, 0.12, source="E1")
                self.owner.stats.apply_modifier(mod, "refresh")
                e1_applied = True

        wind_applied = False
        if getattr(self.owner, "_has_wind", False) and _target_is_slowed(target):
            mod = StatModifier(StatType.DMG_BONUS, StatModifierType.FLAT, 0.40, source="Trace_Wind")
            self.owner.stats.apply_modifier(mod, "refresh")
            wind_applied = True

        dmg, crit, tough, brk = state.execute_action(
            self.owner, self.action_type, target,
            self.skill_multiplier, damage_type=self.damage_type,
        )

        if e1_applied:
            self.owner.stats.remove_modifier_by_source("E1")
        if wind_applied:
            self.owner.stats.remove_modifier_by_source("Trace_Wind")

        return (dmg, crit, tough, brk)


class DanHengSkill(TemplateSkill):
    skill_multiplier = 3.25
    energy_gain = 30

    def execute(self, target, state) -> tuple[int, bool, float, bool]:
        e1_applied = False
        if getattr(self.owner, "_has_e1", False):
            if target.max_hp > 0 and target.hp / target.max_hp >= 0.5:
                mod = StatModifier(StatType.CRIT_RATE, StatModifierType.FLAT, 0.12, source="E1")
                self.owner.stats.apply_modifier(mod, "refresh")
                e1_applied = True

        dmg, crit, tough, brk = state.execute_action(
            self.owner, self.action_type, target,
            self.skill_multiplier, damage_type=self.damage_type,
        )

        if e1_applied:
            self.owner.stats.remove_modifier_by_source("E1")

        if crit and target.is_alive:
            slow_value = -0.20 if getattr(self.owner, "_has_e6", False) else -0.12
            applied, ch = state.try_apply_debuff(
                self.owner, target, base_chance=1.0, debuff_type="",
            )
            if applied:
                slow_mod = StatModifier(
                    StatType.SPD, StatModifierType.PERCENT, slow_value,
                    source="DanHeng_Slow", duration=2, dispellable=True,
                )
                target.stats.apply_modifier(slow_mod, "refresh")

        return (dmg, crit, tough, brk)


class DanHengUltimate(TemplateUltimate):
    skill_multiplier = 4.80
    slow_bonus = 1.44
    energy_gain = 5

    def execute(self, target, state) -> tuple[int, bool, float, bool]:
        multiplier = self.skill_multiplier
        if _target_is_slowed(target):
            multiplier += self.slow_bonus

        e1_applied = False
        if getattr(self.owner, "_has_e1", False):
            if target.max_hp > 0 and target.hp / target.max_hp >= 0.5:
                mod = StatModifier(StatType.CRIT_RATE, StatModifierType.FLAT, 0.12, source="E1")
                self.owner.stats.apply_modifier(mod, "refresh")
                e1_applied = True

        dmg, crit, tough, brk = state.execute_action(
            self.owner, self.action_type, target,
            multiplier, damage_type=self.damage_type,
        )

        if e1_applied:
            self.owner.stats.remove_modifier_by_source("E1")

        return (dmg, crit, tough, brk)


class DanHengTalent:
    action_type = ActionType.TALENT
    skill_multiplier = 0.0

    def __init__(self, owner) -> None:
        self.owner = owner
        self.res_pen_amount = 0.45

    def on_combat_start(self, state) -> None:
        if state.event_bus is None:
            return
        self._state_ref = state
        from core.events import EventType
        state.event_bus.subscribe(EventType.ACTION_START, self._on_action_start)
        state.event_bus.subscribe(EventType.AFTER_ACTION, self._on_after_action)
        state.event_bus.subscribe(EventType.TURN_START, self._on_turn_start)
        state.event_bus.subscribe(EventType.ON_KILL, self._on_kill)

    def _on_action_start(self, **kwargs) -> None:
        unit = kwargs.get("unit")
        target = kwargs.get("target")
        if unit is None or target is None:
            return
        if unit == self.owner or target != self.owner:
            return
        if not getattr(unit, "is_alive", False):
            return
        if self.owner._talent_cooldown_remaining > 0:
            return
        self.owner._talent_buff_active = True
        mod = StatModifier(
            StatType.RES_PEN, StatModifierType.FLAT, self.res_pen_amount,
            source="DanHeng_Talent", duration=None, dispellable=False,
        )
        self.owner.stats.apply_modifier(mod, "refresh")

    def _on_after_action(self, **kwargs) -> None:
        unit = kwargs.get("unit")
        if unit != self.owner:
            return

        if self.owner._talent_buff_active:
            self.owner._talent_buff_active = False
            self.owner.stats.remove_modifier_by_source("DanHeng_Talent")
            cd = 1 if getattr(self.owner, "_has_e2", False) else 2
            self.owner._talent_cooldown_remaining = cd

        if getattr(self.owner, "_has_shadow", False):
            import random
            if random.random() < 0.50:
                mod = StatModifier(
                    StatType.SPD, StatModifierType.PERCENT, 0.20,
                    source="DanHeng_Shadow", duration=2, dispellable=False,
                )
                self.owner.stats.apply_modifier(mod, "refresh")

    def _on_turn_start(self, **kwargs) -> None:
        unit = kwargs.get("unit")
        if unit != self.owner:
            return

        if self.owner._talent_cooldown_remaining > 0:
            self.owner._talent_cooldown_remaining -= 1

        if getattr(self.owner, "_has_dragon_hide", False):
            hp_pct = self.owner.hp / self.owner.max_hp if self.owner.max_hp > 0 else 0.0
            if hp_pct <= 0.5 and not self.owner._dragon_hide_active:
                self.owner.external_taunt_factor *= 0.5
                self.owner._dragon_hide_active = True
            elif hp_pct > 0.5 and self.owner._dragon_hide_active:
                self.owner.external_taunt_factor /= 0.5
                self.owner._dragon_hide_active = False

    def _on_kill(self, **kwargs) -> None:
        source = kwargs.get("source")
        if source != self.owner:
            return
        if not getattr(self.owner, "_has_e4", False):
            return
        if kwargs.get("action_type") != ActionType.ULTIMATE:
            return
        self.owner.advance_action(1.0)

    def execute(self, target, state) -> tuple[int, bool, float, bool]:
        return (0, False, 0.0, False)


class DanHengTechnique:
    action_type = ActionType.TALENT
    skill_multiplier = 0.0

    def __init__(self, owner) -> None:
        self.owner = owner

    def on_combat_start(self, state) -> None:
        if state.event_bus is None:
            return
        from core.events import EventType
        state.event_bus.subscribe(EventType.BATTLE_START, self._on_battle_start)

    def _on_battle_start(self, **kwargs) -> None:
        mod = StatModifier(
            StatType.ATK, StatModifierType.PERCENT, 0.40,
            source="DanHeng_Technique", duration=3, dispellable=False,
        )
        self.owner.stats.apply_modifier(mod, "refresh")

    def execute(self, target, state) -> tuple[int, bool, float, bool]:
        return (0, False, 0.0, False)


class DanHengElationSkill:
    """欢愉测试技能: Elation 伤害体系验证。"""
    action_type = ActionType.TALENT
    skill_multiplier = 2.0
    damage_type = DamageType.ELATION

    def __init__(self, owner) -> None:
        self.owner = owner

    def execute(self, target, state) -> tuple[int, bool, float, bool]:
        return state.execute_action(
            self.owner, self.action_type, target,
            self.skill_multiplier, damage_type=self.damage_type,
        )

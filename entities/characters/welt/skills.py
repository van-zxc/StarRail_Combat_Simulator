from __future__ import annotations
"""Welt Skills — 普攻140% / 战技5段弹射90%+减速 / 终结技180%群攻+禁锢+失重 / 天赋附加伤害+失重被动 / 秘技禁锢。"""

import random

from core.enums import ActionType, DamageType, StatType, StatModifierType, ElementType
from core.targeting import TargetManager
from entities.base import StatModifier, ToughnessDamagePacket, HitPacket
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


def _apply_verdict(owner) -> bool:
    if not getattr(owner, "_has_verdict", False):
        owner.stats.remove_modifier_by_source("Welt_Verdict")
        return False
    owner.stats.remove_modifier_by_source("Welt_Verdict")
    ehr = owner.stats.get_total_stat(StatType.EFFECT_HIT_RATE)
    if ehr > 0.40:
        excess = ehr - 0.40
        steps = int(excess / 0.10)
        bonus = min(steps * 0.20, 0.80)
        if bonus > 0:
            mod = StatModifier(StatType.ATK, StatModifierType.PERCENT, bonus, source="Welt_Verdict", dispellable=True)
            owner.stats.apply_modifier(mod, "refresh")
            return True
    return False


def _apply_weightless_to_enemy(enemy) -> None:
    enemy.weightless_remaining_turns = 2
    enemy.weightless_hit_count = 0
    def_mod = StatModifier(StatType.DEF, StatModifierType.PERCENT, -0.40, source="Welt_Weightless_DEF", dispellable=False)
    spd_mod = StatModifier(StatType.SPD, StatModifierType.PERCENT, -0.05, source="Welt_Weightless_SPD", dispellable=False)
    enemy.stats.apply_modifier(def_mod, "refresh")
    enemy.stats.apply_modifier(spd_mod, "refresh")


class WeltBasicAttack(TemplateBasicAttack):
    skill_multiplier = 1.40
    energy_gain = 20

    def execute(self, target, state) -> tuple[int, bool, float, bool]:
        _apply_verdict(self.owner)
        dmg, crit, tough, brk = state.execute_action(
            self.owner, self.action_type, target,
            self.skill_multiplier, damage_type=self.damage_type,
        )

        total_dmg = dmg
        add_mult = 0.0
        if getattr(self.owner, "_has_judgement", False):
            add_mult += self.skill_multiplier * 0.80
        if add_mult > 0 and target.is_alive:
            ad, _, _, _ = state.execute_action(
                self.owner, ActionType.TALENT, target, add_mult,
                damage_type=DamageType.ADDITIONAL_DMG, element_override=ElementType.IMAGINARY,
            )
            total_dmg += ad

        if _target_is_slowed(target) and target.is_alive:
            talent_mult = getattr(self.owner._skills.get("talent"), "skill_multiplier", 0.75)
            td, _, _, _ = state.execute_action(
                self.owner, ActionType.TALENT, target, talent_mult,
                damage_type=DamageType.ADDITIONAL_DMG, element_override=ElementType.IMAGINARY,
            )
            total_dmg += td
            if getattr(self.owner, "_has_e2", False):
                self.owner.gain_energy(3)

        return (total_dmg, crit, tough, brk)


class WeltSkill(TemplateSkill):
    skill_multiplier = 0.90
    energy_gain = 30

    def execute(self, target, state) -> tuple[int, bool, float, bool]:
        _apply_verdict(self.owner)

        total_dmg = 0
        total_crit = False
        total_tough = 0.0
        total_brk = False

        num_bounces = 5
        base_chance = 0.80 + (0.35 if getattr(self.owner, "_has_e4", False) else 0.0)

        talent_mult = getattr(self.owner._skills.get("talent"), "skill_multiplier", 0.75)

        e6_crit = getattr(self.owner, "_has_e6", False)

        for i in range(num_bounces):
            t = TargetManager.select_target(self.owner, state.alive_enemies, is_bounce=True)
            if t is None:
                continue

            tp = ToughnessDamagePacket(amount=10.0, element=ElementType.IMAGINARY)

            if e6_crit and _target_is_slowed(t):
                mod_cr = StatModifier(StatType.CRIT_RATE, StatModifierType.FLAT, 0.30,
                                      source="Welt_E6_CR", dispellable=False)
                mod_cd = StatModifier(StatType.CRIT_DMG, StatModifierType.FLAT, 0.60,
                                      source="Welt_E6_CD", dispellable=False)
                self.owner.stats.apply_modifier(mod_cr, "refresh")
                self.owner.stats.apply_modifier(mod_cd, "refresh")

            dmg, crit, tough, brk = state.execute_action(
                self.owner, self.action_type, t,
                self.skill_multiplier, damage_type=self.damage_type,
                toughness_packet=tp,
                skip_action_resources=(i > 0),
            )

            if e6_crit and _target_is_slowed(t):
                self.owner.stats.remove_modifier_by_source("Welt_E6_CR")
                self.owner.stats.remove_modifier_by_source("Welt_E6_CD")

            total_dmg += dmg
            total_crit = total_crit or crit
            total_tough += tough
            total_brk = total_brk or brk

            if t.is_alive:
                applied, _ = state.try_apply_debuff(self.owner, t, base_chance=base_chance)
                if applied:
                    slow_mod = StatModifier(
                        StatType.SPD, StatModifierType.PERCENT, -0.10,
                        source="Welt_Slow", duration=2, dispellable=True,
                    )
                    t.stats.apply_modifier(slow_mod, "refresh")

            add_mult = 0.0
            if getattr(self.owner, "_has_judgement", False):
                add_mult += self.skill_multiplier * 1.20

            if add_mult > 0 and t.is_alive:
                ad, _, _, _ = state.execute_action(
                    self.owner, ActionType.TALENT, t, add_mult,
                    damage_type=DamageType.ADDITIONAL_DMG, element_override=ElementType.IMAGINARY,
                )
                total_dmg += ad

            if _target_is_slowed(t) and t.is_alive:
                td, _, _, _ = state.execute_action(
                    self.owner, ActionType.TALENT, t, talent_mult,
                    damage_type=DamageType.ADDITIONAL_DMG, element_override=ElementType.IMAGINARY,
                )
                total_dmg += td
                if getattr(self.owner, "_has_e2", False):
                    self.owner.gain_energy(3)

        return (total_dmg, total_crit, total_tough, total_brk)


class WeltUltimate(TemplateUltimate):
    skill_multiplier = 1.80
    energy_gain = 5

    def execute(self, target, state) -> tuple[int, bool, float, bool]:
        _apply_verdict(self.owner)

        enemies = state.alive_enemies
        total_dmg = 0
        total_crit = False
        total_tough = 0.0
        total_brk = False

        talent_mult = getattr(self.owner._skills.get("talent"), "skill_multiplier", 0.75)
        e6_crit = getattr(self.owner, "_has_e6", False)

        for enemy in enemies:
            if e6_crit and _target_is_slowed(enemy):
                mod_cr = StatModifier(StatType.CRIT_RATE, StatModifierType.FLAT, 0.30,
                                      source="Welt_E6_CR", dispellable=False)
                mod_cd = StatModifier(StatType.CRIT_DMG, StatModifierType.FLAT, 0.60,
                                      source="Welt_E6_CD", dispellable=False)
                self.owner.stats.apply_modifier(mod_cr, "refresh")
                self.owner.stats.apply_modifier(mod_cd, "refresh")

            dmg, crit, tough, brk = state.execute_action(
                self.owner, self.action_type, enemy,
                self.skill_multiplier, damage_type=self.damage_type,
            )

            if e6_crit and _target_is_slowed(enemy):
                self.owner.stats.remove_modifier_by_source("Welt_E6_CR")
                self.owner.stats.remove_modifier_by_source("Welt_E6_CD")

            total_dmg += dmg
            total_crit = total_crit or crit
            total_tough += tough
            total_brk = total_brk or brk

            if enemy.is_alive:
                applied, _ = state.try_apply_debuff(self.owner, enemy, base_chance=1.0)
                if applied:
                    from entities.base import CCStatus
                    enemy.cc_statuses.append(CCStatus("Imprison", remaining_turns=1))
                    spd_mod_imprison = StatModifier(
                        StatType.SPD, StatModifierType.PERCENT, -0.10,
                        source="Welt_Imprison_Slow", duration=1, dispellable=True,
                    )
                    enemy.stats.apply_modifier(spd_mod_imprison, "refresh")
                    enemy.delay_action(0.15)

                _apply_weightless_to_enemy(enemy)

            if _target_is_slowed(enemy) and enemy.is_alive:
                td, _, _, _ = state.execute_action(
                    self.owner, ActionType.TALENT, enemy, talent_mult,
                    damage_type=DamageType.ADDITIONAL_DMG, element_override=ElementType.IMAGINARY,
                )
                total_dmg += td
                if getattr(self.owner, "_has_e2", False):
                    self.owner.gain_energy(3)

        # A6 Verdict: extra energy on ultimate
        if getattr(self.owner, "_has_verdict", False):
            self.owner.gain_energy(5)

        return (total_dmg, total_crit, total_tough, total_brk)


class WeltTalent:
    action_type = ActionType.TALENT
    skill_multiplier = 0.75

    def __init__(self, owner) -> None:
        self.owner = owner

    def on_combat_start(self, state) -> None:
        if state.event_bus is None:
            return
        self._state_ref = state
        from core.events import EventType
        state.event_bus.subscribe(EventType.ON_DAMAGE_DEALT, self._on_damage_dealt)
        state.event_bus.subscribe(EventType.TURN_START, self._on_turn_start)
        state.event_bus.subscribe(EventType.BATTLE_START, self._on_battle_start)
        state.event_bus.subscribe(EventType.AFTER_ACTION, self._on_after_action_e1)

    def _on_after_action_e1(self, **kwargs) -> None:
        if not getattr(self.owner, "_has_e1", False):
            return
        unit = kwargs.get("unit")
        target = kwargs.get("target")
        if unit != self.owner or target is None or not target.is_alive:
            return
        action_type = kwargs.get("action_type")
        if action_type not in (ActionType.SKILL, ActionType.ULTIMATE):
            return
        has_weightless = any(
            m.source == "Welt_Weightless_DEF"
            for m in getattr(target, "stats", object).active_modifiers
        )
        if not has_weightless:
            return
        has_mark = any(
            m.source == "Welt_E1_HitMark"
            for m in getattr(target, "stats", object).active_modifiers
        )
        if has_mark:
            return
        mark = StatModifier(StatType.HP, StatModifierType.FLAT, 0,
                            source="Welt_E1_HitMark", dispellable=False)
        target.stats.apply_modifier(mark, "refresh")
        ult = self.owner._skills.get("ultimate")
        ult_mult = ult.skill_multiplier if ult else 1.80
        pursue_mult = ult_mult * 0.50
        self._state_ref.execute_action(
            self.owner, ActionType.TALENT, target, pursue_mult,
            damage_type=DamageType.ADDITIONAL_DMG,
            element_override=ElementType.IMAGINARY,
        )

    def _on_damage_dealt(self, **kwargs) -> None:
        target = kwargs.get("target")
        source = kwargs.get("source")
        if target is None or source is None:
            return
        if not hasattr(target, "weightless_remaining_turns"):
            return

        if target.weightless_remaining_turns > 0 and target.weightless_hit_count < 8:
            target.delay_action(0.04)
            target.weightless_hit_count += 1

        if getattr(self.owner, "_has_retribution", False) and target.weightless_remaining_turns > 0:
            if hasattr(source, "stats"):
                existing = [m for m in source.stats.active_modifiers if m.source == "Welt_Retribution"]
                current_val = existing[0].value if existing else 0.0
                if current_val < 1.0:
                    mod = StatModifier(StatType.DMG_BONUS, StatModifierType.FLAT, 0.10,
                                       source="Welt_Retribution", duration=2, dispellable=False)
                    source.stats.apply_modifier(mod, "add_stacks")
                    for m in source.stats.active_modifiers:
                        if m.source == "Welt_Retribution":
                            m.duration = 2

    def _on_turn_start(self, **kwargs) -> None:
        unit = kwargs.get("unit")
        if unit is None:
            return

        if hasattr(unit, "weightless_remaining_turns") and unit.weightless_remaining_turns > 0:
            unit.weightless_hit_count = 0
            unit.weightless_remaining_turns -= 1
            if unit.weightless_remaining_turns <= 0:
                unit.stats.remove_modifier_by_source("Welt_Weightless_DEF")
                unit.stats.remove_modifier_by_source("Welt_Weightless_SPD")

        if unit == self.owner:
            _apply_verdict(self.owner)

    def _on_battle_start(self, **kwargs) -> None:
        if getattr(self.owner, "_has_retribution", False):
            self.owner.gain_energy(30)

    def execute(self, target, state) -> tuple[int, bool, float, bool]:
        return (0, False, 0.0, False)


class WeltTechnique:
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
        engine = kwargs.get("engine")
        if engine is None:
            return
        state = engine.state
        for enemy in state.alive_enemies:
            from entities.base import CCStatus
            enemy.cc_statuses.append(CCStatus("Imprison", remaining_turns=1))
            spd_mod = StatModifier(
                StatType.SPD, StatModifierType.PERCENT, -0.10,
                source="Welt_Technique_Slow", duration=1, dispellable=True,
            )
            enemy.stats.apply_modifier(spd_mod, "refresh")
            enemy.delay_action(0.20)

    def execute(self, target, state) -> tuple[int, bool, float, bool]:
        return (0, False, 0.0, False)

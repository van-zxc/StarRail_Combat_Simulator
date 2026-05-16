"""Himeko Skills — 普攻140% / 战技250%+100%扩散 / 终结技276%群攻+击杀回能 / 天赋充能FUA / 秘技易伤。"""

from __future__ import annotations

import random

from core.enums import ActionType, DamageType, StatType, StatModifierType, ElementType
from core.targeting import TargetManager
from entities.base import StatModifier, ToughnessDamagePacket, DoTStatus
from entities.characters.template_character.skills import (
    TemplateBasicAttack,
    TemplateSkill,
    TemplateUltimate,
)


def _target_has_burn(target) -> bool:
    for dot in getattr(target, "dot_statuses", []):
        if dot.element == ElementType.FIRE:
            return True
    return False


def _apply_beacon(owner) -> bool:
    if not getattr(owner, "_has_beacon", False):
        return False
    hp_pct = owner.hp / owner.max_hp if owner.max_hp > 0 else 0.0
    if hp_pct >= 0.80:
        mod = StatModifier(StatType.CRIT_RATE, StatModifierType.FLAT, 0.15, source="Trace_Beacon", dispellable=True)
        owner.stats.apply_modifier(mod, "refresh")
        return True
    else:
        owner.stats.remove_modifier_by_source("Trace_Beacon")
    return False


def _cleanup_beacon(owner) -> None:
    owner.stats.remove_modifier_by_source("Trace_Beacon")


def _apply_e2(owner, target) -> bool:
    if not getattr(owner, "_has_e2", False):
        return False
    if target.max_hp > 0 and target.hp / target.max_hp <= 0.5:
        mod = StatModifier(StatType.DMG_BONUS, StatModifierType.FLAT, 0.15, source="E2")
        owner.stats.apply_modifier(mod, "refresh")
        return True
    return False


def _cleanup_e2(owner) -> None:
    owner.stats.remove_modifier_by_source("E2")


def _apply_a4_burn(owner, target) -> bool:
    if not getattr(owner, "_has_scorch", False):
        return False
    if _target_has_burn(target):
        mod = StatModifier(StatType.DMG_BONUS, StatModifierType.FLAT, 0.20, source="Trace_Scorch")
        owner.stats.apply_modifier(mod, "refresh")
        return True
    return False


def _cleanup_a4(owner) -> None:
    owner.stats.remove_modifier_by_source("Trace_Scorch")


class HimekoBasicAttack(TemplateBasicAttack):
    skill_multiplier = 1.40
    energy_gain = 20

    def execute(self, target, state) -> tuple[int, bool, float, bool]:
        self.owner._killing_action = "basic"
        beacon = _apply_beacon(self.owner)
        e2 = _apply_e2(self.owner, target)

        dmg, crit, tough, brk = state.execute_action(
            self.owner, self.action_type, target,
            self.skill_multiplier, damage_type=self.damage_type,
        )

        if beacon:
            _cleanup_beacon(self.owner)
        if e2:
            _cleanup_e2(self.owner)
        return (dmg, crit, tough, brk)


class HimekoSkill(TemplateSkill):
    skill_multiplier = 2.50
    skill_adjacent = 1.00
    energy_gain = 30

    def execute(self, target, state) -> tuple[int, bool, float, bool]:
        self.owner._killing_action = "skill"

        blast_targets = TargetManager.select_blast(state.alive_enemies, target)
        total_dmg = 0
        total_crit = False
        total_tough = 0.0
        total_brk = False

        beacon = _apply_beacon(self.owner)

        for t in blast_targets:
            mult = self.skill_multiplier if t is target else self.skill_adjacent
            tp = ToughnessDamagePacket(
                amount=20.0 if t is target else 10.0, element=ElementType.FIRE)
            e2 = _apply_e2(self.owner, t)
            a4 = _apply_a4_burn(self.owner, t)

            dmg, crit, tough, brk = state.execute_action(
                self.owner, self.action_type, t,
                mult, damage_type=self.damage_type,
                toughness_packet=tp,
            )
            total_dmg += dmg
            total_crit = total_crit or crit
            total_tough += tough
            total_brk = total_brk or brk

            if e2:
                _cleanup_e2(self.owner)
            if a4:
                _cleanup_a4(self.owner)

        if beacon:
            _cleanup_beacon(self.owner)
        return (total_dmg, total_crit, total_tough, total_brk)


class HimekoUltimate(TemplateUltimate):
    skill_multiplier = 2.76
    energy_gain = 5

    def execute(self, target, state) -> tuple[int, bool, float, bool]:
        self.owner._killing_action = "ultimate"

        enemies = state.alive_enemies
        total_dmg = 0
        total_crit = False
        total_tough = 0.0
        total_brk = False

        beacon = _apply_beacon(self.owner)

        for t in enemies:
            e2 = _apply_e2(self.owner, t)
            dmg, crit, tough, brk = state.execute_action(
                self.owner, self.action_type, t,
                self.skill_multiplier, damage_type=self.damage_type,
            )
            total_dmg += dmg
            total_crit = total_crit or crit
            total_tough += tough
            total_brk = total_brk or brk
            if e2:
                _cleanup_e2(self.owner)

            if not t.is_alive:
                self.owner.gain_energy(5)

        if getattr(self.owner, "_has_e6", False):
            extra_candidates = [e for e in state.alive_enemies if e.is_alive]
            hits = min(2, len(extra_candidates))
            if hits > 0:
                chosen = random.sample(extra_candidates, hits)
                for t in chosen:
                    e2 = _apply_e2(self.owner, t)
                    dmg, crit, tough, brk = state.execute_action(
                        self.owner, self.action_type, t,
                        self.skill_multiplier * 0.40, damage_type=self.damage_type,
                    )
                    total_dmg += dmg
                    total_crit = total_crit or crit
                    if e2:
                        _cleanup_e2(self.owner)

        if beacon:
            _cleanup_beacon(self.owner)
        return (total_dmg, total_crit, total_tough, total_brk)


class HimekoTalent:
    action_type = ActionType.TALENT
    skill_multiplier = 1.75

    def __init__(self, owner) -> None:
        self.owner = owner

    def on_combat_start(self, state) -> None:
        if state.event_bus is None:
            return
        self._state_ref = state
        from core.events import EventType
        state.event_bus.subscribe(EventType.ON_WEAKNESS_BREAK, self._on_weakness_break)
        state.event_bus.subscribe(EventType.AFTER_ACTION, self._on_after_action)
        state.event_bus.subscribe(EventType.BATTLE_START, self._on_battle_start)

    def _on_battle_start(self, **kwargs) -> None:
        self.owner._charge_count = 1

    def _on_weakness_break(self, **kwargs) -> None:
        self.owner._charge_count = min(self.owner._charge_count + 1, self.owner._charge_max)

        breaker = kwargs.get("breaker")
        if breaker == self.owner and getattr(self.owner, "_has_e4", False):
            if self.owner._killing_action == "skill":
                self.owner._charge_count = min(self.owner._charge_count + 1, self.owner._charge_max)

    def _on_after_action(self, **kwargs) -> None:
        unit = kwargs.get("unit")
        if unit is None:
            return
        if not getattr(unit, "is_alive", False):
            return

        target = kwargs.get("target")
        if getattr(self.owner, "_has_starfire", False) and unit == self.owner and target is not None:
            applied, _ = self._state_ref.try_apply_debuff(
                self.owner, target, base_chance=0.50, debuff_type="Burn",
            )
            if applied and target.is_alive:
                dot = DoTStatus(
                    source_character=self.owner, element=ElementType.FIRE,
                    dot_multiplier=0.30, duration=2,
                )
                if hasattr(target, "apply_dot"):
                    target.apply_dot(dot)
                else:
                    target.dot_statuses.append(dot)

        if self.owner._charge_count >= self.owner._charge_max:
            self.owner._charge_count = 0
            self._state_ref.grant_follow_up_action(self.owner, self)

            if getattr(self.owner, "_has_e1", False):
                mod = StatModifier(
                    StatType.SPD, StatModifierType.PERCENT, 0.20,
                    source="Himeko_E1", duration=2, dispellable=False,
                )
                self.owner.stats.apply_modifier(mod, "refresh")

    def execute(self, target, state) -> tuple[int, bool, float, bool]:
        self.owner._killing_action = "talent_fua"

        enemies = state.alive_enemies
        total_dmg = 0
        total_crit = False
        total_tough = 0.0
        total_brk = False

        beacon = _apply_beacon(self.owner)

        for t in enemies:
            e2 = _apply_e2(self.owner, t)
            dmg, crit, tough, brk = state.execute_action(
                self.owner, ActionType.FOLLOW_UP, t,
                self.skill_multiplier, damage_type=DamageType.DIRECT,
                tags={"attack", "follow_up"}, follow_up_energy_type=2,
                toughness_packet=ToughnessDamagePacket(
                    amount=10.0, element=ElementType.FIRE),
            )
            total_dmg += dmg
            total_crit = total_crit or crit
            total_tough += tough
            total_brk = total_brk or brk
            if e2:
                _cleanup_e2(self.owner)

        if beacon:
            _cleanup_beacon(self.owner)
        return (total_dmg, total_crit, total_tough, total_brk)


class HimekoTechnique:
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
            applied, _ = state.try_apply_debuff(self.owner, enemy, base_chance=1.0)
            if applied:
                mod = StatModifier(
                    StatType.FIRE_VULN, StatModifierType.FLAT, 0.10,
                    source="Himeko_Technique", duration=2, dispellable=True,
                )
                enemy.stats.apply_modifier(mod, "refresh")

    def execute(self, target, state) -> tuple[int, bool, float, bool]:
        return (0, False, 0.0, False)

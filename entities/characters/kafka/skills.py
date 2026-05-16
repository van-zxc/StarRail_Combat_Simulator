"""Kafka Skills — 普攻140% / 战技200%+75%扩散+DoT引爆 / 终结技96%群攻+触电+全引爆 / 天赋FUA+触电 / 秘技触电。"""

from __future__ import annotations

from core.enums import ActionType, DamageType, StatType, StatModifierType, ElementType
from core.targeting import TargetManager
from entities.base import StatModifier, DoTStatus, ToughnessDamagePacket
from entities.characters.template_character.skills import (
    TemplateBasicAttack,
    TemplateSkill,
    TemplateUltimate,
)


def _detonate_dots(state, target, detonate_pct) -> int:
    total = 0
    for dot in target.dot_statuses:
        source = dot.source_character
        if not source.is_alive:
            continue
        base_dmg = int(source.atk * dot.dot_multiplier * dot.stacks * detonate_pct)
        if base_dmg <= 0:
            continue
        dmg, _, _, _ = state.execute_action(
            character=source,
            action_type=ActionType.BASIC_ATTACK,
            target=target,
            skill_multiplier=0.0,
            damage_type=DamageType.DOT,
            base_damage_override=base_dmg,
            element_override=dot.element,
        )
        total += dmg
    return total


def _apply_shock(owner, target, state, base_chance=1.0, dot_multiplier=None, duration=None) -> bool:
    if dot_multiplier is None:
        dot_multiplier = 5.169 if getattr(owner, "_has_e6", False) else 3.6069
    if duration is None:
        duration = 3 if getattr(owner, "_has_e6", False) else 2

    applied, _ = state.try_apply_debuff(owner, target, base_chance=base_chance, debuff_type="Shock")
    if applied:
        dot = DoTStatus(source_character=owner, element=ElementType.LIGHTNING,
                         dot_multiplier=dot_multiplier, duration=duration)
        if hasattr(target, "apply_dot"):
            target.apply_dot(dot)
        else:
            target.dot_statuses.append(dot)
        return True
    return False


class KafkaBasicAttack(TemplateBasicAttack):
    skill_multiplier = 1.40
    energy_gain = 20

    def execute(self, target, state) -> tuple[int, bool, float, bool]:
        self.owner._killing_action = "basic"
        dmg, crit, tough, brk = state.execute_action(
            self.owner, self.action_type, target,
            self.skill_multiplier, damage_type=self.damage_type,
        )
        return (dmg, crit, tough, brk)


class KafkaSkill(TemplateSkill):
    skill_multiplier = 2.0
    skill_adjacent = 0.75
    detonate_primary = 0.825
    detonate_adjacent = 0.55
    energy_gain = 30

    def execute(self, target, state) -> tuple[int, bool, float, bool]:
        self.owner._killing_action = "skill"

        blast_targets = TargetManager.select_blast(state.alive_enemies, target)
        total_dmg = 0
        total_crit = False
        total_tough = 0.0
        total_brk = False

        for t in blast_targets:
            is_primary = t is target
            mult = self.skill_multiplier if is_primary else self.skill_adjacent
            tp = ToughnessDamagePacket(
                amount=20.0 if is_primary else 10.0, element=ElementType.LIGHTNING)

            dmg, crit, tough, brk = state.execute_action(
                self.owner, self.action_type, t,
                mult, damage_type=self.damage_type,
                toughness_packet=tp,
            )
            total_dmg += dmg
            total_crit = total_crit or crit
            total_tough += tough
            total_brk = total_brk or brk

            if t.is_alive and t.dot_statuses:
                pct = self.detonate_primary if is_primary else self.detonate_adjacent
                det_dmg = _detonate_dots(state, t, pct)
                total_dmg += det_dmg

        return (total_dmg, total_crit, total_tough, total_brk)


class KafkaUltimate(TemplateUltimate):
    skill_multiplier = 0.96
    detonate_pct = 1.30
    energy_gain = 5

    def execute(self, target, state) -> tuple[int, bool, float, bool]:
        self.owner._killing_action = "ultimate"

        enemies = state.alive_enemies
        total_dmg = 0
        total_crit = False
        total_tough = 0.0
        total_brk = False

        for enemy in enemies:
            dmg, crit, tough, brk = state.execute_action(
                self.owner, self.action_type, enemy,
                self.skill_multiplier, damage_type=self.damage_type,
            )
            total_dmg += dmg
            total_crit = total_crit or crit
            total_tough += tough
            total_brk = total_brk or brk

            if enemy.is_alive:
                _apply_shock(self.owner, enemy, state, base_chance=1.0)

            if enemy.is_alive and enemy.dot_statuses:
                det_dmg = _detonate_dots(state, enemy, self.detonate_pct)
                total_dmg += det_dmg

        if getattr(self.owner, "_has_thorn", False):
            self.owner._talent_count = min(self.owner._talent_count + 1, self.owner._talent_max)

        return (total_dmg, total_crit, total_tough, total_brk)


class KafkaTalent:
    action_type = ActionType.TALENT
    skill_multiplier = 1.89

    def __init__(self, owner) -> None:
        self.owner = owner

    def on_combat_start(self, state) -> None:
        if state.event_bus is None:
            return
        self._state_ref = state
        from core.events import EventType
        state.event_bus.subscribe(EventType.AFTER_ACTION, self._on_after_action)
        state.event_bus.subscribe(EventType.TURN_END, self._on_turn_end)
        state.event_bus.subscribe(EventType.TURN_START, self._on_turn_start_a2)
        state.event_bus.subscribe(EventType.ON_KILL, self._on_kill_a4)

    def _on_turn_start_a2(self, **kwargs) -> None:
        unit = kwargs.get("unit")
        if unit is None:
            return
        if not hasattr(unit, "stats"):
            return
        if unit == self.owner:
            return
        if not getattr(self.owner, "_has_torture", False):
            return
        unit.stats.remove_modifier_by_source("Kafka_Torture")
        ehr = unit.stats.get_total_stat(StatType.EFFECT_HIT_RATE)
        if ehr >= 0.75:
            mod = StatModifier(StatType.ATK, StatModifierType.PERCENT, 1.0,
                              source="Kafka_Torture", dispellable=False)
            unit.stats.apply_modifier(mod, "refresh")

    def _on_after_action(self, **kwargs) -> None:
        unit = kwargs.get("unit")
        target = kwargs.get("target")
        if unit is None or target is None:
            return
        if unit == self.owner:
            return
        if not hasattr(unit, "stats"):
            return
        if not hasattr(target, "dot_statuses"):
            return
        if self.owner._talent_count <= 0:
            return

        self.owner._talent_count -= 1
        self._state_ref.grant_follow_up_action(self.owner, self)

    def _on_turn_end(self, **kwargs) -> None:
        unit = kwargs.get("unit")
        if unit == self.owner:
            self.owner._talent_count = min(self.owner._talent_count + 1, self.owner._talent_max)

    def _on_kill_a4(self, **kwargs) -> None:
        target = kwargs.get("target")
        if target is None:
            return
        if not getattr(self.owner, "_has_plunder", False):
            return
        if not hasattr(target, "dot_statuses"):
            return
        has_shock = any(d.element == ElementType.LIGHTNING for d in target.dot_statuses)
        if has_shock:
            self.owner.gain_energy(5)

    def execute(self, target, state) -> tuple[int, bool, float, bool]:
        self.owner._killing_action = "talent_fua"

        total_dmg = 0
        total_crit = False
        total_tough = 0.0
        total_brk = False

        dmg, crit, tough, brk = state.execute_action(
            self.owner, ActionType.FOLLOW_UP, target,
            self.skill_multiplier, damage_type=DamageType.DIRECT,
            tags={"attack", "follow_up"}, follow_up_energy_type=2,
            toughness_packet=ToughnessDamagePacket(
                amount=10.0, element=ElementType.LIGHTNING),
        )
        total_dmg += dmg
        total_crit = total_crit or crit
        total_tough += tough
        total_brk = total_brk or brk

        if target.is_alive:
            _apply_shock(self.owner, target, state)

        if target.is_alive and getattr(self.owner, "_has_e1", False):
            applied, _ = state.try_apply_debuff(self.owner, target, base_chance=1.0)
            if applied:
                mod = StatModifier(StatType.VULNERABILITY, StatModifierType.FLAT, 0.30,
                                  source="Kafka_E1", duration=2, dispellable=True)
                target.stats.apply_modifier(mod, "refresh")

        if target.is_alive and getattr(self.owner, "_has_thorn", False):
            det_dmg = _detonate_dots(state, target, 0.80)
            total_dmg += det_dmg

        return (total_dmg, total_crit, total_tough, total_brk)


class KafkaTechnique:
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
            dmg, _, _, _ = state.execute_action(
                self.owner, ActionType.TALENT, enemy,
                0.50, damage_type=DamageType.DIRECT, element_override=ElementType.LIGHTNING,
            )
            if enemy.is_alive:
                _apply_shock(self.owner, enemy, state)

    def execute(self, target, state) -> tuple[int, bool, float, bool]:
        return (0, False, 0.0, False)

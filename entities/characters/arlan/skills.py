from __future__ import annotations
"""Arlan Skills — 普攻2段30%+70% / 战技HP消耗不耗SP / 终结技3段扩散 / 天赋HP损失→DMG / 秘技AoE。

来源: 1008_arlan.json
"""

import math

from core.enums import ActionType, DamageType, StatType, StatModifierType, ElementType
from core.targeting import TargetManager
from entities.base import StatModifier, ToughnessDamagePacket, HitPacket
from entities.characters.template_character.skills import (
    TemplateBasicAttack,
    TemplateSkill,
    TemplateUltimate,
)

_HIT_SPLIT_BASIC = [0.30, 0.70]
_HIT_SPLIT_ULT = [0.30, 0.10, 0.60]


def _arlan_talent_bonus(owner) -> float:
    """Talent: DMG_BONUS = (1 - hp/max_hp) × talent_max%. """
    hp_ratio = owner.hp / max(owner.max_hp, 1)
    lost_ratio = max(0.0, 1.0 - hp_ratio)
    talent = owner._skills.get("talent")
    if talent is None:
        return 0.0
    return lost_ratio * talent.talent_max


def _apply_talent_dmg(owner) -> None:
    owner.stats.remove_modifier_by_source("Arlan_Talent")
    bonus = _arlan_talent_bonus(owner)
    if bonus > 0:
        mod = StatModifier(StatType.DMG_BONUS, StatModifierType.FLAT, bonus,
                           source="Arlan_Talent", dispellable=False)
        owner.stats.apply_modifier(mod, "refresh")


def _remove_talent_dmg(owner) -> None:
    owner.stats.remove_modifier_by_source("Arlan_Talent")


class ArlanBasicAttack(TemplateBasicAttack):
    skill_multiplier = 1.40
    damage_type = DamageType.DIRECT
    energy_gain = 20

    def execute(self, target, state) -> tuple[int, bool, float, bool]:
        _apply_talent_dmg(self.owner)
        toughness_base = getattr(self.owner, "_toughness_map", {}).get(
            ActionType.BASIC_ATTACK, 10.0)
        hits = [
            HitPacket(target=target, skill_multiplier=self.skill_multiplier * r,
                      toughness_packet=ToughnessDamagePacket(
                          amount=toughness_base * r, element=ElementType.LIGHTNING))
            for r in _HIT_SPLIT_BASIC
        ]
        results = state.execute_multi_hit(self.owner, hits, self.action_type, self.damage_type)
        _remove_talent_dmg(self.owner)
        total_dmg = sum(r[0] for r in results)
        any_crit = any(r[1] for r in results)
        total_tough = sum(r[2] for r in results)
        any_brk = any(r[3] for r in results)
        return (total_dmg, any_crit, total_tough, any_brk)


class ArlanSkill(TemplateSkill):
    skill_multiplier = 3.0
    damage_type = DamageType.DIRECT
    energy_gain = 30
    hp_cost_ratio = 0.15

    def execute(self, target, state) -> tuple[int, bool, float, bool]:
        # HP cost
        hp_cost = int(self.owner.max_hp * self.hp_cost_ratio)
        if self.owner.hp > hp_cost:
            self.owner.take_damage(hp_cost, bypass_shield=True)
        else:
            self.owner.hp = 1

        # E1: HP ≤ 50% → +10% skill DMG
        e1_bonus = 0.0
        if getattr(self.owner, "_has_e1", False) and self.owner.hp <= self.owner.max_hp * 0.5:
            e1_bonus = 0.10

        _apply_talent_dmg(self.owner)
        if e1_bonus > 0:
            mod = StatModifier(StatType.DMG_BONUS, StatModifierType.FLAT, e1_bonus,
                               source="Arlan_E1", dispellable=False)
            self.owner.stats.apply_modifier(mod, "refresh")

        dmg, crit, tough, brk = state.execute_action(
            self.owner, self.action_type, target,
            self.skill_multiplier, damage_type=self.damage_type,
            skip_action_resources=True,
        )
        self.owner.gain_energy(30.0)

        _remove_talent_dmg(self.owner)
        self.owner.stats.remove_modifier_by_source("Arlan_E1")

        # E2: self-dispel after skill
        if getattr(self.owner, "_has_e2", False):
            state.dispel_one(self.owner)

        return (dmg, crit, tough, brk)


class ArlanUltimate(TemplateUltimate):
    skill_multiplier = 3.84
    skill_adjacent = 1.92
    damage_type = DamageType.DIRECT
    energy_gain = 5

    def execute(self, target, state) -> tuple[int, bool, float, bool]:
        _apply_talent_dmg(self.owner)

        # E6: HP ≤ 50% → +20% ult DMG, adjacent = primary
        e6_bonus = 0.0
        e6_uniform = False
        if getattr(self.owner, "_has_e6", False) and self.owner.hp <= self.owner.max_hp * 0.5:
            e6_bonus = 0.20
            e6_uniform = True

        if e6_bonus > 0:
            mod = StatModifier(StatType.DMG_BONUS, StatModifierType.FLAT, e6_bonus,
                               source="Arlan_E6", dispellable=False)
            self.owner.stats.apply_modifier(mod, "refresh")

        blast_targets = TargetManager.select_blast(state.alive_enemies, target)
        toughness_base = getattr(self.owner, "_toughness_map", {}).get(
            ActionType.ULTIMATE, 20.0)
        total_dmg = 0
        total_crit = False
        total_tough = 0.0
        total_brk = False

        for t in blast_targets:
            is_primary = t is target
            mult = self.skill_multiplier if (is_primary or e6_uniform) else self.skill_adjacent
            ult_hits = [
                HitPacket(target=t, skill_multiplier=mult * r,
                          toughness_packet=ToughnessDamagePacket(
                              amount=toughness_base * r, element=ElementType.LIGHTNING))
                for r in _HIT_SPLIT_ULT
            ]
            results = state.execute_multi_hit(self.owner, ult_hits, self.action_type, self.damage_type)
            total_dmg += sum(r[0] for r in results)
            total_crit = total_crit or any(r[1] for r in results)
            total_tough += sum(r[2] for r in results)
            total_brk = total_brk or any(r[3] for r in results)

        _remove_talent_dmg(self.owner)
        self.owner.stats.remove_modifier_by_source("Arlan_E6")

        # E2: self-dispel after ult
        if getattr(self.owner, "_has_e2", False):
            state.dispel_one(self.owner)

        return (total_dmg, total_crit, total_tough, total_brk)


class ArlanTalent:
    action_type = ActionType.TALENT
    skill_multiplier = 0.0
    talent_max = 0.9

    def __init__(self, owner) -> None:
        self.owner = owner

    def on_combat_start(self, state) -> None:
        if state.event_bus is None:
            return
        self._state_ref = state
        from core.events import EventType
        state.event_bus.subscribe(EventType.ON_KILL, self._on_kill_revival)
        state.event_bus.subscribe(EventType.BATTLE_START, self._on_battle_start)
        state.event_bus.subscribe(EventType.BEFORE_DEATH, self._on_before_death_e4)
        state.event_bus.subscribe(EventType.TURN_START, self._on_turn_start_e4)

    def _on_battle_start(self, **kwargs) -> None:
        # Repel (A3): HP ≤ 50% → nullify direct damage
        if getattr(self.owner, "_has_repel", False):
            if self.owner.hp <= self.owner.max_hp * 0.5:
                self.owner._nullify_direct_dmg = True

        # E4: 2-turn death-prevention buff
        if getattr(self.owner, "_has_e4", False):
            self.owner._e4_active = True
            self.owner._e4_remaining = 2

    def _on_turn_start_e4(self, **kwargs) -> None:
        unit = kwargs.get("unit")
        if unit is not self.owner:
            return
        if getattr(self.owner, "_e4_active", False):
            self.owner._e4_remaining -= 1
            if self.owner._e4_remaining <= 0:
                self.owner._e4_active = False

    def _on_kill_revival(self, **kwargs) -> None:
        if not getattr(self.owner, "_has_revival", False):
            return
        if self.owner.hp <= self.owner.max_hp * 0.3:
            heal = int(self.owner.max_hp * 0.20)
            self.owner.receive_heal(heal)

    def _on_before_death_e4(self, **kwargs) -> None:
        target = kwargs.get("target") or kwargs.get("unit")
        if target is not self.owner:
            return
        if not getattr(self.owner, "_e4_active", False):
            return
        self.owner.hp = int(self.owner.max_hp * 0.25)
        self.owner._e4_active = False
        self.owner._before_death_emitted = False  # 复活后重置标记

    def execute(self, target, state) -> tuple[int, bool, float, bool]:
        return (0, False, 0.0, False)


class ArlanTechnique:
    action_type = ActionType.TALENT
    skill_multiplier = 0.80
    damage_type = DamageType.DIRECT

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
            state.execute_action(
                self.owner, ActionType.TALENT, enemy,
                self.skill_multiplier, damage_type=self.damage_type,
            )

    def execute(self, target, state) -> tuple[int, bool, float, bool]:
        return (0, False, 0.0, False)

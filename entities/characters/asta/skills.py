from __future__ import annotations
"""Asta Skills — 普攻+灼烧 / 战技弹射5段 / 终结技全体加速 / 天赋蓄能ATK buff / 秘技AoE。

来源: 1009_asta.json
"""

from core.enums import ActionType, DamageType, StatType, StatModifierType, ElementType
from core.targeting import TargetManager
from entities.base import StatModifier, DoTStatus, ToughnessDamagePacket
from entities.characters.template_character.skills import (
    TemplateBasicAttack,
    TemplateSkill,
    TemplateUltimate,
)


def _apply_charge_buff(owner, allies) -> None:
    """Apply ATK buff to all party members based on charge count."""
    from entities.characters.base import BaseCharacter
    for ally in allies:
        ally.stats.remove_modifier_by_source("Asta_Charge_ATK")
    for mod in owner.stats.active_modifiers:
        if mod.source == "Asta_Charge_DEF":
            owner.stats.remove_modifier(mod)
    owner.stats.remove_modifier_by_source("Asta_E4_ERR")

    count = owner._charge_count
    talent = owner._skills.get("talent")
    if talent is None or count <= 0:
        return

    atk_pct = count * talent.charge_atk_pct
    for ally in allies:
        atk_mod = StatModifier(StatType.ATK, StatModifierType.PERCENT, atk_pct,
                               source="Asta_Charge_ATK", dispellable=False)
        ally.stats.apply_modifier(atk_mod, "refresh")

    if getattr(owner, "_has_constellation", False):
        def_pct = count * talent.constellation_def_pct
        if def_pct > 0:
            def_mod = StatModifier(StatType.DEF, StatModifierType.PERCENT, def_pct,
                                   source="Asta_Charge_DEF", dispellable=False)
            owner.stats.apply_modifier(def_mod, "refresh")

    if getattr(owner, "_has_e4", False) and count >= 2:
        err_mod = StatModifier(StatType.ERR, StatModifierType.FLAT, 0.15,
                               source="Asta_E4_ERR", dispellable=False)
        owner.stats.apply_modifier(err_mod, "refresh")


def _add_charges(owner, hit_targets: set) -> int:
    """Add charges based on unique hit targets + fire weakness bonus."""
    total = 0
    for t in hit_targets:
        if owner._charge_count < owner._charge_max:
            owner._charge_count += 1
            total += 1
        if hasattr(t, "weaknesses") and ElementType.FIRE in t.weaknesses:
            if owner._charge_count < owner._charge_max:
                owner._charge_count += 1
                total += 1
    return total


class AstaBasicAttack(TemplateBasicAttack):
    skill_multiplier = 1.40
    damage_type = DamageType.DIRECT
    energy_gain = 20

    def execute(self, target, state) -> tuple[int, bool, float, bool]:
        dmg, crit, tough, brk = state.execute_action(
            self.owner, self.action_type, target,
            self.skill_multiplier, damage_type=self.damage_type,
        )

        hit_targets: set = set()
        if target.is_alive:
            hit_targets.add(target)

        if hit_targets:
            added = _add_charges(self.owner, hit_targets)
            if added > 0:
                _apply_charge_buff(self.owner, state.characters)

        if target.is_alive and getattr(self.owner, "_has_spark", False):
            self._apply_spark_burn(target, state)

        return (dmg, crit, tough, brk)

    def _apply_spark_burn(self, target, state) -> None:
        applied, _ = state.try_apply_debuff(self.owner, target, base_chance=0.80, debuff_type="Burn")
        if applied:
            dot = DoTStatus(source_character=self.owner, element=ElementType.FIRE,
                            dot_multiplier=0.50, duration=3)
            if hasattr(target, "apply_dot"):
                target.apply_dot(dot)
            else:
                target.dot_statuses.append(dot)


class AstaSkill(TemplateSkill):
    skill_multiplier = 0.625
    damage_type = DamageType.DIRECT
    energy_gain = 30

    def execute(self, target, state) -> tuple[int, bool, float, bool]:
        num_bounces = 6 if getattr(self.owner, "_has_e1", False) else 5

        total_dmg = 0
        total_crit = False
        total_tough = 0.0
        total_brk = False
        hit_targets: set = set()

        for i in range(num_bounces):
            t = TargetManager.select_target(self.owner, state.alive_enemies, is_bounce=True)
            if t is None:
                continue

            tp = ToughnessDamagePacket(amount=10.0, element=ElementType.FIRE)

            dmg, crit, tough, brk = state.execute_action(
                self.owner, self.action_type, t,
                self.skill_multiplier, damage_type=self.damage_type,
                toughness_packet=tp,
                skip_action_resources=(i > 0),
            )
            total_dmg += dmg
            total_crit = total_crit or crit
            total_tough += tough
            total_brk = total_brk or brk

            if t.is_alive:
                hit_targets.add(t)

        if hit_targets:
            added = _add_charges(self.owner, hit_targets)
            if added > 0:
                _apply_charge_buff(self.owner, state.characters)

        return (total_dmg, total_crit, total_tough, total_brk)


class AstaUltimate(TemplateUltimate):
    skill_multiplier = 0.0
    damage_type = DamageType.DIRECT
    energy_gain = 5
    spd_buff = 57.0
    spd_duration = 2

    def execute(self, target, state) -> tuple[int, bool, float, bool]:
        for ally in state.characters:
            mod = StatModifier(StatType.SPD, StatModifierType.FLAT, self.spd_buff,
                               source="Asta_Ult_SPD", duration=self.spd_duration,
                               dispellable=False)
            ally.stats.apply_modifier(mod, "refresh")

        if getattr(self.owner, "_has_e2", False):
            self.owner._e2_skip_decay = True

        return (0, False, 0.0, False)


class AstaTalent:
    action_type = ActionType.TALENT
    skill_multiplier = 0.0
    charge_atk_pct = 0.175
    constellation_def_pct = 0.06
    decay_amount = 3

    def __init__(self, owner) -> None:
        self.owner = owner

    def on_combat_start(self, state) -> None:
        if state.event_bus is None:
            return
        self._state_ref = state
        from core.events import EventType
        state.event_bus.subscribe(EventType.TURN_START, self._on_turn_start)
        state.event_bus.subscribe(EventType.BATTLE_START, self._apply_ignite_aura)
        state.event_bus.subscribe(EventType.UNIT_DOWNED, self._remove_ignite_aura)

    def _on_turn_start(self, **kwargs) -> None:
        unit = kwargs.get("unit")
        if unit is not self.owner:
            return
        self.owner._turn_count += 1
        if self.owner._turn_count < 2:
            return

        if getattr(self.owner, "_e2_skip_decay", False):
            self.owner._e2_skip_decay = False
        else:
            decay = self.decay_amount - (1 if getattr(self.owner, "_has_e6", False) else 0)
            self.owner._charge_count = max(0, self.owner._charge_count - decay)

        _apply_charge_buff(self.owner, self._state_ref.characters)

    def _apply_ignite_aura(self, **kwargs) -> None:
        if not getattr(self.owner, "_has_ignite", False):
            return
        source = "Asta_Trace_Ignite"
        for ally in self._state_ref.characters:
            ally.stats.remove_modifier_by_source(source)
            mod = StatModifier(StatType.FIRE_DMG_BONUS, StatModifierType.FLAT, 0.18,
                               source=source, dispellable=False)
            ally.stats.apply_modifier(mod, "no_stack")

    def _remove_ignite_aura(self, **kwargs) -> None:
        target = kwargs.get("target") or kwargs.get("unit")
        if target is not self.owner:
            return
        source = "Asta_Trace_Ignite"
        for ally in self._state_ref.characters:
            ally.stats.remove_modifier_by_source(source)

    def execute(self, target, state) -> tuple[int, bool, float, bool]:
        return (0, False, 0.0, False)


class AstaTechnique:
    action_type = ActionType.TALENT
    skill_multiplier = 0.50
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

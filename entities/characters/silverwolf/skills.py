from __future__ import annotations
"""Silver Wolf Skills — 普攻140% / 战技弱点植入+全属性抗性降低 / 终结技群攻+减防 / 天赋缺陷植入 / 秘技群攻。

来源: 1006_silverwolf.json (Enhanced 11006xx)
"""

import random

from core.enums import ActionType, DamageType, StatType, StatModifierType, ElementType
from entities.base import StatModifier, ImplantedWeakness, ToughnessDamagePacket
from entities.characters.template_character.skills import (
    TemplateBasicAttack,
    TemplateSkill,
    TemplateUltimate,
)


_BUG_TYPE_MAP: list[tuple[str, StatType, StatModifierType, str]] = [
    ("ATK", StatType.ATK, StatModifierType.PERCENT, "SilverWolf_Bug_ATK"),
    ("DEF", StatType.DEF, StatModifierType.PERCENT, "SilverWolf_Bug_DEF"),
    ("SPD", StatType.SPD, StatModifierType.PERCENT, "SilverWolf_Bug_SPD"),
]


def _count_enemy_debuffs(enemy) -> int:
    count = 0
    if hasattr(enemy, "stats") and hasattr(enemy.stats, "active_modifiers"):
        for mod in enemy.stats.active_modifiers:
            if mod.value < 0:
                count += 1
    if hasattr(enemy, "cc_statuses"):
        count += len(enemy.cc_statuses)
    if hasattr(enemy, "dot_statuses"):
        count += len(enemy.dot_statuses)
    return count


def _apply_e6_bonus(owner, enemy) -> bool:
    """E6: per debuff on enemy +20% DMG_BONUS, max 100%. Returns True if bonus applied."""
    if not getattr(owner, "_has_e6", False):
        return False
    owner.stats.remove_modifier_by_source("SilverWolf_E6")
    count = _count_enemy_debuffs(enemy)
    bonus = min(count * 0.20, 1.00)
    if bonus > 0:
        mod = StatModifier(StatType.DMG_BONUS, StatModifierType.FLAT, bonus,
                           source="SilverWolf_E6", dispellable=False)
        owner.stats.apply_modifier(mod, "refresh")
        return True
    return False


def _remove_e6_bonus(owner) -> None:
    owner.stats.remove_modifier_by_source("SilverWolf_E6")


def _apply_annotation(owner) -> None:
    """A6: EHR→ATK conversion. Every 10% EHR → 10% ATK, max 50%."""
    owner.stats.remove_modifier_by_source("SilverWolf_Annotation")
    if not getattr(owner, "_has_annotation", False):
        return
    ehr = owner.stats.get_total_stat(StatType.EFFECT_HIT_RATE)
    steps = int(ehr / 0.10)
    bonus = min(steps * 0.10, 0.50)
    if bonus > 0:
        mod = StatModifier(StatType.ATK, StatModifierType.PERCENT, bonus,
                           source="SilverWolf_Annotation", dispellable=False)
        owner.stats.apply_modifier(mod, "refresh")


def _apply_random_bug(owner, target, state, atk_down, def_down, spd_down, base_chance, bug_duration) -> bool:
    applied, _ = state.try_apply_debuff(owner, target, base_chance=base_chance)
    if not applied:
        return False

    bug_type, stat_type, mod_type, source = random.choice(_BUG_TYPE_MAP)
    if bug_type == "ATK":
        value = atk_down
    elif bug_type == "DEF":
        value = def_down
    else:
        value = spd_down

    mod = StatModifier(stat_type, mod_type, -value, source=source,
                       duration=bug_duration, dispellable=True)
    target.stats.apply_modifier(mod, "refresh")
    return True


def _implant_weakness(owner, target, state, base_chance, element, res_reduction, duration,
                      alltype_res_value, alltype_res_duration) -> None:
    applied, _ = state.try_apply_debuff(owner, target, base_chance=base_chance)
    if applied:
        has_natural = element in target.weaknesses
        if target.implanted_weakness is not None and target.implanted_weakness.source is owner:
            old_elem = target.implanted_weakness.element
            if old_elem in target.element_res_modifiers:
                del target.element_res_modifiers[old_elem]

        target.implanted_weakness = ImplantedWeakness(
            element=element,
            source=owner,
            remaining_turns=duration,
            res_reduction=res_reduction if not has_natural else 0.0,
        )

        if not has_natural and res_reduction > 0:
            target.element_res_modifiers[element] = target.element_res_modifiers.get(element, 0.0) - res_reduction

    if alltype_res_value > 0:
        applied2, _ = state.try_apply_debuff(owner, target, base_chance=1.0)
        if applied2:
            mod = StatModifier(StatType.RES, StatModifierType.FLAT, -alltype_res_value,
                               source="SilverWolf_AllTypeRES", duration=alltype_res_duration,
                               dispellable=True)
            target.stats.apply_modifier(mod, "refresh")


class SilverWolfBasicAttack(TemplateBasicAttack):
    skill_multiplier = 1.40
    damage_type = DamageType.DIRECT
    energy_gain = 20

    def execute(self, target, state) -> tuple[int, bool, float, bool]:
        _apply_annotation(self.owner)
        _apply_e6_bonus(self.owner, target)
        result = state.execute_action(
            self.owner, self.action_type, target,
            self.skill_multiplier, damage_type=self.damage_type,
        )
        _remove_e6_bonus(self.owner)
        return result


class SilverWolfSkill(TemplateSkill):
    skill_multiplier = 2.45
    damage_type = DamageType.DIRECT
    energy_gain = 30

    implant_base_chance = 1.40
    res_reduction = 0.20
    res_duration = 3
    alltype_res_value = 0.1425
    alltype_res_duration = 2

    def execute(self, target, state) -> tuple[int, bool, float, bool]:
        _apply_annotation(self.owner)
        first_ally = state.characters[0]
        element_to_implant = first_ally.element

        _apply_e6_bonus(self.owner, target)
        dmg, crit, tough, brk = state.execute_action(
            self.owner, self.action_type, target,
            self.skill_multiplier, damage_type=self.damage_type,
        )
        _remove_e6_bonus(self.owner)

        if target.is_alive:
            _implant_weakness(
                self.owner, target, state,
                base_chance=self.implant_base_chance,
                element=element_to_implant,
                res_reduction=self.res_reduction,
                duration=self.res_duration,
                alltype_res_value=self.alltype_res_value,
                alltype_res_duration=self.alltype_res_duration,
            )

        return (dmg, crit, tough, brk)


class SilverWolfUltimate(TemplateUltimate):
    skill_multiplier = 4.56
    damage_type = DamageType.DIRECT
    energy_gain = 5

    def_reduce_base_chance = 1.40
    def_reduce_value = 0.495
    def_reduce_duration = 3

    def execute(self, target, state) -> tuple[int, bool, float, bool]:
        _apply_annotation(self.owner)
        total_dmg = 0
        total_crit = False
        total_tough = 0.0
        total_brk = False

        for enemy in state.alive_enemies:
            _apply_e6_bonus(self.owner, enemy)
            dmg, crit, tough, brk = state.execute_action(
                self.owner, self.action_type, enemy,
                self.skill_multiplier, damage_type=self.damage_type,
            )
            _remove_e6_bonus(self.owner)
            total_dmg += dmg
            total_crit = total_crit or crit
            total_tough += tough
            total_brk = total_brk or brk

            if enemy.is_alive:
                self._apply_def_reduce(enemy, state)
                self._apply_e1_energy(enemy, state)
                total_dmg += self._apply_e4_additional(enemy, state)

        return (total_dmg, total_crit, total_tough, total_brk)

    def _apply_def_reduce(self, enemy, state) -> None:
        applied, _ = state.try_apply_debuff(self.owner, enemy, base_chance=self.def_reduce_base_chance)
        if applied:
            mod = StatModifier(StatType.DEF, StatModifierType.PERCENT, -self.def_reduce_value,
                               source="SilverWolf_Ult_DEF", duration=self.def_reduce_duration,
                               dispellable=True)
            enemy.stats.apply_modifier(mod, "refresh")

    def _apply_e1_energy(self, enemy, state) -> None:
        if not getattr(self.owner, "_has_e1", False):
            return
        count = min(_count_enemy_debuffs(enemy), 5)
        if count > 0:
            self.owner.gain_energy(float(count * 7))

    def _apply_e4_additional(self, enemy, state) -> int:
        if not getattr(self.owner, "_has_e4", False):
            return 0
        count = min(_count_enemy_debuffs(enemy), 5)
        add_total = 0
        for _ in range(count):
            add_dmg, _, _, _ = state.execute_action(
                character=self.owner,
                action_type=ActionType.ULTIMATE,
                target=enemy,
                skill_multiplier=0.0,
                damage_type=DamageType.ADDITIONAL_DMG,
                base_damage_override=int(self.owner.atk * 0.20),
                element_override=ElementType.QUANTUM,
            )
            add_total += add_dmg
        return add_total


class SilverWolfTalent:
    action_type = ActionType.TALENT
    skill_multiplier = 0.0

    bug_atk_down = 0.125
    bug_def_down = 0.15
    bug_spd_down = 0.075
    bug_base_chance = 1.20
    bug_duration = 3

    def __init__(self, owner) -> None:
        self.owner = owner

    def _get_bug_duration(self) -> int:
        return self.bug_duration + (1 if getattr(self.owner, "_has_generate", False) else 0)

    def on_combat_start(self, state) -> None:
        if state.event_bus is None:
            return
        self._state_ref = state
        from core.events import EventType
        state.event_bus.subscribe(EventType.AFTER_ACTION, self._on_after_action)
        state.event_bus.subscribe(EventType.ON_WEAKNESS_BREAK, self._on_weakness_break)
        state.event_bus.subscribe(EventType.ON_KILL, self._on_kill)
        state.event_bus.subscribe(EventType.TURN_START, self._on_turn_start)
        state.event_bus.subscribe(EventType.BATTLE_START, self._on_battle_start)
        state.event_bus.subscribe(EventType.WAVE_START, self._on_wave_start)
        state.event_bus.subscribe(EventType.ON_BEFORE_HIT, self._on_enemy_before_hit_e2)

    def _on_battle_start(self, **kwargs) -> None:
        self._apply_inject_sp()
        _apply_annotation(self.owner)
        self._apply_e2_vuln(kwargs.get("engine"))

    def _on_wave_start(self, **kwargs) -> None:
        self._apply_e2_vuln(kwargs.get("engine"))

    def _apply_inject_sp(self) -> None:
        if not getattr(self.owner, "_has_inject", False):
            return
        if self._state_ref is not None and hasattr(self._state_ref, "skill_points"):
            self._state_ref.skill_points = min(self._state_ref.skill_points + 1, self._state_ref.max_sp)

    def _apply_e2_vuln(self, engine) -> None:
        if not getattr(self.owner, "_has_e2", False) or engine is None:
            return
        for enemy in engine.state.alive_enemies:
            mod = StatModifier(StatType.VULNERABILITY, StatModifierType.FLAT, 0.20,
                               source="SilverWolf_E2_Vuln", dispellable=False)
            enemy.stats.apply_modifier(mod, "refresh")

    def _on_enemy_before_hit_e2(self, **kwargs) -> None:
        if not getattr(self.owner, "_has_e2", False):
            return
        source = kwargs.get("source")
        target = kwargs.get("target")
        if source is None or target is None:
            return
        if not hasattr(source, "stats") or not hasattr(target, "stats"):
            return
        from entities.characters.base import BaseCharacter
        if not isinstance(target, BaseCharacter):
            return
        if not hasattr(source, "dot_statuses"):
            return
        _apply_random_bug(
            self.owner, source, self._state_ref,
            self.bug_atk_down, self.bug_def_down, self.bug_spd_down,
            self.bug_base_chance, self._get_bug_duration(),
        )

    def _on_after_action(self, **kwargs) -> None:
        unit = kwargs.get("unit")
        target = kwargs.get("target")
        if unit is None or target is None:
            return
        if unit != self.owner:
            return
        if not target.is_alive:
            return
        if not hasattr(target, "stats"):
            return

        _apply_random_bug(
            self.owner, target, self._state_ref,
            self.bug_atk_down, self.bug_def_down, self.bug_spd_down,
            self.bug_base_chance, self._get_bug_duration(),
        )

    def _on_weakness_break(self, **kwargs) -> None:
        if not getattr(self.owner, "_has_generate", False):
            return
        target = kwargs.get("target")
        if target is None or not target.is_alive:
            return
        if not hasattr(target, "stats"):
            return

        _apply_random_bug(
            self.owner, target, self._state_ref,
            self.bug_atk_down, self.bug_def_down, self.bug_spd_down,
            1.0, self._get_bug_duration(),
        )

    def _on_kill(self, **kwargs) -> None:
        source = kwargs.get("source")
        target = kwargs.get("target")
        if target is None:
            return
        if target.implanted_weakness is None:
            return
        if target.implanted_weakness.source is not self.owner:
            return

        iw = target.implanted_weakness
        alive_enemies = [e for e in self._state_ref.alive_enemies
                         if e is not target and e.implanted_weakness is None]
        if not alive_enemies:
            return

        new_target = alive_enemies[0]
        new_target.implanted_weakness = ImplantedWeakness(
            element=iw.element,
            source=self.owner,
            remaining_turns=iw.remaining_turns,
            res_reduction=iw.res_reduction,
        )
        if iw.res_reduction > 0:
            new_target.element_res_modifiers[iw.element] = (
                new_target.element_res_modifiers.get(iw.element, 0.0) - iw.res_reduction
            )

    def _on_turn_start(self, **kwargs) -> None:
        unit = kwargs.get("unit")
        if unit is None:
            return
        if not hasattr(unit, "implanted_weakness"):
            return
        if unit.implanted_weakness is None:
            return

        iw = unit.implanted_weakness
        if iw.source is not self.owner:
            return

        iw.remaining_turns -= 1
        if iw.remaining_turns <= 0:
            if iw.element in unit.element_res_modifiers:
                del unit.element_res_modifiers[iw.element]
            unit.implanted_weakness = None

        if getattr(self.owner, "_has_inject", False) and unit is self.owner:
            self._apply_inject_sp()

        if unit is self.owner:
            _apply_annotation(self.owner)

    def execute(self, target, state) -> tuple[int, bool, float, bool]:
        return (0, False, 0.0, False)


class SilverWolfTechnique:
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
        toughness_pkt = ToughnessDamagePacket(
            amount=10.0, element=ElementType.QUANTUM, ignores_weakness=True,
        )
        for enemy in state.alive_enemies:
            state.execute_action(
                self.owner, ActionType.TALENT, enemy,
                self.skill_multiplier, damage_type=self.damage_type,
                toughness_packet=toughness_pkt,
            )

    def execute(self, target, state) -> tuple[int, bool, float, bool]:
        return (0, False, 0.0, False)

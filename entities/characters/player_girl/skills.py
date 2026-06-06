from __future__ import annotations
"""PlayerGirl Skills — 普攻140% / 战技156.25%扩散 / 终结技二选一(525%单/315%+189%扩散) / 天赋击破+ATK / 秘技回血。"""

from core.enums import ActionType, DamageType, StatType, StatModifierType, ElementType
from core.targeting import TargetManager
from entities.base import StatModifier, ToughnessDamagePacket
from entities.characters.template_character.skills import (
    TemplateBasicAttack,
    TemplateSkill,
    TemplateUltimate,
)


class PlayerGirlBasicAttack(TemplateBasicAttack):
    skill_multiplier = 1.40
    energy_gain = 20

    def execute(self, target, state) -> tuple[int, bool, float, bool]:
        e4_applied = False
        if getattr(self.owner, "_has_e4", False):
            if getattr(target, "current_toughness", 1.0) <= 0:
                mod = StatModifier(StatType.CRIT_RATE, StatModifierType.FLAT, 0.25, source="E4")
                self.owner.stats.apply_modifier(mod, "refresh")
                e4_applied = True

        dmg, crit, tough, brk = state.execute_action(
            self.owner, self.action_type, target,
            self.skill_multiplier, damage_type=self.damage_type,
        )

        if e4_applied:
            self.owner.stats.remove_modifier_by_source("E4")

        return (dmg, crit, tough, brk)


class PlayerGirlSkill(TemplateSkill):
    skill_multiplier = 1.5625
    energy_gain = 30

    def execute(self, target, state) -> tuple[int, bool, float, bool]:
        blast_targets = TargetManager.select_blast(state.alive_enemies, target)
        total_dmg = 0
        total_crit = False
        total_tough = 0.0
        total_brk = False

        has_a6 = getattr(self.owner, "_has_fighting_spirit", False)

        for t in blast_targets:
            is_primary = t is target
            tp = ToughnessDamagePacket(
                amount=20.0 if is_primary else 10.0, element=ElementType.PHYSICAL)

            e4_applied = False
            if getattr(self.owner, "_has_e4", False):
                if getattr(t, "current_toughness", 1.0) <= 0:
                    mod = StatModifier(StatType.CRIT_RATE, StatModifierType.FLAT, 0.25, source="E4")
                    self.owner.stats.apply_modifier(mod, "refresh")
                    e4_applied = True

            a6_applied = False
            if has_a6 and t is target:
                mod = StatModifier(StatType.DMG_BONUS, StatModifierType.FLAT, 0.25, source="Trace_A6")
                self.owner.stats.apply_modifier(mod, "refresh")
                a6_applied = True

            dmg, crit, tough, brk = state.execute_action(
                self.owner, self.action_type, t,
                self.skill_multiplier, damage_type=self.damage_type,
                toughness_packet=tp,
            )
            total_dmg += dmg
            total_crit = total_crit or crit
            total_tough += tough
            total_brk = total_brk or brk

            if e4_applied:
                self.owner.stats.remove_modifier_by_source("E4")
            if a6_applied:
                self.owner.stats.remove_modifier_by_source("Trace_A6")

        return (total_dmg, total_crit, total_tough, total_brk)


class PlayerGirlUltimate(TemplateUltimate):
    skill_multiplier = 5.25
    blast_primary = 3.15
    blast_adjacent = 1.89
    energy_gain = 5

    def execute(self, target, state) -> tuple[int, bool, float, bool]:
        enemies = state.alive_enemies
        has_a6 = getattr(self.owner, "_has_fighting_spirit", False)

        if len(enemies) <= 1:
            e4_applied = False
            if getattr(self.owner, "_has_e4", False):
                if getattr(target, "current_toughness", 1.0) <= 0:
                    mod = StatModifier(StatType.CRIT_RATE, StatModifierType.FLAT, 0.25, source="E4")
                    self.owner.stats.apply_modifier(mod, "refresh")
                    e4_applied = True

            dmg, crit, tough, brk = state.execute_action(
                self.owner, self.action_type, target,
                self.skill_multiplier, damage_type=self.damage_type,
                toughness_packet=ToughnessDamagePacket(
                    amount=30.0, element=ElementType.PHYSICAL),
            )

            if e4_applied:
                self.owner.stats.remove_modifier_by_source("E4")

            return (dmg, crit, tough, brk)

        blast_targets = TargetManager.select_blast(enemies, target)
        total_dmg = 0
        total_crit = False
        total_tough = 0.0
        total_brk = False

        for t in blast_targets:
            is_primary = t is target
            mult = self.blast_primary if is_primary else self.blast_adjacent
            tp = ToughnessDamagePacket(
                amount=20.0 if is_primary else 10.0, element=ElementType.PHYSICAL)

            e4_applied = False
            if getattr(self.owner, "_has_e4", False):
                if getattr(t, "current_toughness", 1.0) <= 0:
                    mod = StatModifier(StatType.CRIT_RATE, StatModifierType.FLAT, 0.25, source="E4")
                    self.owner.stats.apply_modifier(mod, "refresh")
                    e4_applied = True

            a6_applied = False
            if has_a6 and is_primary:
                mod = StatModifier(StatType.DMG_BONUS, StatModifierType.FLAT, 0.25, source="Trace_A6")
                self.owner.stats.apply_modifier(mod, "refresh")
                a6_applied = True

            dmg, crit, tough, brk = state.execute_action(
                self.owner, self.action_type, t,
                mult, damage_type=self.damage_type,
                toughness_packet=tp,
            )
            total_dmg += dmg
            total_crit = total_crit or crit
            total_tough += tough
            total_brk = total_brk or brk

            if e4_applied:
                self.owner.stats.remove_modifier_by_source("E4")
            if a6_applied:
                self.owner.stats.remove_modifier_by_source("Trace_A6")

        return (total_dmg, total_crit, total_tough, total_brk)


class PlayerGirlTalent:
    action_type = ActionType.TALENT
    skill_multiplier = 0.0

    def __init__(self, owner) -> None:
        self.owner = owner
        self.atk_per_stack = 0.25

    def on_combat_start(self, state) -> None:
        if state.event_bus is None:
            return
        self._state_ref = state
        from core.events import EventType
        state.event_bus.subscribe(EventType.ON_WEAKNESS_BREAK, self._on_weakness_break)
        state.event_bus.subscribe(EventType.ON_KILL, self._on_kill)
        state.event_bus.subscribe(EventType.AFTER_ACTION, self._on_after_action)
        state.event_bus.subscribe(EventType.BATTLE_START, self._on_battle_start_a2)

    def _add_talent_stack(self) -> None:
        max_stacks = 3 if getattr(self.owner, "_has_e6", False) else 2
        if self.owner._talent_stacks >= max_stacks:
            return
        self.owner._talent_stacks += 1
        atk_mod = StatModifier(
            StatType.ATK, StatModifierType.PERCENT, self.atk_per_stack,
            source="PlayerGirl_Talent_ATK", dispellable=False,
        )
        self.owner.stats.apply_modifier(atk_mod, "add_stacks")
        if getattr(self.owner, "_has_tenacity", False):
            def_mod = StatModifier(
                StatType.DEF, StatModifierType.PERCENT, 0.10,
                source="PlayerGirl_Talent_DEF", dispellable=False,
            )
            self.owner.stats.apply_modifier(def_mod, "add_stacks")

    def _on_weakness_break(self, **kwargs) -> None:
        breaker = kwargs.get("source")
        if breaker != self.owner:
            return
        self._add_talent_stack()

    def _on_kill(self, **kwargs) -> None:
        source = kwargs.get("source")
        if source != self.owner:
            return

        if getattr(self.owner, "_has_e6", False):
            self._add_talent_stack()

        if getattr(self.owner, "_has_e1", False) and not self.owner._e1_triggered_this_attack:
            if kwargs.get("action_type") == ActionType.ULTIMATE:
                self.owner.gain_energy(10)
                self.owner._e1_triggered_this_attack = True

    def _on_after_action(self, **kwargs) -> None:
        unit = kwargs.get("unit")
        if unit != self.owner:
            return
        self.owner._e1_triggered_this_attack = False

        if getattr(self.owner, "_has_e2", False):
            target = kwargs.get("target")
            if target is not None and hasattr(target, "weaknesses"):
                if ElementType.PHYSICAL in target.weaknesses:
                    heal_amount = int(self.owner.stats.get_total_stat(StatType.ATK) * 0.05)
                    if heal_amount > 0:
                        actual = self.owner.receive_heal(heal_amount)
                        if actual > 0:
                            print(f"  [E2] {self.owner.name} 回复 {actual} HP")

    def _on_battle_start_a2(self, **kwargs) -> None:
        if getattr(self.owner, "_has_a2_energy", False):
            self.owner.gain_energy(15)

    def execute(self, target, state) -> tuple[int, bool, float, bool]:
        return (0, False, 0.0, False)


class PlayerGirlTechnique:
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
        for char in engine.state.alive_characters:
            heal_amount = int(char.max_hp * 0.15)
            if heal_amount > 0:
                actual = char.receive_heal(heal_amount)
                if actual > 0:
                    print(f"  [秘技] {char.name} 回复 {actual} HP")

    def execute(self, target, state) -> tuple[int, bool, float, bool]:
        return (0, False, 0.0, False)

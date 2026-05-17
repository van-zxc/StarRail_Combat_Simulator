"""Herta Skills — 普攻140% / 战技2段AoE+HP条件增伤 / 终结技240%+冻结增伤 / 天赋HP阈值FUA / 秘技ATK+40%。"""

from __future__ import annotations

from core.enums import ActionType, DamageType, StatType, StatModifierType, ElementType
from entities.base import StatModifier, ToughnessDamagePacket, HitPacket
from entities.characters.template_character.skills import (
    TemplateBasicAttack,
    TemplateSkill,
    TemplateUltimate,
)

_HERTA_HIT_SPLIT = [0.30, 0.70]


def _target_is_frozen(target) -> bool:
    for cc in getattr(target, "cc_statuses", []):
        if cc.cc_type == "Freeze":
            return True
    return False


def _apply_e2(owner) -> None:
    if not getattr(owner, "_has_e2", False):
        return
    existing = [m for m in owner.stats.active_modifiers if m.source == "Herta_E2"]
    current_stack_value = existing[0].value if existing else 0.0
    if current_stack_value < 0.15:
        mod = StatModifier(StatType.CRIT_RATE, StatModifierType.FLAT, 0.03,
                           source="Herta_E2", dispellable=False)
        owner.stats.apply_modifier(mod, "add_stacks")
        if current_stack_value + 0.03 > 0.15:
            for m in owner.stats.active_modifiers:
                if m.source == "Herta_E2":
                    m.value = 0.15


class HertaBasicAttack(TemplateBasicAttack):
    skill_multiplier = 1.40
    energy_gain = 20

    def execute(self, target, state) -> tuple[int, bool, float, bool]:
        dmg, crit, tough, brk = state.execute_action(
            self.owner, self.action_type, target,
            self.skill_multiplier, damage_type=self.damage_type,
        )

        if getattr(self.owner, "_has_e1", False) and target.is_alive:
            hp_pct = target.hp / target.max_hp if target.max_hp > 0 else 0.0
            if hp_pct <= 0.50:
                add_dmg, _, _, _ = state.execute_action(
                    self.owner, self.action_type, target, 0.0,
                    damage_type=DamageType.ADDITIONAL_DMG,
                    base_damage_override=int(self.owner.atk * 0.40),
                    element_override=ElementType.ICE,
                )
                dmg += add_dmg

        return (dmg, crit, tough, brk)


class HertaSkill(TemplateSkill):
    skill_multiplier = 1.0

    def execute(self, target, state) -> tuple[int, bool, float, bool]:
        enemies = state.alive_enemies
        total_dmg = 0
        total_crit = False
        total_tough = 0.0
        total_brk = False
        toughness_base = 20.0

        for t in enemies:
            hp_pct = t.hp / t.max_hp if t.max_hp > 0 else 0.0
            bonus_applied = False
            if hp_pct >= 0.50:
                bonus = 0.20 + (0.25 if getattr(self.owner, "_has_efficiency", False) else 0.0)
                mod = StatModifier(StatType.DMG_BONUS, StatModifierType.FLAT, bonus,
                                   source="Herta_Skill_Bonus")
                self.owner.stats.apply_modifier(mod, "refresh")
                bonus_applied = True

            hits = [
                HitPacket(target=t, skill_multiplier=self.skill_multiplier * r,
                          toughness_packet=ToughnessDamagePacket(
                              amount=toughness_base * r, element=ElementType.ICE))
                for r in _HERTA_HIT_SPLIT
            ]
            results = state.execute_multi_hit(self.owner, hits, self.action_type, self.damage_type)

            if bonus_applied:
                self.owner.stats.remove_modifier_by_source("Herta_Skill_Bonus")

            total_dmg += sum(r[0] for r in results)
            total_crit = total_crit or any(r[1] for r in results)
            total_tough += sum(r[2] for r in results)
            total_brk = total_brk or any(r[3] for r in results)

        return (total_dmg, total_crit, total_tough, total_brk)


class HertaUltimate(TemplateUltimate):
    skill_multiplier = 2.0

    def execute(self, target, state) -> tuple[int, bool, float, bool]:
        enemies = state.alive_enemies
        total_dmg = 0
        total_crit = False
        total_tough = 0.0
        total_brk = False

        for t in enemies:
            freeze_bonus = False
            if getattr(self.owner, "_has_freeze", False) and _target_is_frozen(t):
                mod = StatModifier(StatType.DMG_BONUS, StatModifierType.FLAT, 0.20,
                                   source="Herta_Freeze_Bonus")
                self.owner.stats.apply_modifier(mod, "refresh")
                freeze_bonus = True

            dmg, crit, tough, brk = state.execute_action(
                self.owner, self.action_type, t,
                self.skill_multiplier, damage_type=self.damage_type,
            )
            total_dmg += dmg
            total_crit = total_crit or crit
            total_tough += tough
            total_brk = total_brk or brk

            if freeze_bonus:
                self.owner.stats.remove_modifier_by_source("Herta_Freeze_Bonus")

        if getattr(self.owner, "_has_e6", False):
            mod = StatModifier(StatType.ATK, StatModifierType.PERCENT, 0.25,
                               source="Herta_E6_ATK", duration=1, dispellable=False)
            self.owner.stats.apply_modifier(mod, "refresh")

        return (total_dmg, total_crit, total_tough, total_brk)


class HertaTalent:
    action_type = ActionType.TALENT
    skill_multiplier = 0.40

    def __init__(self, owner) -> None:
        self.owner = owner

    def on_combat_start(self, state) -> None:
        if state.event_bus is None:
            return
        self._state_ref = state
        from core.events import EventType
        state.event_bus.subscribe(EventType.AFTER_ACTION, self._on_after_action)
        state.event_bus.subscribe(EventType.BATTLE_START, self._on_battle_start_reset)
        state.event_bus.subscribe(EventType.WAVE_START, self._on_wave_start)

    def _on_battle_start_reset(self, **kwargs) -> None:
        self.owner._talent_triggered = set()

    def _on_wave_start(self, **kwargs) -> None:
        self.owner._talent_triggered = set()
        self._state_ref.follow_up_action_pending = [
            x for x in self._state_ref.follow_up_action_pending
            if x[0] is not self.owner
        ]

    def _on_after_action(self, **kwargs) -> None:
        unit = kwargs.get("unit")
        action_type = kwargs.get("action_type")
        if unit is None:
            return
        if not getattr(unit, "is_alive", False):
            return
        if unit == self.owner and action_type == ActionType.TALENT:
            return

        should_trigger = False
        for enemy in self._state_ref.alive_enemies:
            if id(enemy) in self.owner._talent_triggered:
                continue
            hp_pct = enemy.hp / enemy.max_hp if enemy.max_hp > 0 else 0.0
            if hp_pct <= 0.50:
                self.owner._talent_triggered.add(id(enemy))
                should_trigger = True

        if should_trigger:
            self._state_ref.grant_follow_up_action(self.owner, self)

    def execute(self, target, state) -> tuple[int, bool, float, bool]:
        mult = self.skill_multiplier
        if getattr(self.owner, "_has_e4", False):
            mult *= 1.10

        if getattr(self.owner, "_has_e2", False):
            _apply_e2(self.owner)

        enemies = state.alive_enemies
        total_dmg = 0
        total_crit = False
        total_tough = 0.0
        total_brk = False

        for t in enemies:
            dmg, crit, tough, brk = state.execute_action(
                self.owner, ActionType.FOLLOW_UP, t, mult,
                damage_type=DamageType.DIRECT,
                tags={"attack", "follow_up"}, follow_up_energy_type=2,
                toughness_packet=ToughnessDamagePacket(
                    amount=10.0, element=ElementType.ICE),
            )
            total_dmg += dmg
            total_crit = total_crit or crit
            total_tough += tough
            total_brk = total_brk or brk

        return (total_dmg, total_crit, total_tough, total_brk)


class HertaTechnique:
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
        mod = StatModifier(StatType.ATK, StatModifierType.PERCENT, 0.40,
                           source="Herta_Technique", duration=3, dispellable=False)
        self.owner.stats.apply_modifier(mod, "refresh")

    def execute(self, target, state) -> tuple[int, bool, float, bool]:
        return (0, False, 0.0, False)

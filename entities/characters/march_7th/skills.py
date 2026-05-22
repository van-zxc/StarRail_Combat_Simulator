from __future__ import annotations
"""March7th Skills — 基于 JSON 数据: 普攻140% / 战技护盾+嘲讽 / 终结技群攻+冻结Dot / 天赋反击 / 秘技冻结。"""

from core.enums import ActionType, DamageType, ElementType, StatType
from entities.base import ToughnessDamagePacket
from entities.characters.template_character.skills import (
    TemplateBasicAttack,
    TemplateSkill,
    TemplateUltimate,
)


class March7thBasicAttack(TemplateBasicAttack):
    """普攻: 140% ATK 单攻冰伤 (lv10 params[9][0]=1.40)。"""
    skill_multiplier = 1.40
    energy_gain = 20


class March7thSkill(TemplateSkill):
    """战技: 提供 DEF×66.5% + 974 护盾, HP≥30% 嘲讽 600%, 持续 3(+1) 回合。"""

    skill_multiplier = 0.0

    def execute(self, target, state) -> tuple[int, bool, float, bool]:
        from core.game_state import GameState as GS
        from entities.base import ShieldStatus

        # 护盾值
        def_stat = self.owner.stats.get_total_stat(StatType.DEF)
        duration = 4 if getattr(self.owner, "_has_shield_plus", False) else 3
        shield_val = GS.calculate_shield_value(
            self.owner, def_stat, 0.665, 974.0,
        )

        # 移除已有的弱护盾 (同源替换)
        self.owner.shield_statuses[:] = [
            s for s in self.owner.shield_statuses
            if s.source_name != "March7th_Shield" or s.shield_value >= shield_val
        ]
        self.owner.apply_shield(ShieldStatus(shield_val, shield_val, "March7th_Shield", duration=duration))

        # 己方 HP≥30% → 大幅提高受击概率 (600%)
        hp_pct = self.owner.hp / self.owner.max_hp if self.owner.max_hp > 0 else 0.0
        if hp_pct >= 0.30:
            self.owner.external_taunt_factor = 6.0

        # 纯洁: 解除 1 个负面效果
        if getattr(self.owner, "_has_cleanse", False):
            state.dispel_one(self.owner)

        print(f"  March7th 施放护盾: 值 {shield_val:.0f}, 持续{duration}回合" +
              (" [嘲讽600%]" if self.owner.external_taunt_factor > 1.0 else ""))
        return (0, False, 0.0, False)


class March7thUltimate(TemplateUltimate):
    """终结技: 180% ATK 群攻冰伤 + 65%(冰咒) 基础冻结 1回合 + 75% ATK 冻结附加伤害。"""

    skill_multiplier = 1.80

    def execute(self, target, state) -> tuple[int, bool, float, bool]:
        from entities.base import CCStatus, FreezeDotStatus

        # 伤害结算: 对所有敌方都打
        base_chance = 0.65 if getattr(self.owner, "_has_freeze_plus", False) else 0.50
        total_dmg = 0
        total_crit = False
        total_tough = 0.0
        total_brk = False
        frozen_count = 0

        for enemy in state.alive_enemies:
            dmg, is_crit, tough, brk = state.execute_action(
                self.owner, self.action_type, enemy, self.skill_multiplier,
                damage_type=self.damage_type,
            )
            total_dmg += dmg
            total_crit = total_crit or is_crit
            total_tough += tough
            total_brk = total_brk or brk

            # 冻结判定
            applied, ch = state.try_apply_debuff(
                self.owner, enemy, base_chance=base_chance, debuff_type="Freeze",
            )
            if applied:
                enemy.cc_statuses.append(CCStatus("Freeze", remaining_turns=1))
                # 冻结附加伤害: 75% ATK (lv15 params[14][3]=0.75)
                freeze_dot_mult = 0.75
                enemy.freeze_dot_statuses.append(
                    FreezeDotStatus(attacker=self.owner, multiplier=freeze_dot_mult, remaining_turns=1)
                )
                frozen_count += 1
                print(f"  >>> 终结技冻结成功! {enemy.name} (命中率 {ch:.2f})")

        # E1: 每冻结 1 个目标恢复 6 能量
        if frozen_count > 0 and self.owner._has_e1:
            energy_gain = frozen_count * 6.0
            self.owner.gain_energy(energy_gain)
            print(f"  >>> E1: 冻结 {frozen_count} 个目标, 恢复 {energy_gain:.0f} 能量")

        print(f"  March7th 终结技: 造成 {total_dmg} 伤害, 冻结 {frozen_count} 个目标")
        return (total_dmg, total_crit, total_tough, total_brk)


class March7thTalent(TemplateSkill):
    """天赋: 持盾者受击 → 反击 125% ATK 冰伤 (每回合 max 2/3 次)。"""

    skill_multiplier = 1.25
    action_type = ActionType.BASIC_ATTACK
    tags = {"attack", "counter", "follow_up"}

    def on_combat_start(self, state) -> None:
        if state.event_bus is None:
            return
        self._state_ref = state
        from core.events import EventType
        state.event_bus.subscribe(EventType.ON_HIT, self._on_hit_listener)
        state.event_bus.subscribe(EventType.TURN_START, self._on_turn_start)
        state.event_bus.subscribe(EventType.BATTLE_START, self._on_battle_start_eidolons)

    def _on_battle_start_eidolons(self, **kwargs) -> None:
        """E2: 进入战斗时, 为 HP% 最低的队友提供护盾 (DEF×24% + 320, 3回合)。"""
        if not getattr(self.owner, "_has_e2", False):
            return
        engine = kwargs.get("engine")
        if engine is None:
            return
        state = engine.state

        # 找 HP% 最低的队友
        lowest = min(
            (c for c in state.alive_characters if c.is_alive),
            key=lambda c: c.hp / c.max_hp if c.max_hp > 0 else 1.0,
            default=None,
        )
        if lowest is None:
            return

        from entities.base import ShieldStatus
        from core.enums import StatType
        def_stat = self.owner.stats.get_total_stat(StatType.DEF)
        shield_val = (def_stat * 0.24 + 320.0) * (1.0 + self.owner.stats.get_total_stat(StatType.SHIELD_BONUS))

        lowest.shield_statuses[:] = [
            s for s in lowest.shield_statuses
            if s.source_name != "March7th_E2_Shield"
        ]
        lowest.apply_shield(ShieldStatus(shield_val, shield_val, "March7th_E2_Shield", duration=3))
        print(f"  [E2] 给 {lowest.name} 施加护盾: {shield_val:.0f} (3回合)")

    def _on_hit_listener(self, **kwargs) -> None:
        source = kwargs.get("source")
        hit_target = kwargs.get("target")
        if source is None or hit_target is None:
            return
        from entities.enemies.base import BaseEnemy
        from entities.characters.base import BaseCharacter
        if not isinstance(source, BaseEnemy):
            return
        if not isinstance(hit_target, BaseCharacter):
            return
        # 受击者持有 March7th 护盾
        has_m7_shield = any(
            s.source_name == "March7th_Shield" and s.shield_value > 0
            for s in hit_target.shield_statuses
        )
        if not has_m7_shield:
            return
        self._state_ref.grant_follow_up_action(self.owner, self, is_follow_up_action=True)

    def _on_turn_start(self, **kwargs) -> None:
        """回合开始: 重置反击计数器 + E6 护盾回复。"""
        unit = kwargs.get("unit")
        if unit is self.owner:
            self.owner._counter_used = 0

        # E6: 持盾者每回合开始回复 4%HP + 106
        if getattr(self.owner, "_has_e6", False) and isinstance(unit, self._CharacterClass):
            has_m7_shield = any(
                s.source_name in ("March7th_Shield", "March7th_E2_Shield") and s.shield_value > 0
                for s in unit.shield_statuses
            )
            if has_m7_shield:
                from core.enums import StatType
                heal_amount = int(unit.max_hp * 0.04 + 106)
                actual = unit.receive_heal(heal_amount)
                if actual > 0:
                    print(f"  [E6] {unit.name} 回复 {actual} HP")

    @property
    def _CharacterClass(self):
        from entities.characters.base import BaseCharacter
        return BaseCharacter

    def trigger_counter(self, target, state) -> int:
        if self.owner._counter_used >= self.owner._counter_max:
            return 0
        self.owner._counter_used += 1

        dmg, _, _, _ = state.execute_action(
            self.owner, self.action_type, target, self.skill_multiplier,
            tags=self.tags, follow_up_energy_type=2,
            toughness_packet=ToughnessDamagePacket(
                amount=10.0, element=ElementType.ICE),
        )

        # E4: 反击伤害 +DEF×30% 作为固定附加 (直接加在 damage 上)
        def_bonus = getattr(self.owner, "_e4_def_flat", 0.0)
        if def_bonus > 0:
            dmg += int(def_bonus)

        print(f"  >>> March7th 反击! 造成 {dmg} 点伤害 " +
              f"({self.owner._counter_used}/{self.owner._counter_max})" +
              (f" [DEF加成+{int(def_bonus)}]" if def_bonus > 0 else ""))
        return dmg

    def execute(self, target, state) -> tuple[int, bool, float, bool]:
        dmg = self.trigger_counter(target, state)
        return (dmg, False, 0.0, False)


class March7thTechnique:
    """秘技: 100% 基础概率使随机敌方单体冻结 1回合 + 50% ATK 附加伤害 + AoE 50%伤害削韧20。"""

    action_type = ActionType.TALENT
    skill_multiplier = 0.50

    def __init__(self, owner) -> None:
        self.owner = owner

    def on_combat_start(self, state) -> None:
        if state.event_bus is None:
            return
        from core.events import EventType
        state.event_bus.subscribe(EventType.BATTLE_START, self._on_battle_start)

    def _on_battle_start(self, **kwargs) -> None:
        from entities.base import CCStatus, FreezeDotStatus, ToughnessDamagePacket
        import random

        engine = kwargs.get("engine")
        if engine is None:
            return
        state = engine.state
        enemies = state.alive_enemies
        if not enemies:
            return

        tp = ToughnessDamagePacket(
            amount=20.0, element=ElementType.ICE)

        for enemy in enemies:
            dmg, _, _, _ = state.execute_action(
                self.owner, ActionType.TALENT, enemy,
                self.skill_multiplier, damage_type=DamageType.DIRECT,
                element_override=ElementType.ICE,
                toughness_packet=tp,
            )

        target = random.choice(enemies)
        applied, ch = state.try_apply_debuff(
            self.owner, target, base_chance=1.0, debuff_type="Freeze",
        )
        if applied:
            target.cc_statuses.append(CCStatus("Freeze", remaining_turns=1))
            target.freeze_dot_statuses.append(
                FreezeDotStatus(attacker=self.owner, multiplier=0.50, remaining_turns=1)
            )
            print(f"  [秘技] {target.name} 被冻结! (命中率 {ch:.2f})")

    def execute(self, target, state) -> tuple[int, bool, float, bool]:
        return (0, False, 0.0, False)

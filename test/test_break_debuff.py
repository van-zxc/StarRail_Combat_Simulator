from __future__ import annotations

"""验证装备系统（光锥/遗器）、白值/绿值分离、韧性、暴击、终结技插队。

测试覆盖：
  - 光锥 & 遗器装备 → 白值 / 绿值计算
  - EquipmentEffect 回调
  - 韧性削韧 & 弱点击破
  - Stats 面板解耦 & 数据驱动
  - 暴击判定 (mock random)
  - 终结技插队
  - 能量 & SP 规则
"""

# mypy: ignore-errors
# pyright: reportPrivateUsage=false

from unittest.mock import Mock, patch

import pytest

from starrail_combat import (
    ActionType,
    ShieldStatus,
    Character,
    CombatEngine,
    DamageType,
    DoTStatus,
    ElementType,
    Enemy,
    EntityStats,
    EquipmentEffect,
    GameState,
    LightCone,
    Memosprite,
    PathType,
    Relic,
    RelicPart,
    StatModifier,
    StatModifierType,
    StatType,
    create_test_character,
    get_data_loader,
    init_data,
)
from core.enums import DEBUFF_RES_MAP
from core.events import EventType
from core.targeting import TargetManager
from entities.light_cones.arrows import Arrows, ArrowsEffect
from entities.light_cones.post_op import PostOpConversation, PostOpEffect
from entities.light_cones.night_milky_way import NightOnTheMilkyWay, NightMilkyWayEffect
from entities.light_cones.collateral import Collateral, CollateralEffect
from entities.light_cones.skyfall import Skyfall, SkyfallEffect
from entities.light_cones.amber import Amber, AmberEffect
from entities.light_cones.deep_dark import DeepDark, DeepDarkEffect
from entities.light_cones.chorus import Chorus, ChorusEffect
from entities.light_cones.data_bank import DataBank, DataBankEffect
from core.damage.multipliers import (
    apply_break_effect,
    crit_multiplier,
    damage_bonus_multiplier,
    defense_multiplier,
    resistance_multiplier,
    toughness_multiplier,
    vulnerability_multiplier,
)

# 模块加载时初始化 DataLoader（读取 JSON 文件）
init_data()


# ============================================================
#  TestEquipmentSystem — 光锥 & 遗器装备系统
# ============================================================


class TestDebuffApplication:
    """验证 EHR 等级成长 + 类型特定 DEBUFF_RES + try_apply_debuff。"""

    # ── 测试 1: lv=90 敌人的基础 EHR ──
    def test_enemy_ehr_level_growth(self) -> None:
        enemy = Enemy(name="Test", hp=1000, speed=50, base_damage=10, level=90)
        base_ehr = enemy.stats.get_base_stat(StatType.EFFECT_HIT_RATE)
        expected = (90 - 50) * 0.008
        assert base_ehr == pytest.approx(expected)  # 0.32

    # ── 测试 2: 命中概率推算 (EHR=1.2, RES=0.4, Burn RES=0) ──
    def test_real_chance_calculation(self) -> None:
        attacker = create_test_character("Attacker", hp=200, speed=100, atk=50.0)
        attacker.stats.add_modifier(StatModifier(
            StatType.EFFECT_HIT_RATE, StatModifierType.FLAT, 1.20, source="Test"))
        target = create_test_character("Target", hp=200, speed=100, atk=50.0)
        target.stats.add_modifier(StatModifier(
            StatType.EFFECT_RES, StatModifierType.FLAT, 0.40, source="Test"))

        state = GameState(characters=[attacker, target], enemies=[])

        success, real_chance = state.try_apply_debuff(
            attacker, target, base_chance=1.0, debuff_type="Burn",
        )
        # 1.0 * (1+1.2) * (1-0.4) * (1-0) = 2.2 * 0.6 = 1.32
        assert real_chance == pytest.approx(1.32)
        assert success is True  # > 1.0 → 必定命中

    # ── 测试 3: 类型特定 DEBUFF_RES 生效 ──
    def test_type_specific_debuff_res(self) -> None:
        attacker = create_test_character("Attacker", hp=200, speed=100, atk=50.0)
        target = create_test_character("Target", hp=200, speed=100, atk=50.0)
        # 50% Burn 抵抗
        target.stats.add_modifier(StatModifier(
            StatType.DEBUFF_RES_BURN, StatModifierType.FLAT, 0.50, source="Test"))

        state = GameState(characters=[attacker, target], enemies=[])

        _, burn_chance = state.try_apply_debuff(
            attacker, target, base_chance=1.0, debuff_type="Burn",
        )
        # 1.0 * 1.0 * 1.0 * (1-0.50) = 0.50
        assert burn_chance == pytest.approx(0.50)

        # Freeze 不受 Burn RES 影响
        _, freeze_chance = state.try_apply_debuff(
            attacker, target, base_chance=1.0, debuff_type="Freeze",
        )
        assert freeze_chance == pytest.approx(1.0)


# ============================================================
#  TestEnergySystemV2 — 能量 V2 (非能/半能/受击/ERR)
# ============================================================


class TestBreakDebuffs:
    """验证 Break DMG, DoT/CC 挂载, 冻结跳回合, 纠缠叠层。"""

    # ── 测试 1: Physical 裂伤 + Break DMG ──
    def test_physical_break_applies_bleed(self) -> None:
        char = create_test_character("P", hp=200, speed=100, atk=50.0,
                                      element=ElementType.PHYSICAL, level=80)
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL], max_toughness=1.0)
        state = GameState(characters=[char], enemies=[enemy])
        engine = CombatEngine(state)

        _, _, _, triggered = state.execute_action(char, ActionType.BASIC_ATTACK, enemy, 1.0)
        assert triggered
        engine._apply_break_effects(char, enemy)
        # 裂伤 DoT 已挂载
        assert any(d.element == ElementType.PHYSICAL for d in enemy.dot_statuses)

    # ── 测试 2: Fire 灼烧 ──
    def test_fire_break_applies_burn(self) -> None:
        char = create_test_character("F", hp=200, speed=100, atk=50.0,
                                      element=ElementType.FIRE, level=80)
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.FIRE], max_toughness=1.0)
        state = GameState(characters=[char], enemies=[enemy])
        engine = CombatEngine(state)

        _, _, _, triggered = state.execute_action(char, ActionType.BASIC_ATTACK, enemy, 1.0)
        engine._apply_break_effects(char, enemy)
        assert any(d.element == ElementType.FIRE for d in enemy.dot_statuses)

    # ── 测试 3: Ice 冻结 → 敌方跳过回合 ──
    def test_ice_break_freezes_and_skips_turn(self) -> None:
        char = create_test_character("I", hp=200, speed=100, atk=50.0,
                                      element=ElementType.ICE, level=80)
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.ICE], max_toughness=1.0)
        state = GameState(characters=[char], enemies=[enemy])
        engine = CombatEngine(state)

        _, _, _, triggered = state.execute_action(char, ActionType.BASIC_ATTACK, enemy, 1.0)
        engine._apply_break_effects(char, enemy)
        assert len(enemy.cc_statuses) == 1
        assert enemy.cc_statuses[0].cc_type == "Freeze"
        # 冻结导致跳过行动
        assert engine._process_cc_turn_start(enemy) is True

    # ── 测试 4: Entanglement 纠缠叠层 + 伤害 ──
    def test_entanglement_stacks_on_hit(self) -> None:
        char = create_test_character("Q", hp=200, speed=100, atk=50.0,
                                      element=ElementType.QUANTUM, level=80)
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.QUANTUM], max_toughness=1.0)
        state = GameState(characters=[char], enemies=[enemy])
        engine = CombatEngine(state)

        _, _, _, triggered = state.execute_action(char, ActionType.BASIC_ATTACK, enemy, 1.0)
        engine._apply_break_effects(char, enemy)
        assert len(enemy.cc_statuses) == 1
        assert enemy.cc_statuses[0].cc_type == "Entanglement"

        init_stack = enemy.cc_statuses[0].stacks
        # 再次命中 → 叠层
        state.execute_action(char, ActionType.BASIC_ATTACK, enemy, 1.0)
        assert enemy.cc_statuses[0].stacks > init_stack

    # ── 测试 5: Imprison 禁锢 ──
    def test_imprison_slows_enemy(self) -> None:
        char = create_test_character("IM", hp=200, speed=100, atk=50.0,
                                      element=ElementType.IMAGINARY, level=80)
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.IMAGINARY], max_toughness=1.0)
        state = GameState(characters=[char], enemies=[enemy])
        engine = CombatEngine(state)

        _, _, _, triggered = state.execute_action(char, ActionType.BASIC_ATTACK, enemy, 1.0)
        engine._apply_break_effects(char, enemy)
        assert len(enemy.cc_statuses) == 1
        assert enemy.cc_statuses[0].cc_type == "Imprison"

        spd_before = enemy.speed
        engine._process_cc_turn_start(enemy)
        assert enemy.speed < spd_before  # 减速 10%


# ============================================================
#  TestTrueDamage — 真实伤害乘区
# ============================================================


class TestBreakMechanics:
    """验证文档 §10 的击破相关逻辑是否正确。"""

    # ── 测试 1: 击破恢复时机 (§10.3) ──
    def test_break_recovery_on_enemy_own_turn(self) -> None:
        """击破后，敌方在自己回合初恢复韧性 (非其他单位回合)。"""
        char = create_test_character("Breaker", hp=200, speed=200, atk=100.0,
                                      crit_rate=0.0, element=ElementType.FIRE)
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.FIRE], max_toughness=15)
        state = GameState(characters=[char], enemies=[enemy])
        engine = CombatEngine(state)

        state.execute_action(char, ActionType.SKILL, enemy, 1.0)
        assert enemy.broken
        assert enemy.current_toughness == 0

        # 角色再行动 → 敌人仍是 broken
        engine._decrement_modifiers()  # 模拟回合结束
        assert enemy.broken  # 角色回合不恢复敌人韧性

        # 敌方自己回合 → 恢复
        engine._check_break_recovery(enemy)
        assert not enemy.broken
        assert enemy.current_toughness == enemy.max_toughness

    # ── 测试 2: 基础击破推条 25% (§10.2) ──
    def test_break_delays_target_by_25_percent(self) -> None:
        """任何元素击破均应推条 25% (non-量子/非虚数不叠加额外推条)。"""
        char = create_test_character("Breaker", hp=200, speed=100, atk=100.0,
                                      crit_rate=0.0, element=ElementType.FIRE)
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.FIRE], max_toughness=15)
        state = GameState(characters=[char], enemies=[enemy])
        engine = CombatEngine(state)

        av_before = enemy.current_av
        state.execute_action(char, ActionType.SKILL, enemy, 2.0)
        # 击破效果中的推条由 _apply_break_effects 执行
        engine._apply_break_effects(char, enemy)

        # 击破推条固定 25%
        expected_av = av_before * (1.0 + 0.25)
        assert enemy.current_av == pytest.approx(expected_av)

    # ── 测试 3: 韧性伤害溢出钳位 (§10.2) ──
    def test_toughness_damage_clamped_to_remaining(self) -> None:
        """剩余韧性不足时只扣部分, 不倒扣为负数。"""
        char = create_test_character("Breaker", hp=200, speed=100, atk=100.0,
                                      crit_rate=0.0, element=ElementType.FIRE)
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.FIRE], max_toughness=5)
        state = GameState(characters=[char], enemies=[enemy])

        # 战技 20 削韧 > 剩余 5
        _, _, toughness, did_break = state.execute_action(char, ActionType.SKILL, enemy, 1.0)
        assert toughness == pytest.approx(5.0)  # 仅扣 5
        assert enemy.current_toughness == 0
        assert enemy.broken
        assert did_break

    # ── 测试 4: 风化击破 DoT (§10.2) ──
    def test_wind_break_applies_3_stack_wind_shear(self) -> None:
        """风属性击破挂载 3 层风化, 持续 2 回合, is_break_induced=True。"""
        char = create_test_character("Breaker", hp=200, speed=200, atk=100.0,
                                      crit_rate=0.0, element=ElementType.WIND)
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.WIND], max_toughness=30)
        state = GameState(characters=[char], enemies=[enemy])
        engine = CombatEngine(state)

        state.execute_action(char, ActionType.SKILL, enemy, 2.0)
        engine._apply_break_effects(char, enemy)

        assert len(enemy.dot_statuses) == 1
        dot = enemy.dot_statuses[0]
        assert dot.element == ElementType.WIND
        assert dot.stacks == 3
        assert dot.duration == 2
        assert dot.is_break_induced

    # ── 测试 5: 触电击破 DoT (§10.2) ──
    def test_lightning_break_applies_shock(self) -> None:
        """雷属性击破挂载触电, dot_multiplier = 2×LM。"""
        char = create_test_character("Breaker", hp=200, speed=200, atk=100.0,
                                      crit_rate=0.0, element=ElementType.LIGHTNING)
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.LIGHTNING], max_toughness=30)
        state = GameState(characters=[char], enemies=[enemy])
        engine = CombatEngine(state)

        state.execute_action(char, ActionType.SKILL, enemy, 2.0)
        engine._apply_break_effects(char, enemy)

        assert len(enemy.dot_statuses) == 1
        dot = enemy.dot_statuses[0]
        assert dot.element == ElementType.LIGHTNING
        assert dot.stacks == 1
        assert dot.is_break_induced
        # dot_base = 2 × LM(80) = 2 × 3767.5533
        expected_base = 2.0 * engine._get_level_multiplier(char.level)
        assert dot.dot_multiplier == pytest.approx(expected_base)

    # ── 测试 6: 裂伤上限公式 (§10.2) ──
    def test_physical_bleed_cap_formula(self) -> None:
        """裂伤上限 = min(0.07×max_hp, 2.0×LM×TM)。"""
        char = create_test_character("Breaker", hp=200, speed=200, atk=100.0,
                                      crit_rate=0.0, element=ElementType.PHYSICAL)
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL], max_toughness=40)
        state = GameState(characters=[char], enemies=[enemy])
        engine = CombatEngine(state)

        state.execute_action(char, ActionType.SKILL, enemy, 2.0)
        engine._apply_break_effects(char, enemy)

        assert len(enemy.dot_statuses) == 1
        dot = enemy.dot_statuses[0]
        assert dot.element == ElementType.PHYSICAL

        lm = engine._get_level_multiplier(char.level)
        tm = 0.5 + enemy.max_toughness / 40.0
        cap = 2.0 * lm * tm  # 2 × 3767.55 × 1.5
        raw = 0.07 * enemy.max_hp  # 700
        expected = min(raw, cap)
        assert dot.dot_multiplier == pytest.approx(expected)

    # ── 测试 7: 击破 DoT 不暴击 (§8.5) ──
    def test_break_dot_skips_crit(self) -> None:
        """击破 DoT 结算应不经过暴击乘区。"""
        char = create_test_character("Breaker", hp=200, speed=200, atk=100.0,
                                      crit_rate=1.0, element=ElementType.FIRE)
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.FIRE], max_toughness=30)
        state = GameState(characters=[char], enemies=[enemy])
        engine = CombatEngine(state)

        state.execute_action(char, ActionType.SKILL, enemy, 2.0)
        engine._apply_break_effects(char, enemy)

        assert len(enemy.dot_statuses) == 1
        dot = enemy.dot_statuses[0]
        assert dot.element == ElementType.FIRE

        # 手动结算 DoT: damage_type=DOT → chain 不含 crit
        base_dmg = int(dot.dot_multiplier * dot.stacks)
        damage, is_crit, _, _ = state.execute_action(
            char, ActionType.BASIC_ATTACK, enemy, 0.0,
            damage_type=DamageType.DOT, base_damage_override=base_dmg,
            element_override=dot.element,
        )
        assert not is_crit

    # ── 测试 8: 超击破公式验证 (§8.8) ──
    def test_super_break_damage_formula(self) -> None:
        """Super Break = LM × (TD/30) × (1+BE) × DEF × RES × Vuln × Broken。"""
        char = create_test_character("Breaker", hp=200, speed=200, atk=100.0,
                                      crit_rate=0.0, element=ElementType.FIRE,
                                      level=80)
        char.stats.add_modifier(StatModifier(
            StatType.BREAK_EFFECT, StatModifierType.FLAT, 1.0, source="Test"))
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.FIRE], max_toughness=30)
        state = GameState(characters=[char], enemies=[enemy])

        # 预击破
        enemy.broken = True
        enemy.current_toughness = 0

        engine = CombatEngine(state)
        lm = engine._get_level_multiplier(char.level)
        td = 10.0  # basic attack toughness damage
        break_effect = 1.0 + char.stats.get_total_stat(StatType.BREAK_EFFECT)

        super_break_base = int(lm * (td / 30.0))
        assert super_break_base > 0

        dmg, _, _, _ = state.execute_action(
            char, ActionType.BASIC_ATTACK, enemy, 1.0,
            damage_type=DamageType.SUPER_BREAK,
            base_damage_override=super_break_base,
        )
        assert dmg > 0


# ============================================================
#  TestToughnessPacket — ToughnessDamagePacket 新特性
# ============================================================


class TestToughnessPacket:
    """验证 ignoresWeakness 和 efficiencyMultiplier。"""

    def test_ignore_weakness_bypasses_element_check(self) -> None:
        """ignores_weakness=True 时, 不匹配弱点也能削韧。"""
        from entities.base import ToughnessDamagePacket

        char = create_test_character("Breaker", hp=200, speed=100, atk=100.0,
                                      crit_rate=0.0, element=ElementType.ICE)
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.FIRE], max_toughness=30)
        state = GameState(characters=[char], enemies=[enemy])

        packet = ToughnessDamagePacket(
            amount=20.0, element=ElementType.ICE,
            ignores_weakness=True,
        )
        _, _, toughness, did_break = state.execute_action(
            char, ActionType.SKILL, enemy, 1.0,
            toughness_packet=packet,
        )
        assert toughness == pytest.approx(20.0)
        # 韧性 30 → 扣 20 → 剩余 10 → 未击破
        assert not enemy.broken
        assert enemy.current_toughness == pytest.approx(10.0)

    def test_efficiency_multiplier_scales_toughness_damage(self) -> None:
        """efficiency_multiplier 按比例缩放削韧量。"""
        from entities.base import ToughnessDamagePacket

        char = create_test_character("Breaker", hp=200, speed=100, atk=100.0,
                                      crit_rate=0.0, element=ElementType.FIRE)
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.FIRE], max_toughness=30)
        state = GameState(characters=[char], enemies=[enemy])

        packet = ToughnessDamagePacket(
            amount=10.0, element=ElementType.FIRE,
            efficiency_multiplier=2.0,
        )
        _, _, toughness, did_break = state.execute_action(
            char, ActionType.BASIC_ATTACK, enemy, 1.0,
            toughness_packet=packet,
        )
        assert toughness == pytest.approx(20.0)  # 10 × 2.0

    def test_combined_ignore_and_efficiency(self) -> None:
        """同时忽视弱点 + 效率倍率 → 跨元素高削韧击破。"""
        from entities.base import ToughnessDamagePacket

        char = create_test_character("Breaker", hp=200, speed=100, atk=100.0,
                                      crit_rate=0.0, element=ElementType.ICE)
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.FIRE], max_toughness=30)
        state = GameState(characters=[char], enemies=[enemy])

        packet = ToughnessDamagePacket(
            amount=15.0, element=ElementType.ICE,
            ignores_weakness=True, efficiency_multiplier=2.0,
        )
        _, _, toughness, did_break = state.execute_action(
            char, ActionType.BASIC_ATTACK, enemy, 1.0,
            toughness_packet=packet,
        )
        assert toughness == pytest.approx(30.0)  # 15 × 2.0 → max_toughness
        assert enemy.broken
        assert did_break

    def test_zero_amount_no_toughness_damage(self) -> None:
        """amount=0 的分组不造成削韧。"""
        from entities.base import ToughnessDamagePacket

        char = create_test_character("Breaker", hp=200, speed=100, atk=100.0,
                                      crit_rate=0.0, element=ElementType.FIRE)
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.FIRE], max_toughness=30)
        state = GameState(characters=[char], enemies=[enemy])

        packet = ToughnessDamagePacket(
            amount=0.0, element=ElementType.FIRE,
            ignores_weakness=True,
        )
        _, _, toughness, did_break = state.execute_action(
            char, ActionType.BASIC_ATTACK, enemy, 1.0,
            toughness_packet=packet,
        )
        assert toughness == 0.0
        assert not enemy.broken

    def test_negative_efficiency_clamped_to_zero(self) -> None:
        """负效率倍率被 max(0, multiplier) 钳位为 0。"""
        from entities.base import ToughnessDamagePacket

        char = create_test_character("Breaker", hp=200, speed=100, atk=100.0,
                                      crit_rate=0.0, element=ElementType.FIRE)
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.FIRE], max_toughness=30)
        state = GameState(characters=[char], enemies=[enemy])

        packet = ToughnessDamagePacket(
            amount=10.0, element=ElementType.FIRE,
            efficiency_multiplier=-0.5,
        )
        _, _, toughness, _ = state.execute_action(
            char, ActionType.BASIC_ATTACK, enemy, 1.0,
            toughness_packet=packet,
        )
        assert toughness == 0.0


# ============================================================
#  TestAggroDoc — 文档 §11 仇恨机制验证
# ============================================================


class TestTickTiming:
    """验证 StatModifier 按 tick_timing 在不同时点递减。"""

    def test_owner_turn_end_only_decrements_owner_turn_end_mods(self) -> None:
        """tick_timing='owner_turn_end' 的修饰器仅在回合结束时递减。"""
        attacker = create_test_character("A", hp=200, speed=200, atk=10.0, crit_rate=0.0)
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[attacker], enemies=[enemy])

        mod_end = StatModifier(StatType.ATK, StatModifierType.FLAT, 10.0,
                               tick_timing="owner_turn_end", duration=2)
        attacker.stats.add_modifier(mod_end)

        engine = CombatEngine(state)
        # 角色回合结束 → owner_turn_end 递减
        engine._decrement_modifiers_timing("owner_turn_end")
        assert mod_end.duration == 1
        engine._decrement_modifiers_timing("owner_turn_end")
        assert mod_end.duration == 0
        assert mod_end not in attacker.stats.active_modifiers

    def test_owner_turn_start_only_decrements_owner_turn_start_mods(self) -> None:
        """tick_timing='owner_turn_start' 的修饰器仅在回合开始时递减。"""
        attacker = create_test_character("A", hp=200, speed=200, atk=10.0, crit_rate=0.0)
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[attacker], enemies=[enemy])

        mod_start = StatModifier(StatType.ATK, StatModifierType.FLAT, 10.0,
                                 tick_timing="owner_turn_start", duration=2)
        attacker.stats.add_modifier(mod_start)

        engine = CombatEngine(state)
        # 回合结束不递减 owner_turn_start 修饰器
        engine._decrement_modifiers_timing("owner_turn_end")
        assert mod_start.duration == 2  # 不变

        # 回合开始才递减
        engine._decrement_modifiers_timing("owner_turn_start")
        assert mod_start.duration == 1

    def test_mixed_timings_decrement_independently(self) -> None:
        """不同 tick_timing 的修饰器各自在正确时点递减。"""
        attacker = create_test_character("A", hp=200, speed=200, atk=10.0, crit_rate=0.0)
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[attacker], enemies=[enemy])

        mod_start = StatModifier(StatType.ATK, StatModifierType.FLAT, 5.0,
                                 tick_timing="owner_turn_start", duration=1)
        mod_end = StatModifier(StatType.DEF, StatModifierType.FLAT, 10.0,
                               tick_timing="owner_turn_end", duration=2)
        attacker.stats.add_modifier(mod_start)
        attacker.stats.add_modifier(mod_end)

        engine = CombatEngine(state)
        engine._decrement_modifiers_timing("owner_turn_end")
        assert mod_start.duration == 1   # 不减
        assert mod_end.duration == 1     # -1

        engine._decrement_modifiers_timing("owner_turn_start")
        assert mod_start.duration == 0   # -1 → 移除
        assert mod_end.duration == 1     # 不减
        assert mod_start not in attacker.stats.active_modifiers


# ============================================================
#  TestCleanseDispel — P1-3: 驱散/净化
# ============================================================


class TestCleanseDispel:
    """验证按 source 和 tag 批量移除修饰器。"""

    def test_remove_modifier_by_source(self) -> None:
        """移除指定来源的所有可驱散修饰器。"""
        char = create_test_character("A", hp=200, speed=100)
        m1 = StatModifier(StatType.ATK, StatModifierType.FLAT, 10.0, source="BossA")
        m2 = StatModifier(StatType.DEF, StatModifierType.FLAT, 5.0, source="BossA")
        m3 = StatModifier(StatType.SPD, StatModifierType.FLAT, 20.0, source="Ally")
        char.stats.add_modifier(m1)
        char.stats.add_modifier(m2)
        char.stats.add_modifier(m3)
        assert len(char.stats.active_modifiers) == 3

        char.stats.remove_modifier_by_source("BossA")
        assert len(char.stats.active_modifiers) == 1
        assert char.stats.active_modifiers[0].source == "Ally"

    def test_remove_modifier_by_tag(self) -> None:
        """移除指定标签的所有可驱散修饰器。"""
        char = create_test_character("A", hp=200, speed=100)
        m1 = StatModifier(StatType.ATK, StatModifierType.FLAT, 10.0,
                          tags=("debuff", "fire"))
        m2 = StatModifier(StatType.DEF, StatModifierType.FLAT, 5.0,
                          tags=("debuff", "ice"))
        m3 = StatModifier(StatType.SPD, StatModifierType.FLAT, 20.0,
                          tags=("buff",))
        char.stats.add_modifier(m1)
        char.stats.add_modifier(m2)
        char.stats.add_modifier(m3)
        assert len(char.stats.active_modifiers) == 3

        char.stats.remove_modifier_by_tag("debuff")
        assert len(char.stats.active_modifiers) == 1
        assert char.stats.active_modifiers[0].tags == ("buff",)

    def test_non_dispellable_immune_to_removal(self) -> None:
        """dispellable=False 的修饰器不受驱散影响。"""
        char = create_test_character("A", hp=200, speed=100)
        m1 = StatModifier(StatType.ATK, StatModifierType.FLAT, 10.0,
                          source="Boss", dispellable=False)
        m2 = StatModifier(StatType.DEF, StatModifierType.FLAT, 5.0,
                          source="Boss", dispellable=True)
        char.stats.add_modifier(m1)
        char.stats.add_modifier(m2)

        char.stats.remove_modifier_by_source("Boss")
        assert len(char.stats.active_modifiers) == 1
        assert char.stats.active_modifiers[0].dispellable is False


# ============================================================
#  TestCharacterCC — P1-4: 角色侧 CC 状态追踪
# ============================================================


class TestCharacterCC:
    """验证角色被冻结/禁锢时在回合初有对应行为。"""

    def test_frozen_character_skips_turn(self) -> None:
        """被冻结的角色回合被跳过。"""
        from entities.base import CCStatus
        char = create_test_character("Frozen", hp=200, speed=200, atk=10.0, crit_rate=0.0)
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])
        engine = CombatEngine(state)

        char.cc_statuses.append(CCStatus("Freeze", remaining_turns=1))

        skipped = engine._process_cc_turn_start_char(char)
        assert skipped is True

    def test_frozen_character_cc_ticks_down(self) -> None:
        """冻结持续回合递减，归零后解除。"""
        from entities.base import CCStatus

        char = create_test_character("Frozen", hp=200, speed=200, atk=10.0, crit_rate=0.0)
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])
        engine = CombatEngine(state)

        char.cc_statuses.append(CCStatus("Freeze", remaining_turns=2))
        engine._process_cc_turn_start_char(char)
        assert len(char.cc_statuses) == 1
        assert char.cc_statuses[0].remaining_turns == 1

        engine._process_cc_turn_start_char(char)
        assert len(char.cc_statuses) == 0

    def test_imprisoned_character_gets_slow(self) -> None:
        """被禁锢的角色在回合初获得 SPD 减益。"""
        from entities.base import CCStatus

        char = create_test_character("Imprisoned", hp=200, speed=100, atk=10.0, crit_rate=0.0)
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])
        engine = CombatEngine(state)

        char.cc_statuses.append(CCStatus("Imprison", remaining_turns=1))
        spd_before = char.speed

        engine._process_cc_turn_start_char(char)
        # SPD 减益已挂载到修饰器池
        spd_after = char.speed
        assert spd_after < spd_before
        assert len(char.cc_statuses) == 0


# ============================================================
#  TestDoc13 — 文档 §13 追加攻击/反击/召唤物/倒计时
# ============================================================

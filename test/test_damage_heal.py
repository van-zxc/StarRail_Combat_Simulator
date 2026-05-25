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


class TestDoTSystem:
    """验证 DoT 挂载、叠层、衰减、以及 DOT 不暴击。"""

    def _make_attacker(self) -> Character:
        """ATK=2000, DMG_BONUS=50%, CR=100%, CD=200%。"""
        char = create_test_character(
            "Attacker", hp=200, speed=100, atk=2000.0,
            crit_rate=1.0, crit_dmg=2.0,
            element=ElementType.LIGHTNING, level=80,
        )
        char.stats.add_modifier(StatModifier(
            StatType.DMG_BONUS, StatModifierType.FLAT, 0.50, source="Test",
        ))
        return char

    def _make_defender(self) -> Enemy:
        """95 级无弱点敌人 (非击破)。"""
        return Enemy(
            name="Boss", hp=100000, speed=50, base_damage=0, level=95,
            weaknesses=[ElementType.FIRE],
        )

    # ── 测试 1: 直伤包含暴击 ──
    def test_direct_damage_includes_crit(self) -> None:
        char = self._make_attacker()
        enemy = self._make_defender()
        state = GameState(characters=[char], enemies=[enemy])

        damage, is_crit, _, _ = state.execute_action(
            char, ActionType.BASIC_ATTACK, enemy, skill_multiplier=2.0,
            damage_type=DamageType.DIRECT,
        )
        assert is_crit is True

    # ── 测试 2: DoT 不暴击 ──
    def test_dot_skips_crit(self) -> None:
        char = self._make_attacker()
        enemy = self._make_defender()
        state = GameState(characters=[char], enemies=[enemy])

        # DoT base = 2000 * 1.0 * 1 = 2000
        damage, is_crit, _, _ = state.execute_action(
            char, ActionType.BASIC_ATTACK, enemy, skill_multiplier=0.0,
            damage_type=DamageType.DOT,
            base_damage_override=2000,
            element_override=ElementType.LIGHTNING,
        )
        assert is_crit is False

        # 手动验证 DoT 伤害 (不含暴击):
        # base=2000 → dmg_bonus: 2000*1.5=3000
        # vul=1.0 → 3000
        # def: 1000/(1150+1000)=0.46512, int(3000*0.46512)=1395
        # res: base_res=0.2 (无弱点), 1.0-0.2=0.8, int(1395*0.8)=1116
        # tough: 0.9, int(1116*0.9)=1004
        # crit: 1.0, 1004
        assert damage == 1004

    # ── 测试 3: apply_dot 叠层 + 衰减 ──
    def test_apply_dot_stacks_and_tick_down(self) -> None:
        char = self._make_attacker()
        enemy = self._make_defender()
        state = GameState(characters=[char], enemies=[enemy])

        # 挂载 2 层 Lightning DoT (mult=1.0, duration=2)
        enemy.apply_dot(DoTStatus(
            source_character=char, element=ElementType.LIGHTNING,
            dot_multiplier=1.0, stacks=2, duration=2,
        ))

        assert len(enemy.dot_statuses) == 1
        assert enemy.dot_statuses[0].stacks == 2
        assert enemy.dot_statuses[0].duration == 2

        # 第一次 tick: 基础 = 2000 * 1.0 * 2 = 4000
        logs = state.resolve_enemy_dot_ticks(enemy)
        assert len(logs) == 1
        assert logs[0]["base"] == 4000
        assert logs[0]["stacks"] == 2
        assert len(enemy.dot_statuses) == 1
        assert enemy.dot_statuses[0].duration == 1

        # 第二次 tick: duration → 0 → 移除
        logs = state.resolve_enemy_dot_ticks(enemy)
        assert len(logs) == 1
        assert len(enemy.dot_statuses) == 0

    # ── 测试 4: 同来源同元素 DoT 叠加而非重复 ──
    def test_apply_dot_same_source_merges(self) -> None:
        char = self._make_attacker()
        enemy = self._make_defender()

        enemy.apply_dot(DoTStatus(char, ElementType.LIGHTNING, 1.0, 1, 2))
        enemy.apply_dot(DoTStatus(char, ElementType.LIGHTNING, 1.0, 1, 3))

        assert len(enemy.dot_statuses) == 1
        assert enemy.dot_statuses[0].stacks == 2
        assert enemy.dot_statuses[0].duration == 3  # max(2, 3)

    # ── 测试 5: DoT 在 action_log 中记录 ──
    def test_dot_logged_in_action_log(self) -> None:
        char = self._make_attacker()
        enemy = self._make_defender()
        state = GameState(characters=[char], enemies=[enemy])
        engine = CombatEngine(state)

        enemy.apply_dot(DoTStatus(char, ElementType.LIGHTNING, 1.0, 1, 1))
        engine.turn_count = 5
        engine._resolve_enemy_dot_ticks(enemy)

        log_entry = engine.action_log[0]
        assert log_entry["action"] == "DOT_TICK"
        assert log_entry["dot_element"] == "LIGHTNING"
        assert log_entry["dot_stacks"] == 1


# ============================================================
#  TestAVSystem — AV 轮次 & 速度动态折算
# ============================================================


class TestAdditionalDMG:
    """验证 ADDITIONAL_DMG 只享受通用增伤、可暴击、不触发 on_attack。"""

    def _make_attacker(self) -> Character:
        """ALL_DMG=20%, SKILL_DMG=50%, CR=100%, CD=100%。"""
        char = create_test_character(
            "Attacker", hp=200, speed=100, atk=100.0,
            crit_rate=1.0, crit_dmg=1.0,
            element=ElementType.PHYSICAL, level=1,   # level=1 对齐防御公式
        )
        char.stats.add_modifier(StatModifier(
            StatType.DMG_BONUS, StatModifierType.FLAT, 0.20, source="Test",
        ))
        char.stats.add_modifier(StatModifier(
            StatType.SKILL_DMG, StatModifierType.FLAT, 0.50, source="Test",
        ))
        return char

    def _make_defender(self) -> Enemy:
        return Enemy(name="Dummy", hp=10000, speed=50, base_damage=0, level=1,
                      weaknesses=[ElementType.PHYSICAL])

    # ── 测试 1: 战技直伤包含通用 + 战技增伤 ──
    def test_skill_direct_includes_both_bonuses(self) -> None:
        char = self._make_attacker()
        enemy = self._make_defender()
        state = GameState(characters=[char], enemies=[enemy])

        damage, is_crit, _, _ = state.execute_action(
            char, ActionType.SKILL, enemy, skill_multiplier=1.0,
            damage_type=DamageType.DIRECT,
        )
        # base=100, dmg_bonus=1.0+0.20+0.50=1.70→170
        # vul=1.0, def=(1*10+200)/(210+210)=0.5→85
        # res=1.0, tough=0.9→76
        # crit=2.0→152
        assert is_crit
        # step-by-step: 100→170→85→76→152
        assert damage == 152

    # ── 测试 2: 附加伤害只含通用增伤 + 可暴击 ──
    def test_additional_dmg_only_universal_bonus(self) -> None:
        char = self._make_attacker()
        enemy = self._make_defender()
        state = GameState(characters=[char], enemies=[enemy])

        damage, is_crit, _, _ = state.execute_action(
            char, ActionType.SKILL, enemy, skill_multiplier=1.0,
            damage_type=DamageType.ADDITIONAL_DMG,
        )
        # 基础由 override 或 ATK*mult 决定 (此处 ATK*1.0=100)
        # dmg_bonus: 仅通用 0.20 → 1.20, 100*1.20=120
        # def*0.5=60, res=1.0, tough*0.9=54, crit*2.0=108
        assert is_crit
        assert damage == 108

    # ── 测试 3: 附加伤害不触发 on_attack ──
    def test_additional_dmg_no_energy_sp_change(self) -> None:
        char = self._make_attacker()
        enemy = self._make_defender()
        state = GameState(characters=[char], enemies=[enemy])

        sp_before = state.skill_points
        energy_before = char.energy

        state.execute_action(
            char, ActionType.SKILL, enemy, skill_multiplier=1.0,
            damage_type=DamageType.ADDITIONAL_DMG,
        )

        # 附加伤害不应消耗/恢复 SP，不应给能量
        assert state.skill_points == sp_before
        assert char.energy == energy_before


# ============================================================
#  TestAggroSystem — 仇恨值 & 索敌优先级
# ============================================================


class TestHealingSystem:
    """验证治疗量计算、乘区加成、cap 限制。"""

    # ── 测试 1: 治疗量公式与乘区 ──
    def test_heal_formula_with_multipliers(self) -> None:
        healer = create_test_character("Healer", hp=3000, speed=100, atk=50.0)
        healer.stats.add_modifier(StatModifier(
            StatType.OUTGOING_HEALING_BOOST, StatModifierType.FLAT, 0.20, source="Test"))

        target = create_test_character("Target", hp=1000, speed=100, atk=50.0, level=1)
        # HP 设为 1000/5000
        target.max_hp = 5000
        target.hp = 1000
        target.stats.add_modifier(StatModifier(
            StatType.INCOMING_HEALING_BOOST, StatModifierType.FLAT, 0.10, source="Test"))
        target.stats.add_modifier(StatModifier(
            StatType.INCOMING_HEALING_REDUCTION, StatModifierType.FLAT, 0.50, source="Debuff"))

        state = GameState(characters=[healer, target], enemies=[])

        # Base: 3000*0.1 + 200 = 500
        # Mult: 1 + 0.20 + 0.10 - 0.50 = 0.80
        # Final: int(500 * 0.80) = 400
        actual = state.calculate_and_apply_heal(healer, target, 3000, 0.1, 200)
        assert actual == 400
        assert target.hp == 1400

    # ── 测试 2: 治疗不溢出 max_hp ──
    def test_heal_cannot_exceed_max_hp(self) -> None:
        healer = create_test_character("Healer", hp=3000, speed=100, atk=50.0)
        target = create_test_character("Target", hp=5000, speed=100, atk=50.0, level=1)
        target.max_hp = 5000
        target.hp = 1000

        state = GameState(characters=[healer, target], enemies=[])

        # 5000 点超量治疗
        actual = state.calculate_and_apply_heal(healer, target, 5000, 1.0, 0)
        assert actual == 4000  # capped at max_hp - current
        assert target.hp == 5000


# ============================================================
#  TestJointAttackSystem — 连携攻击
# ============================================================


class TestTrueDamage:
    """验证 TRUE_DMG_BONUS 作为独立乘区生效。"""

    def test_true_dmg_multiplier(self) -> None:
        char = create_test_character("TD", hp=200, speed=100, atk=100.0, crit_rate=0.0)
        char.stats.add_modifier(StatModifier(
            StatType.TRUE_DMG_BONUS, StatModifierType.FLAT, 0.20, source="Test"))
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])

        state = GameState(characters=[char], enemies=[enemy])
        damage, _, _, _ = state.execute_action(char, ActionType.BASIC_ATTACK, enemy, 1.0)

        # 无 true_dmg 时: 100→100, vul=1.0, def*0.5=50, res=1.0, tough*0.9=45
        # 有 true_dmg 时: 45 * 1.20 = 54
        assert damage == 54


# ============================================================
#  TestShieldAbsorptionInTakeDamage — 护盾吸收下沉至 Fighter
# ============================================================

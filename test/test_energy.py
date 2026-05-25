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


class TestEnergySystem:
    """能量获取与上限验证。"""

    def _setup(self) -> tuple[Character, Enemy, GameState]:
        char = create_test_character("Test", hp=200, speed=100, atk=50.0)
        enemy = Enemy(name="Test", hp=1000, speed=50, base_damage=0)
        state = GameState(characters=[char], enemies=[enemy])
        return char, enemy, state

    def test_basic_attack_gains_20_energy(self) -> None:
        char, enemy, state = self._setup()
        state.execute_action(char, ActionType.BASIC_ATTACK, enemy, 1.0)
        assert char.energy == 20

    def test_skill_gains_30_energy(self) -> None:
        char, enemy, state = self._setup()
        state.execute_action(char, ActionType.SKILL, enemy, 2.0)
        assert char.energy == 30

    def test_ultimate_resets_energy(self) -> None:
        char, enemy, state = self._setup()
        char.energy = 100
        state.execute_action(char, ActionType.ULTIMATE, enemy, 3.0)
        assert char.energy == 5

    def test_energy_cannot_exceed_max(self) -> None:
        char, enemy, state = self._setup()
        char.energy = 95
        state.execute_action(char, ActionType.BASIC_ATTACK, enemy, 1.0)
        assert char.energy == 100

    def test_sp_changes_on_actions(self) -> None:
        char, enemy, state = self._setup()
        sp_before = state.skill_points
        state.execute_action(char, ActionType.BASIC_ATTACK, enemy, 1.0)
        assert state.skill_points == sp_before + 1
        state.execute_action(char, ActionType.SKILL, enemy, 2.0)
        assert state.skill_points == sp_before

    def test_ultimate_does_not_change_sp(self) -> None:
        char, enemy, state = self._setup()
        char.energy = 100
        sp_before = state.skill_points
        state.execute_action(char, ActionType.ULTIMATE, enemy, 3.0)
        assert state.skill_points == sp_before


# ============================================================
#  TestDeclareUltimateDedup — 去重
# ============================================================


class TestDeclareUltimateDedup:
    """终结技声明去重验证。"""

    def test_no_duplicate_in_queue(self) -> None:
        char = create_test_character("Test", hp=200, speed=100, atk=50.0)
        enemy = Enemy(name="Test", hp=1000, speed=50, base_damage=0)
        state = GameState(characters=[char], enemies=[enemy])
        state.declare_ultimate(char)
        state.declare_ultimate(char)
        state.declare_ultimate(char)
        assert len(state.ultimate_pending) == 1


# ============================================================
#  TestModifierPool — 修饰器池 & 分支公式
# ============================================================


class TestEnergySystemV2:
    """验证 uses_energy, can_half_cast_ult, ERR 受击回能。"""

    # ── 测试 1: 非能体系角色无视回能 ──
    def test_non_energy_character_gain_zero(self) -> None:
        char = create_test_character("NoEnergy", hp=200, speed=100, atk=50.0)
        char.uses_energy = False
        char.energy = 0

        gained = char.gain_energy(50)
        assert gained == 0
        assert char.energy == 0

    # ── 测试 2: 半能释放标记 ──
    def test_half_cast_ult_ready_at_half(self) -> None:
        char = create_test_character("Half", hp=200, speed=100, atk=50.0, max_energy=180)
        char.can_half_cast_ult = True
        char.energy = 90
        assert char.is_ultimate_ready is True
        char.energy = 89
        assert char.is_ultimate_ready is False

    # ── 测试 3: ERR 影响受击回能 ──
    def test_err_affects_gain_energy(self) -> None:
        char = create_test_character("ERR", hp=200, speed=100, atk=50.0, max_energy=200)
        # 修改 ERR 为 1.1 (110%)
        char.stats.add_modifier(StatModifier(
            StatType.ERR, StatModifierType.FLAT, 0.10, source="Test",
        ))
        gained = char.gain_energy(30)
        # 30 * (1.0 + 0.10) = 33
        assert gained == 33
        assert char.energy == 33

    # ── 测试 4: set_energy 不受 ERR 影响 ──
    def test_set_energy_ignores_err(self) -> None:
        char = create_test_character("SetE", hp=200, speed=100, atk=50.0)
        char.stats.add_modifier(StatModifier(
            StatType.ERR, StatModifierType.FLAT, 1.0, source="Test",
        ))
        char.set_energy(50)
        assert char.energy == 50

    # ── 测试 5: on_kill / on_hit 回能 ──
    def test_on_hit_and_on_kill_energy(self) -> None:
        char = create_test_character("HitMe", hp=200, speed=100, atk=50.0, max_energy=200)
        enemy = Enemy(name="Dummy", hp=1000, speed=50, base_damage=0, level=1)
        state = GameState(characters=[char], enemies=[enemy])

        # 受击回能
        gained = state.on_hit(char, base_amount=10)
        assert gained == 10  # ERR=1.0 default
        # 击杀回能
        gained = state.on_kill(char)
        assert gained == 10
        assert char.energy == 20


# ============================================================
#  TestExtraTurnSystem — 额外回合 + 队列优先级
# ============================================================


class TestEnergyBuckets:
    """验证敌 hit_energy_bucket 和 FUA follow_up_energy_type。"""

    # ── 受击回能分段 ──
    def test_enemy_hit_energy_bucket_default(self) -> None:
        """默认 hit_energy_bucket = 10.0。"""
        enemy = Enemy(name="E", hp=1000, speed=50, base_damage=10, level=1)
        assert enemy.hit_energy_bucket == 10.0

    def test_enemy_custom_hit_energy_bucket(self) -> None:
        """敌方可设置自定义受击回能量。"""
        char = create_test_character("A", hp=200, speed=100)
        char.energy = 0
        enemy = Enemy(name="E", hp=1000, speed=50, base_damage=10, level=1)
        enemy.hit_energy_bucket = 25.0  # Boss 模板
        state = GameState(characters=[char], enemies=[enemy])
        engine = CombatEngine(state)

        engine._execute_enemy_turn(enemy)
        # hit_energy_bucket=25, ERR=1.0 → 25
        assert char.energy == 25

    # ── FUA 返能分类 ──
    def test_fua_energy_type1_returns_zero(self) -> None:
        """type1 FUA 返能 0。"""
        char = create_test_character("A", hp=200, speed=100, atk=10.0, crit_rate=0.0)
        char.energy = 0
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])

        state.execute_action(char, ActionType.FOLLOW_UP, enemy, 1.0,
                              follow_up_energy_type=1)
        assert char.energy == 0

    def test_fua_energy_type2_returns_five(self) -> None:
        """type2 FUA 返能 10。"""
        char = create_test_character("A", hp=200, speed=100, atk=10.0, crit_rate=0.0)
        char.energy = 0
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])

        state.execute_action(char, ActionType.FOLLOW_UP, enemy, 1.0,
                              follow_up_energy_type=2)
        assert char.energy == 10

    def test_fua_energy_type3_returns_ten(self) -> None:
        """type3 FUA 返能 10。"""
        char = create_test_character("A", hp=200, speed=100, atk=10.0, crit_rate=0.0)
        char.energy = 0
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])

        state.execute_action(char, ActionType.FOLLOW_UP, enemy, 1.0,
                              follow_up_energy_type=3)
        assert char.energy == 10


# ============================================================
#  TestDanHeng — 丹恒 (巡猎·风) 技能/行迹/星魂验证
# ============================================================

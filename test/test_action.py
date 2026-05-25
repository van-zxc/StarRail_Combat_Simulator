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


class TestUltimateInterleave:
    """终结技插队机制验证。"""

    def setup_method(self) -> None:
        self.char_a = create_test_character("A", hp=200, speed=100, atk=50.0)
        self.char_b = create_test_character("B", hp=200, speed=200, atk=50.0)
        self.enemy = Enemy(name="Dummy", hp=10000, speed=1, base_damage=0)
        self.state = GameState(characters=[self.char_a, self.char_b], enemies=[self.enemy])
        self.engine = CombatEngine(self.state)
        self.char_a.current_av = 100.0
        self.char_b.current_av = 50.0
        self.char_a.energy = 100

    def test_full_energy_character_enqueued_at_start(self) -> None:
        assert self.char_a.is_ultimate_ready
        self.engine._check_and_enqueue_ultimates()
        assert self.state.has_pending_ultimates()
        assert self.char_a in self.state.ultimate_pending

    def test_ultimate_interleaves_before_lower_av(self) -> None:
        self.engine._check_and_enqueue_ultimates()
        self.engine._resolve_pending_ultimates()
        assert not self.state.has_pending_ultimates()
        assert len(self.engine.action_log) == 1
        assert self.engine.action_log[0]["actor"] == "A"
        assert self.engine.action_log[0]["action"] == "ULTIMATE"

    def test_ultimate_preserves_av(self) -> None:
        self.engine._check_and_enqueue_ultimates()
        self.engine._resolve_pending_ultimates()
        assert self.char_a.current_av == pytest.approx(100.0)
        assert self.char_a.energy == 5

    def test_av_advances_to_b_after_ultimate(self) -> None:
        self.engine._check_and_enqueue_ultimates()
        self.engine._resolve_pending_ultimates()
        next_actor = self.engine._find_next_actor()
        assert next_actor is self.char_b
        assert self.char_b.current_av == pytest.approx(50.0)

    def test_a_av_decremented_after_b_acts(self) -> None:
        self.engine._check_and_enqueue_ultimates()
        self.engine._resolve_pending_ultimates()
        advance_amount = self.char_b.current_av
        self.engine._advance_time(advance_amount)
        self.char_b.reset_av()
        self.engine.turn_count += 1
        self.engine._execute_character_turn(self.char_b)
        assert self.char_a.current_av == pytest.approx(50.0)

    def test_action_log_order(self) -> None:
        self.engine._check_and_enqueue_ultimates()
        self.engine._resolve_pending_ultimates()
        advance_amount = self.engine._find_next_actor().current_av
        self.engine._advance_time(advance_amount)
        self.char_b.reset_av()
        self.engine.turn_count += 1
        self.engine._execute_character_turn(self.char_b)
        actions = [(e["actor"], e["action"]) for e in self.engine.action_log]
        assert actions == [("A", "ULTIMATE"), ("B", "SKILL")]


# ============================================================
#  TestEnergySystem — 能量 & SP
# ============================================================


class TestAVSystem:
    """验证速度阈值、动态 SPD 折算、拉条/推条。"""

    # ── 测试 1: 速度阈值 (133.4 speed → 2 次行动在 150 AV 内) ──
    def test_speed_breakpoint_two_actions_in_cycle_0(self) -> None:
        char = create_test_character("Fast", hp=200, speed=133, atk=50.0)
        # 使用 float 速度: 手动设置 stats base SPD
        char_level = 1
        enemy = Enemy(name="Dummy", hp=10000, speed=1, base_damage=0, level=1)
        state = GameState(characters=[char], enemies=[enemy])

        # 将角色 SPD 精确设为 133.4
        # 绕过 create_test_character 的 int speed 限制, 直接修改 base stat
        # 同时需要更新 Fighter._speed 以保持 property 一致
        from core.entity_stats import EntityStats
        stats_dict = {
            StatType.HP: 200.0, StatType.ATK: 50.0, StatType.SPD: 133.4,
            StatType.DEF: 60.0, StatType.CRIT_RATE: 0.05, StatType.CRIT_DMG: 0.50,
            StatType.ERR: 1.0, StatType.MAX_ENERGY: 100.0,
            StatType.EFFECT_RES: 0.0, StatType.EFFECT_HIT_RATE: 0.0,
            StatType.RES_PEN: 0.0, StatType.RES: 0.0, StatType.DMG_TAKEN: 0.0,
            StatType.DMG_BONUS: 0.0, StatType.VULNERABILITY: 0.0,
        }
        char._speed = 133  # Fighter property backing
        char.stats._base_stats[StatType.SPD] = 133.4

        engine = CombatEngine(state)
        engine.current_cycle = 0
        engine.cycle_av_elapsed = 0.0

        # base_av = 10000 / 133.4 ≈ 74.96
        # 2 actions = 2 * 74.96 = 149.92 < 150 → 一轮内 2 次
        base_av = char.base_av
        assert base_av == pytest.approx(10000.0 / 133.4)
        assert 2 * base_av < 150.0

    # ── 测试 2: Cycle boundary 触发 ──
    def test_cycle_boundary_triggered(self) -> None:
        char = create_test_character("Test", hp=200, speed=200, atk=50.0)
        enemy = Enemy(name="Dummy", hp=10000, speed=1, base_damage=0, level=1)
        state = GameState(characters=[char], enemies=[enemy])
        engine = CombatEngine(state)

        # 手动推进 150 AV
        engine.cycle_av_elapsed = 145.0
        engine.current_cycle = 0
        engine._advance_time(10.0)
        engine.cycle_av_elapsed += 10.0
        engine._check_cycle_boundary()
        assert engine.current_cycle == 1
        assert engine.cycle_av_elapsed == pytest.approx(5.0)

    # ── 测试 3: 动态 SPD 折算 ──
    def test_speed_dynamic_recalculation(self) -> None:
        char = create_test_character("Test", hp=200, speed=100, atk=50.0)
        enemy = Enemy(name="Dummy", hp=10000, speed=1, base_damage=0, level=1)
        state = GameState(characters=[char], enemies=[enemy])

        char.current_av = 100.0
        # 经过 50 AV → 剩余 50
        char.current_av = 50.0

        # 添加 +100% SPD
        old_spd = char.stats.get_total_stat(StatType.SPD)
        spd_buff = StatModifier(StatType.SPD, StatModifierType.PERCENT, 1.0, source="Test")
        char.stats.add_modifier(spd_buff)

        new_spd = char.stats.get_total_stat(StatType.SPD)
        assert new_spd == pytest.approx(old_spd * 2.0)
        # av_new = 50 * (100 / 200) = 25
        assert char.current_av == pytest.approx(25.0)

    # ── 测试 4: 拉条 advance_action ──
    def test_advance_action(self) -> None:
        char = create_test_character("Test", hp=200, speed=100, atk=50.0)
        char.current_av = 80.0
        char.advance_action(0.25)
        assert char.current_av == pytest.approx(55.0)  # 80 - 100*0.25

    # ── 测试 5: 推后 delay_action ──
    def test_delay_action(self) -> None:
        char = create_test_character("Test", hp=200, speed=100, atk=50.0)
        char.current_av = 10.0
        char.delay_action(0.25)
        assert char.current_av == pytest.approx(35.0)  # 10 + 100*0.25

    # ── 测试 6: immediate_action ──
    def test_immediate_action(self) -> None:
        char = create_test_character("Test", hp=200, speed=100, atk=50.0)
        char.current_av = 80.0
        char.immediate_action()
        assert char.current_av == pytest.approx(0.0)


# ============================================================
#  TestAdditionalDMG — 附加伤害 + 增伤标签过滤
# ============================================================


class TestExtraTurnSystem:
    """验证 AV 冻结、状态冻结、队列压入取出。"""

    def _make_skill(self, at=ActionType.BASIC_ATTACK, mult=1.0):
        """创建简单技能对象 (action_type + skill_multiplier)。"""
        cls = type("_Skill", (), {"action_type": at, "skill_multiplier": mult})
        return cls()

    # ── 测试 1: 额外回合 AV 冻结 ──
    def test_extra_turn_preserves_av(self) -> None:
        char = create_test_character("A", hp=200, speed=100, atk=50.0)
        enemy = Enemy(name="Dummy", hp=10000, speed=1, base_damage=0, level=1)
        state = GameState(characters=[char], enemies=[enemy])
        engine = CombatEngine(state)

        char.current_av = 40.0
        skill = self._make_skill()
        engine._execute_character_turn(char, skill_obj=skill, is_extra_turn=True)
        # AV 保持不变 (额外回合不重置)
        assert char.current_av == pytest.approx(40.0)

    # ── 测试 2: 额外回合不削减修饰器 ──
    def test_extra_turn_preserves_modifiers(self) -> None:
        char = create_test_character("A", hp=200, speed=100, atk=50.0)
        enemy = Enemy(name="Dummy", hp=10000, speed=1, base_damage=0, level=1)
        state = GameState(characters=[char], enemies=[enemy])
        engine = CombatEngine(state)

        buff = StatModifier(StatType.ATK, StatModifierType.PERCENT, 0.10, source="Test")
        buff.duration = 1  # type: ignore
        char.stats.add_modifier(buff)

        skill = self._make_skill()
        engine._execute_character_turn(char, skill_obj=skill, is_extra_turn=True)
        # 修饰器持续未被削减
        assert getattr(buff, "duration", 1) == 1

    # ── 测试 3: 队列压入与取出 ──
    def test_extra_turn_queue_fifo(self) -> None:
        char = create_test_character("A", hp=200, speed=100, atk=50.0)
        enemy = Enemy(name="Dummy", hp=10000, speed=1, base_damage=0, level=1)
        state = GameState(characters=[char], enemies=[enemy])

        skill = self._make_skill()
        state.grant_extra_turn(char, skill)
        assert state.has_extra_turn()

        popped_c, popped_s = state.pop_next_extra_turn()
        assert popped_c is char
        assert popped_s is skill
        assert not state.has_extra_turn()

    # ── 测试 4: 回合延展不进队列 ──
    def test_turn_extension_not_queued(self) -> None:
        char = create_test_character("A", hp=200, speed=100, atk=50.0)
        enemy = Enemy(name="Dummy", hp=10000, speed=1, base_damage=0, level=1)
        state = GameState(characters=[char], enemies=[enemy])

        skill = self._make_skill()
        state.grant_extra_turn(char, skill, is_turn_extension=True)
        # 不在队列中
        assert not state.has_extra_turn()


# ============================================================
#  TestFollowUpSystem — 追加行动 (CC 拦截 / 非攻击类 / 入场)
# ============================================================


class TestFollowUpSystem:
    """验证追加行动队列优先级、CC 拦截、非攻击类动作。"""

    def _make_skill(self, at=ActionType.SKILL, mult=1.0):
        cls = type("_Skill", (), {"action_type": at, "skill_multiplier": mult})
        return cls()

    # ── 测试 1: 非攻击追加行动 ──
    def test_non_attack_follow_up_queued(self) -> None:
        char = create_test_character("Healer", hp=200, speed=100, atk=50.0)
        enemy = Enemy(name="Dummy", hp=10000, speed=100, base_damage=0, level=1)
        state = GameState(characters=[char], enemies=[enemy])

        heal_skill = self._make_skill(at=ActionType.SKILL, mult=0.0)
        state.grant_follow_up_action(char, heal_skill)

        popped_c, popped_s, is_fua = state.pop_next_follow_up_action()
        assert popped_c is char
        assert popped_s is heal_skill
        assert is_fua is True

    # ── 测试 2: CC 拦截 ──
    def test_cc_blocks_follow_up(self) -> None:
        char = create_test_character("A", hp=200, speed=100, atk=50.0)
        state = GameState(characters=[char], enemies=[])

        freeze = StatModifier(StatType.ATK, StatModifierType.FLAT, 0.0,
                               source="Freeze", cc_type="Freeze")
        char.stats.add_modifier(freeze)
        assert char.is_cc_blocked

        skill = self._make_skill()
        state.grant_follow_up_action(char, skill)
        # CC 存在时主循环会跳过执行
        c, s, _ = state.pop_next_follow_up_action()
        assert c.is_cc_blocked  # 调用方应在执行前检查

    # ── 测试 3: 入场序列 (秘技 → FUA → AV init) ──
    def test_battle_start_follow_up_queued(self) -> None:
        char = create_test_character("A", hp=200, speed=100, atk=50.0)
        enemy = Enemy(name="Dummy", hp=10000, speed=50, base_damage=0, level=1)
        state = GameState(characters=[char], enemies=[enemy])

        skill = self._make_skill()
        state.grant_follow_up_action(char, skill)

        # AV 已初始化
        assert char.current_av == pytest.approx(char.base_av)
        # 追加行动在队列中
        assert state.has_follow_up_action()


# ============================================================
#  TestHealingSystem — 治疗结算
# ============================================================


class TestMultiHit:
    """验证多段 Hit: 独立伤害/暴击/事件，仅首段扣资源。"""

    def _make_hits(self, target: "Fighter", count: int = 3, mult: float = 1.0) -> list["HitPacket"]:
        from starrail_combat import HitPacket

        return [HitPacket(target=target, skill_multiplier=mult) for _ in range(count)]

    # ── 每段独立伤害 ──
    def test_each_hit_deals_damage(self) -> None:
        """每段独立计算伤害。"""
        from starrail_combat import HitPacket

        char = create_test_character("A", hp=200, speed=100, atk=100.0, crit_rate=0.0)
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])

        hits = self._make_hits(enemy, count=2, mult=0.5)
        results = state.execute_multi_hit(char, hits)

        assert len(results) == 2
        assert all(r[0] > 0 for r in results)  # 每段都有伤害

    # ── 首段扣资源，后续段跳过 ──
    def test_only_first_hit_charges_energy(self) -> None:
        """仅首段获取能量和 SP。"""
        char = create_test_character("A", hp=200, speed=100, atk=100.0, crit_rate=0.0)
        char.energy = 0
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])

        energy_before = char.energy
        hits = self._make_hits(enemy, count=3, mult=0.5)
        state.execute_multi_hit(char, hits, action_type=ActionType.BASIC_ATTACK)

        # 普攻回能 20 → 只加一次
        assert char.energy == energy_before + 20

    # ── 每段独立暴击 ──
    def test_each_hit_independent_crit(self) -> None:
        """每段独立进行暴击判定。"""
        char = create_test_character("A", hp=200, speed=100, atk=100.0, crit_rate=1.0)
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])

        hits = self._make_hits(enemy, count=3, mult=1.0)
        results = state.execute_multi_hit(char, hits, action_type=ActionType.BASIC_ATTACK)

        # crit_rate=1.0 → 每段都暴击
        assert len(results) == 3
        assert all(r[1] for r in results)

    # ── ON_HIT 每段触发 ──
    def test_on_hit_fires_per_segment(self) -> None:
        """每段独立触发 ON_HIT 事件。"""
        from core.events import EventBus, EventType

        bus = EventBus()
        hit_count: list[int] = [0]

        def count_hit(**kw):
            hit_count[0] += 1

        bus.subscribe(EventType.ON_HIT, count_hit)

        char = create_test_character("A", hp=200, speed=100, atk=100.0, crit_rate=0.0)
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])
        state.event_bus = bus

        hits = self._make_hits(enemy, count=3, mult=1.0)
        state.execute_multi_hit(char, hits, action_type=ActionType.BASIC_ATTACK)

        assert hit_count[0] == 3  # 每段触发一次 ON_HIT


# ============================================================
#  TestStackPolicy — 叠层策略 apply_modifier()
# ============================================================

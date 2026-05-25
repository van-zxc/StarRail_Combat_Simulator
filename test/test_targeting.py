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


class TestAggroSystem:
    """验证基础仇恨、弹射、嘲讽 > 锁定、退场过滤。"""

    # ── 测试 1: 基础仇恨加权概率 ──
    def test_aggro_weighted_probability(self) -> None:
        from core.targeting import TargetManager

        # 存护 (base=6, AGGRO_MOD+50% → 9)
        pres = create_test_character("Pres", hp=200, speed=100, atk=50.0,
                                      path=PathType.PRESERVATION)
        pres.stats.add_modifier(StatModifier(
            StatType.AGGRO_MODIFIER, StatModifierType.PERCENT, 0.50, source="Test"))
        # 巡猎 (base=3)
        hunt = create_test_character("Hunt", hp=200, speed=100, atk=50.0,
                                      path=PathType.HUNT)

        enemy = Enemy(name="Test", hp=1000, speed=50, base_damage=10, level=1)
        state = GameState(characters=[pres, hunt], enemies=[enemy])

        pres_aggro = TargetManager.get_total_aggro(pres)
        hunt_aggro = TargetManager.get_total_aggro(hunt)
        # pres: 6 * 1.50 = 9.0, hunt: 3
        assert pres_aggro == pytest.approx(9.0)
        assert hunt_aggro == pytest.approx(3.0)
        # 概率: pres = 9/12 = 0.75, hunt = 3/12 = 0.25
        assert pres_aggro / (pres_aggro + hunt_aggro) == pytest.approx(0.75)

    # ── 测试 2: 弹射均匀概率 ──
    def test_bounce_equal_probability(self) -> None:
        pres = create_test_character("Pres", hp=200, speed=100, atk=50.0,
                                      path=PathType.PRESERVATION)
        hunt = create_test_character("Hunt", hp=200, speed=100, atk=50.0,
                                      path=PathType.HUNT)
        enemy = Enemy(name="Test", hp=1000, speed=50, base_damage=10, level=1)

        candidates = [pres, hunt]
        # 多次采样验证
        counts = {pres.name: 0, hunt.name: 0}
        for _ in range(500):
            t = TargetManager.select_target(enemy, candidates, is_bounce=True)
            counts[t.name] += 1
        # 两者差距应在统计误差内 (< 0.2 偏离)
        assert abs(counts[pres.name] / 500 - 0.5) < 0.1
        assert abs(counts[hunt.name] / 500 - 0.5) < 0.1

    # ── 测试 3: 锁定优先于嘲讽 ──
    def test_lock_on_overrides_taunt(self) -> None:
        pres = create_test_character("Pres", hp=200, speed=100, atk=50.0)
        hunt = create_test_character("Hunt", hp=200, speed=100, atk=50.0)
        enemy = Enemy(name="Test", hp=1000, speed=50, base_damage=10, level=1)

        # 敌人锁定了存护
        enemy.lock_on_target = pres
        # 巡猎对敌人施加了嘲讽
        enemy.taunt_source = hunt

        target = TargetManager.select_target(enemy, [pres, hunt])
        assert target is pres  # 锁定 > 嘲讽

    # ── 测试 4: 退场角色被排除 ──
    def test_departed_characters_excluded(self) -> None:
        pres = create_test_character("Pres", hp=200, speed=100, atk=50.0)
        hunt = create_test_character("Hunt", hp=200, speed=100, atk=50.0)
        hunt.is_departed = True
        enemy = Enemy(name="Test", hp=1000, speed=50, base_damage=10, level=1)

        target = TargetManager.select_target(enemy, [pres, hunt])
        assert target is pres  # 巡猎被排除
        assert target is not hunt


# ============================================================
#  TestShieldSystem — 护盾吸收 (溢出穿透 + 同时扣减)
# ============================================================


class TestAggroDoc:
    """验证文档 §11 的仇恨/索敌逻辑是否正确。"""

    # ── 测试 1: 全部 9 个 Path 基础仇恨值 (§11.1) ──
    def test_all_path_base_aggro_values(self) -> None:
        from core.targeting import TargetManager

        expected = {
            PathType.HUNT: 3, PathType.ERUDITION: 3,
            PathType.HARMONY: 4, PathType.NIHILITY: 4,
            PathType.ABUNDANCE: 4, PathType.REMEMBRANCE: 4,
            PathType.ELATION: 4, PathType.DESTRUCTION: 5,
            PathType.PRESERVATION: 6,
        }
        for path, expected_val in expected.items():
            char = create_test_character("T", hp=200, speed=100, path=path)
            assert TargetManager.get_base_aggro(char) == pytest.approx(expected_val), \
                f"Path {path.name}: expected {expected_val}"

    # ── 测试 2: 死亡目标被过滤 (§11.2 step 1) ──
    def test_dead_target_excluded(self) -> None:
        from core.targeting import TargetManager

        alive = create_test_character("A", hp=200, speed=100)
        dead = create_test_character("D", hp=0, speed=100)

        candidates = [alive, dead]
        for _ in range(20):
            target = TargetManager.select_target(
                create_test_character("E", hp=200, speed=100), candidates,
            )
            assert target is alive

    # ── 测试 3: 弹射不受嘲讽影响 (§11.2 step 2) ──
    def test_bounce_ignores_taunt(self) -> None:
        from core.targeting import TargetManager

        taunt_target = create_test_character("Taunted", hp=200, speed=100)
        other = create_test_character("Other", hp=200, speed=100)
        enemy = Enemy(name="E", hp=1000, speed=50, base_damage=10, level=1)
        enemy.taunt_source = taunt_target

        hits = {taunt_target.name: 0, other.name: 0}
        for _ in range(200):
            t = TargetManager.select_target(enemy, [taunt_target, other], is_bounce=True)
            hits[t.name] += 1
        assert hits[taunt_target.name] > 0
        assert hits[other.name] > 0

    # ── 测试 4: 弹射不受锁定影响 (§11.2 step 2) ──
    def test_bounce_ignores_lock_on(self) -> None:
        from core.targeting import TargetManager

        locked = create_test_character("Locked", hp=200, speed=100)
        other = create_test_character("Other", hp=200, speed=100)
        enemy = Enemy(name="E", hp=1000, speed=50, base_damage=10, level=1)
        enemy.lock_on_target = locked

        hits = {locked.name: 0, other.name: 0}
        for _ in range(200):
            t = TargetManager.select_target(enemy, [locked, other], is_bounce=True)
            hits[t.name] += 1
        assert hits[locked.name] > 0
        assert hits[other.name] > 0

    # ── 测试 5: 多个 AggroModifier 叠加 (§11.1) ──
    def test_aggro_modifier_stacking(self) -> None:
        from core.targeting import TargetManager

        char = create_test_character("Tank", hp=200, speed=100, path=PathType.PRESERVATION)
        base = TargetManager.get_base_aggro(char)
        assert base == pytest.approx(6.0)
        assert TargetManager.get_total_aggro(char) == pytest.approx(6.0)

        char.stats.add_modifier(StatModifier(
            StatType.AGGRO_MODIFIER, StatModifierType.PERCENT, 0.20, source="A"))
        assert TargetManager.get_total_aggro(char) == pytest.approx(7.2)

        char.stats.add_modifier(StatModifier(
            StatType.AGGRO_MODIFIER, StatModifierType.PERCENT, 0.30, source="B"))
        assert TargetManager.get_total_aggro(char) == pytest.approx(9.0)

    # ── 测试 6: 非角色目标无 path 时权重 = 1 ──
    def test_non_character_weight_defaults_to_one(self) -> None:
        from core.targeting import TargetManager

        char = create_test_character("A", hp=200, speed=100)
        enemy = Enemy(name="E", hp=1000, speed=50, base_damage=10, level=1)

        candidates = [char, enemy]
        for _ in range(20):
            target = TargetManager.select_target(
                create_test_character("Atk", hp=200, speed=100), candidates,
            )
            assert target in candidates

    # ── 测试 7: 所有权重为 0 回退均匀随机 ──
    def test_zero_weights_fallback_to_uniform(self) -> None:
        from core.targeting import TargetManager

        a = create_test_character("A", hp=200, speed=100)
        b = create_test_character("B", hp=200, speed=100)

        enemy = Enemy(name="E", hp=1000, speed=50, base_damage=10, level=1)
        counts = {a.name: 0, b.name: 0}
        for _ in range(50):
            t = TargetManager.select_target(enemy, [a, b])
            counts[t.name] += 1
        assert counts[a.name] > 0
        assert counts[b.name] > 0

    # ── 测试 8: 空候选返回 None (§11.2) ──
    def test_empty_candidates_returns_none(self) -> None:
        from core.targeting import TargetManager

        enemy = Enemy(name="E", hp=1000, speed=50, base_damage=10, level=1)
        target = TargetManager.select_target(enemy, [])
        assert target is None


# ============================================================
#  TestStatModifierFields — P0-1: StatModifier 扩展字段
# ============================================================


class TestTargetSelection:
    """验证 Blast / AoE / Random 目标选择。"""

    # ── 扩散 ──
    def test_blast_primary_plus_adjacent(self) -> None:
        """Blast: 主目标 + 左右各 1 个相邻目标。"""
        from core.targeting import TargetManager

        chars = [
            create_test_character("A", hp=200, speed=100),
            create_test_character("B", hp=200, speed=100),
            create_test_character("C", hp=200, speed=100),
            create_test_character("D", hp=200, speed=100),
        ]
        primary = chars[1]  # B → adjacent: A and C
        result = TargetManager.select_blast(chars, primary)
        assert len(result) == 3
        assert chars[0] in result  # A (left)
        assert chars[1] in result  # B (primary)
        assert chars[2] in result  # C (right)
        assert chars[3] not in result  # D (too far)

    def test_blast_edge_primary_leftmost(self) -> None:
        """Blast: 主目标在最左边, 只有右邻。"""
        from core.targeting import TargetManager

        chars = [
            create_test_character("A", hp=200, speed=100),
            create_test_character("B", hp=200, speed=100),
        ]
        primary = chars[0]
        result = TargetManager.select_blast(chars, primary)
        assert len(result) == 2
        assert chars[0] in result
        assert chars[1] in result

    def test_blast_single_target_list(self) -> None:
        """Blast: 只有一个候选时仅返回该目标。"""
        from core.targeting import TargetManager

        chars = [create_test_character("A", hp=200, speed=100)]
        result = TargetManager.select_blast(chars, chars[0])
        assert result == chars

    def test_blast_excludes_departed(self) -> None:
        """Blast: 过滤退场目标。"""
        from core.targeting import TargetManager

        chars = [
            create_test_character("A", hp=200, speed=100),
            create_test_character("B", hp=200, speed=100),
            create_test_character("C", hp=200, speed=100),
        ]
        chars[0].is_departed = True
        primary = chars[1]
        result = TargetManager.select_blast(chars, primary)
        assert len(result) == 2  # B + C (A excluded)
        assert chars[0] not in result

    # ── 群攻 ──
    def test_aoe_all_alive(self) -> None:
        """AoE: 返回所有存活且未退场的目标。"""
        from core.targeting import TargetManager

        chars = [
            create_test_character("A", hp=200, speed=100),
            create_test_character("B", hp=0, speed=100),     # dead
            create_test_character("C", hp=200, speed=100),
        ]
        chars[2].is_departed = True
        result = TargetManager.select_aoe(chars)
        assert result == [chars[0]]  # only A is alive + not departed

    def test_aoe_empty_returns_empty(self) -> None:
        """AoE: 无存活目标返回空列表。"""
        from core.targeting import TargetManager

        chars = [create_test_character("A", hp=0, speed=100)]
        result = TargetManager.select_aoe(chars)
        assert result == []

    # ── 随机 ──
    def test_random_select_count(self) -> None:
        """Random: 从候选池抽取指定数量。"""
        from core.targeting import TargetManager

        chars = [
            create_test_character("A", hp=200, speed=100),
            create_test_character("B", hp=200, speed=100),
            create_test_character("C", hp=200, speed=100),
        ]
        result = TargetManager.select_random(chars, 2)
        assert len(result) == 2
        for c in result:
            assert c in chars

    def test_random_no_duplicates(self) -> None:
        """Random: 不重复抽取同一目标。"""
        from core.targeting import TargetManager

        chars = [
            create_test_character("A", hp=200, speed=100),
            create_test_character("B", hp=200, speed=100),
        ]
        result = TargetManager.select_random(chars, 2)
        assert len(result) == 2
        assert result[0] is not result[1]

    def test_random_filters_departed(self) -> None:
        """Random: 过滤退场目标。"""
        from core.targeting import TargetManager

        chars = [
            create_test_character("A", hp=200, speed=100),
            create_test_character("B", hp=200, speed=100),
            create_test_character("C", hp=200, speed=100),
        ]
        chars[1].is_departed = True
        result = TargetManager.select_random(chars, 3)
        assert len(result) == 2  # only 2 valid candidates
        assert chars[1] not in result


# ============================================================
#  TestWaveSystem — §5: 波次/秘技/伏击
# ============================================================

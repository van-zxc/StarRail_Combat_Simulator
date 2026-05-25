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


class TestEquipmentSystem:
    """验证白值（base）与绿值（total）的正确计算。"""

    def _make_character(self) -> Character:
        """创建一个基础角色：HP=500, ATK=100。"""
        return create_test_character("Tester", hp=500, speed=100, atk=100.0)

    def _make_light_cone(self) -> LightCone:
        return LightCone(
            id="TestLC",
            name="Test Light Cone",
            base_hp=300.0,
            base_atk=50.0,
            base_def=40.0,
        )

    # ── 测试 1: 基础 ATK 白值包含光锥 ──
    def test_base_atk_includes_light_cone(self) -> None:
        char = self._make_character()
        lc = self._make_light_cone()

        # 装备前
        base_before = char.stats.get_base_stat(StatType.ATK)

        char.equip_light_cone(lc)

        assert char.stats.get_base_stat(StatType.ATK) == pytest.approx(base_before + lc.base_atk)

    # ── 测试 2: 绿值 ATK 含百分比遗器加成 ──
    def test_total_atk_includes_percent_relic(self) -> None:
        char = self._make_character()
        lc = self._make_light_cone()
        char.equip_light_cone(lc)

        # 装备躯干遗器：ATK +50%
        body_relic = Relic(
            part=RelicPart.BODY,
            set_id="TestSet",
            main_stat=StatModifier(
                stat_type=StatType.ATK,
                modifier_type=StatModifierType.PERCENT,
                value=0.50,
            ),
        )
        char.equip_relic(body_relic)

        # 白值 = 100 + 50 = 150
        expected_base = 100.0 + 50.0
        assert char.stats.get_base_stat(StatType.ATK) == pytest.approx(expected_base)

        # 绿值 = 150 * (1 + 0.50) = 225
        expected_total = expected_base * 1.50
        assert char.stats.get_total_stat(StatType.ATK) == pytest.approx(expected_total)

    # ── 测试 3: 固定 HP 不受百分比 ATK 影响 ──
    def test_flat_hp_not_affected_by_percent_atk(self) -> None:
        char = self._make_character()
        lc = self._make_light_cone()
        char.equip_light_cone(lc)

        # 头部遗器：固定 HP +705
        head_relic = Relic(
            part=RelicPart.HEAD,
            set_id="TestSet",
            main_stat=StatModifier(
                stat_type=StatType.HP,
                modifier_type=StatModifierType.FLAT,
                value=705.0,
            ),
        )
        char.equip_relic(head_relic)

        # 白值 HP = 500 + 300 = 800
        assert char.stats.get_base_stat(StatType.HP) == pytest.approx(800.0)

        # 绿值 HP = 800 * (1 + 0) + 705 = 1505
        assert char.stats.get_total_stat(StatType.HP) == pytest.approx(1505.0)

        # max_hp 同步更新
        assert char.max_hp == 1505

    # ── 测试 4: 装备光锥触发 on_equip ──
    def test_equip_calls_effect_on_equip(self) -> None:
        char = self._make_character()
        mock_effect = Mock(spec=EquipmentEffect)
        lc = LightCone(
            id="TestLC",
            name="Test Light Cone",
            base_hp=100.0,
            base_atk=10.0,
            base_def=10.0,
            effect=mock_effect,
        )

        char.equip_light_cone(lc)
        mock_effect.on_equip.assert_called_once_with(char)

    # ── 测试 5: 多部位遗器加成正确累加 ──
    def test_multiple_relics_accumulate(self) -> None:
        char = self._make_character()

        # 头部：HP% +10%
        head = Relic(
            part=RelicPart.HEAD,
            set_id="TestSet",
            main_stat=StatModifier(StatType.HP, StatModifierType.PERCENT, 0.10),
        )
        # 手部：HP% +5% + ATK flat +10
        hands = Relic(
            part=RelicPart.HANDS,
            set_id="TestSet",
            main_stat=StatModifier(StatType.HP, StatModifierType.PERCENT, 0.05),
            sub_stats=[
                StatModifier(StatType.ATK, StatModifierType.FLAT, 10.0),
            ],
        )

        char.equip_relic(head)
        char.equip_relic(hands)

        # base HP = 500
        # total HP = 500 * (1 + 0.10 + 0.05) + 0 = 575
        assert char.stats.get_total_stat(StatType.HP) == pytest.approx(575.0)

        # total ATK = 100 * (1 + 0) + 10 = 110
        assert char.stats.get_total_stat(StatType.ATK) == pytest.approx(110.0)

    # ── 测试 6: 无装备时 base == total ──
    def test_no_equipment_base_equals_total(self) -> None:
        char = self._make_character()
        for st in (StatType.HP, StatType.ATK, StatType.DEF, StatType.SPD):
            assert char.stats.get_total_stat(st) == pytest.approx(
                char.stats.get_base_stat(st)
            )


# ============================================================
#  TestToughnessSystem — 韧性削韧 & 弱点击破
# ============================================================


class TestModifierPool:
    """验证 Modifier Pool 驱动面板计算的正确性。"""

    def _make_character(self) -> Character:
        return create_test_character("Tester", hp=1000, speed=100, atk=500.0, crit_rate=0.05, crit_dmg=0.50)

    # ── 测试 1: ATK 完整公式 ──
    def test_atk_formula_from_modifier_pool(self) -> None:
        char = self._make_character()
        lc = LightCone(
            id="TestLC", name="TestLC",
            base_hp=300.0, base_atk=500.0, base_def=40.0,
        )
        char.equip_light_cone(lc)

        stats = char.stats

        # 注入三个修饰器: 遗器 43.2% ATK + 光锥特效 20% ATK + 352 flat ATK
        stats.add_modifier(StatModifier(
            StatType.ATK, StatModifierType.PERCENT, 0.432, source="Relic_BODY",
        ))
        stats.add_modifier(StatModifier(
            StatType.ATK, StatModifierType.PERCENT, 0.20, source="LightCone_Effect",
        ))
        stats.add_modifier(StatModifier(
            StatType.ATK, StatModifierType.FLAT, 352.0, source="Relic_HANDS",
        ))

        # (500 + 500) * (1 + 0.432 + 0.20) + 352 = 1984.0
        expected = (500.0 + 500.0) * (1.0 + 0.432 + 0.20) + 352.0
        assert stats.get_total_stat(StatType.ATK) == pytest.approx(expected)

    # ── 测试 2: 移除修饰器后恢复原值 ──
    def test_remove_modifier_reverts_value(self) -> None:
        stats = self._make_character().stats

        mod = StatModifier(StatType.ATK, StatModifierType.FLAT, 100.0, source="Test")
        before = stats.get_total_stat(StatType.ATK)

        stats.add_modifier(mod)
        assert stats.get_total_stat(StatType.ATK) == pytest.approx(before + 100.0)

        stats.remove_modifier(mod)
        assert stats.get_total_stat(StatType.ATK) == pytest.approx(before)

    # ── 测试 3: CRIT 属性为加算型 ──
    def test_crit_rate_is_additive(self) -> None:
        stats = self._make_character().stats
        base_crit = stats.get_total_stat(StatType.CRIT_RATE)

        stats.add_modifier(StatModifier(
            StatType.CRIT_RATE, StatModifierType.PERCENT, 0.15, source="Relic_BODY",
        ))
        # 加算: base + 0.15 (不是 base * 1.15)
        assert stats.get_total_stat(StatType.CRIT_RATE) == pytest.approx(base_crit + 0.15)

    # ── 测试 4: equip_relic 自动注入 source ──
    def test_equip_relic_sets_source(self) -> None:
        char = self._make_character()
        relic = Relic(
            part=RelicPart.BODY,
            set_id="TestSet",
            main_stat=StatModifier(
                StatType.ATK, StatModifierType.PERCENT, 0.432,
            ),
        )
        char.equip_relic(relic)

        assert relic.main_stat.source == "Relic_BODY"
        assert relic.main_stat in char.stats.active_modifiers

    # ── 测试 5: DEF 走乘算公式 ──
    def test_def_formula_multiplicative(self) -> None:
        stats = self._make_character().stats
        base_def = stats.get_base_stat(StatType.DEF)

        stats.add_modifier(StatModifier(
            StatType.DEF, StatModifierType.PERCENT, 0.50, source="Test",
        ))
        stats.add_modifier(StatModifier(
            StatType.DEF, StatModifierType.FLAT, 20.0, source="Test",
        ))
        expected = base_def * 1.50 + 20.0
        assert stats.get_total_stat(StatType.DEF) == pytest.approx(expected)


# ============================================================
#  TestDefenseSystem — 防御减伤乘区
# ============================================================


class TestStatModifierFields:
    """验证 StatModifier 新增字段存在且默认值正确。"""

    def test_dispellable_default_true(self) -> None:
        m = StatModifier(StatType.ATK, StatModifierType.FLAT, 10.0)
        assert m.dispellable is True

    def test_stack_policy_default_independent(self) -> None:
        m = StatModifier(StatType.ATK, StatModifierType.FLAT, 10.0)
        assert m.stack_policy == "independent"

    def test_tick_timing_default_owner_turn_end(self) -> None:
        m = StatModifier(StatType.ATK, StatModifierType.FLAT, 10.0)
        assert m.tick_timing == "owner_turn_end"

    def test_duration_mode_default_turns(self) -> None:
        m = StatModifier(StatType.ATK, StatModifierType.FLAT, 10.0)
        assert m.duration_mode == "turns"

    def test_tags_default_empty(self) -> None:
        m = StatModifier(StatType.ATK, StatModifierType.FLAT, 10.0)
        assert m.tags == ()

    def test_custom_tags_settable(self) -> None:
        m = StatModifier(StatType.ATK, StatModifierType.FLAT, 10.0, tags=["debuff", "fire"])
        assert "debuff" in m.tags
        assert "fire" in m.tags

    def test_existing_constructor_still_works(self) -> None:
        """向后兼容：旧的位置参数构造不报错。"""
        m = StatModifier(StatType.SPD, StatModifierType.PERCENT, -0.10, source="Test",
                         duration=1, cc_type="Freeze")
        assert m.stat_type == StatType.SPD
        assert m.modifier_type == StatModifierType.PERCENT
        assert m.value == pytest.approx(-0.10)
        assert m.source == "Test"
        assert m.duration == 1
        assert m.cc_type == "Freeze"
        # 新增字段默认
        assert m.dispellable is True
        assert m.stack_policy == "independent"


# ============================================================
#  TestTickTiming — P0-2: 分时点递减
# ============================================================

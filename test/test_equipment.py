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
    start_relic_set_effects,
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


# ============================================================
#  TestBandOfSizzlingThunder — 激奏雷电的乐队 (109)
# ============================================================


class TestBandOfSizzlingThunder:
    """2件: 雷属性伤害+10% / 4件: 施放战技后攻击力+20%持续1回合"""

    _SET_ID = "109"
    _SOURCE_2PC = "RelicSet_109_2pc"
    _SOURCE_4PC = "RelicSet_109_4pc"

    def _make_char(self):
        return create_test_character("T", hp=1000, speed=100, atk=500.0, crit_rate=0.05, crit_dmg=0.50)

    def _make_state(self, char):
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])
        engine = CombatEngine(state)
        return state, engine

    def _equip_4pc(self, char):
        for part in (RelicPart.HEAD, RelicPart.HANDS, RelicPart.BODY, RelicPart.FEET):
            if part == RelicPart.HEAD:
                m = StatModifier(StatType.HP, StatModifierType.FLAT, 705.0)
            elif part == RelicPart.HANDS:
                m = StatModifier(StatType.ATK, StatModifierType.FLAT, 352.0)
            else:
                m = StatModifier(StatType.ATK, StatModifierType.PERCENT, 0.30)
            char.equip_relic(Relic(part=part, set_id=self._SET_ID, main_stat=m))

    def _get_source_mods(self, char, stat_type, source):
        return [m for m in char.stats.active_modifiers
                if m.stat_type == stat_type and m.source == source]

    # ── 2件套 ──

    def test_2pc_lightning_dmg_bonus(self) -> None:
        char = self._make_char()
        char.equip_relic(Relic(part=RelicPart.HEAD, set_id=self._SET_ID,
                                main_stat=StatModifier(StatType.HP, StatModifierType.FLAT, 705.0)))
        char.equip_relic(Relic(part=RelicPart.HANDS, set_id=self._SET_ID,
                                main_stat=StatModifier(StatType.ATK, StatModifierType.FLAT, 352.0)))
        mods = self._get_source_mods(char, StatType.THUNDER_DMG_BONUS, self._SOURCE_2PC)
        assert len(mods) == 1
        assert mods[0].value == pytest.approx(0.10)
        assert mods[0].dispellable is False

    def test_1pc_no_bonus(self) -> None:
        char = self._make_char()
        char.equip_relic(Relic(part=RelicPart.HEAD, set_id=self._SET_ID,
                                main_stat=StatModifier(StatType.HP, StatModifierType.FLAT, 705.0)))
        assert len(self._get_source_mods(char, StatType.THUNDER_DMG_BONUS, self._SOURCE_2PC)) == 0

    # ── 4件套 ──

    def test_4pc_atk_after_skill(self) -> None:
        char = self._make_char()
        self._equip_4pc(char)
        state, engine = self._make_state(char)
        start_relic_set_effects(state, char)

        engine.event_bus.emit(
            EventType.AFTER_ACTION,
            unit=char, target=None, action_type=ActionType.SKILL,
        )
        mods = self._get_source_mods(char, StatType.ATK, self._SOURCE_4PC)
        assert len(mods) == 1
        assert mods[0].value == pytest.approx(0.20)
        assert mods[0].duration == 1
        assert mods[0].dispellable is False

    def test_4pc_no_buff_on_other_action(self) -> None:
        char = self._make_char()
        self._equip_4pc(char)
        state, engine = self._make_state(char)
        start_relic_set_effects(state, char)

        engine.event_bus.emit(
            EventType.AFTER_ACTION,
            unit=char, target=None, action_type=ActionType.BASIC_ATTACK,
        )
        assert len(self._get_source_mods(char, StatType.ATK, self._SOURCE_4PC)) == 0

    def test_4pc_only_for_equipped_character(self) -> None:
        char1 = self._make_char()
        char2 = create_test_character("T2", hp=1000, speed=100, atk=500.0)
        self._equip_4pc(char1)

        state, engine = self._make_state(char1)
        state.characters.append(char2)
        start_relic_set_effects(state, char1)

        engine.event_bus.emit(
            EventType.AFTER_ACTION,
            unit=char2, target=None, action_type=ActionType.SKILL,
        )
        assert len(self._get_source_mods(char1, StatType.ATK, self._SOURCE_4PC)) == 0

    def test_4pc_refresh_on_second_skill(self) -> None:
        char = self._make_char()
        self._equip_4pc(char)
        state, engine = self._make_state(char)
        start_relic_set_effects(state, char)

        for _ in range(2):
            engine.event_bus.emit(
                EventType.AFTER_ACTION,
                unit=char, target=None, action_type=ActionType.SKILL,
            )
        mods = self._get_source_mods(char, StatType.ATK, self._SOURCE_4PC)
        assert len(mods) == 1
        assert mods[0].duration == 1

    # ── 卸载 ──

    def test_unequip_cleans_sources(self) -> None:
        char = self._make_char()
        self._equip_4pc(char)
        state, engine = self._make_state(char)
        start_relic_set_effects(state, char)

        engine.event_bus.emit(
            EventType.AFTER_ACTION,
            unit=char, target=None, action_type=ActionType.SKILL,
        )
        assert any(m.source.startswith("RelicSet_109_") for m in char.stats.active_modifiers)

        for part in (RelicPart.HEAD, RelicPart.HANDS, RelicPart.BODY, RelicPart.FEET):
            char.equip_relic(Relic(part=part, set_id="OtherSet",
                                    main_stat=StatModifier(StatType.ATK, StatModifierType.PERCENT, 0.30)))

        assert not any(m.source.startswith("RelicSet_109_") for m in char.stats.active_modifiers)


# ============================================================
#  TestChampionOfStreetwiseBoxing — 街头出身的拳王 (105)
# ============================================================


class TestChampionOfStreetwiseBoxing:
    """2件: 物理伤害+10% / 4件: 攻击/受击后攻击力+5%最多5层"""

    _SET_ID = "105"
    _SOURCE_2PC = "RelicSet_105_2pc"
    _SOURCE_4PC = "RelicSet_105_4pc"

    def _make_char(self):
        return create_test_character("T", hp=1000, speed=100, atk=500.0, crit_rate=0.05, crit_dmg=0.50)

    def _make_state(self, char):
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])
        engine = CombatEngine(state)
        return state, engine

    def _equip_4pc(self, char):
        for part in (RelicPart.HEAD, RelicPart.HANDS, RelicPart.BODY, RelicPart.FEET):
            if part == RelicPart.HEAD:
                m = StatModifier(StatType.HP, StatModifierType.FLAT, 705.0)
            elif part == RelicPart.HANDS:
                m = StatModifier(StatType.ATK, StatModifierType.FLAT, 352.0)
            else:
                m = StatModifier(StatType.ATK, StatModifierType.PERCENT, 0.30)
            char.equip_relic(Relic(part=part, set_id=self._SET_ID, main_stat=m))

    def _get_source_total(self, char, stat_type, source):
        return sum(m.value for m in char.stats.active_modifiers
                   if m.stat_type == stat_type and m.source == source)

    # ── 2件套 ──

    def test_2pc_physical_dmg_bonus(self) -> None:
        char = self._make_char()
        char.equip_relic(Relic(part=RelicPart.HEAD, set_id=self._SET_ID,
                                main_stat=StatModifier(StatType.HP, StatModifierType.FLAT, 705.0)))
        char.equip_relic(Relic(part=RelicPart.HANDS, set_id=self._SET_ID,
                                main_stat=StatModifier(StatType.ATK, StatModifierType.FLAT, 352.0)))
        total = self._get_source_total(char, StatType.PHYSICAL_DMG_BONUS, self._SOURCE_2PC)
        assert total == pytest.approx(0.10)

    def test_1pc_no_bonus(self) -> None:
        char = self._make_char()
        char.equip_relic(Relic(part=RelicPart.HEAD, set_id=self._SET_ID,
                                main_stat=StatModifier(StatType.HP, StatModifierType.FLAT, 705.0)))
        assert self._get_source_total(char, StatType.PHYSICAL_DMG_BONUS, self._SOURCE_2PC) == 0.0

    # ── 4件套 ──

    def test_4pc_stacks_on_action(self) -> None:
        char = self._make_char()
        self._equip_4pc(char)
        state, engine = self._make_state(char)
        start_relic_set_effects(state, char)

        engine.event_bus.emit(
            EventType.AFTER_ACTION,
            unit=char, target=None, action_type=ActionType.BASIC_ATTACK,
        )
        assert self._get_source_total(char, StatType.ATK, self._SOURCE_4PC) == pytest.approx(0.05)

    def test_4pc_stacks_on_hit(self) -> None:
        char = self._make_char()
        self._equip_4pc(char)
        state, engine = self._make_state(char)
        start_relic_set_effects(state, char)

        engine.event_bus.emit(
            EventType.ON_HIT,
            source=None, target=char, damage=100,
        )
        assert self._get_source_total(char, StatType.ATK, self._SOURCE_4PC) == pytest.approx(0.05)

    def test_4pc_caps_at_5_stacks(self) -> None:
        char = self._make_char()
        self._equip_4pc(char)
        state, engine = self._make_state(char)
        start_relic_set_effects(state, char)

        for _ in range(6):
            engine.event_bus.emit(
                EventType.AFTER_ACTION,
                unit=char, target=None, action_type=ActionType.BASIC_ATTACK,
            )
        assert self._get_source_total(char, StatType.ATK, self._SOURCE_4PC) == pytest.approx(0.25)

    def test_4pc_only_for_owner(self) -> None:
        char1 = self._make_char()
        char2 = create_test_character("T2", hp=1000, speed=100, atk=500.0)
        self._equip_4pc(char1)

        state, engine = self._make_state(char1)
        state.characters.append(char2)
        start_relic_set_effects(state, char1)

        engine.event_bus.emit(
            EventType.AFTER_ACTION,
            unit=char2, target=None, action_type=ActionType.BASIC_ATTACK,
        )
        assert self._get_source_total(char1, StatType.ATK, self._SOURCE_4PC) == 0.0

    def test_4pc_accumulates_from_both_triggers(self) -> None:
        char = self._make_char()
        self._equip_4pc(char)
        state, engine = self._make_state(char)
        start_relic_set_effects(state, char)

        engine.event_bus.emit(
            EventType.AFTER_ACTION,
            unit=char, target=None, action_type=ActionType.BASIC_ATTACK,
        )
        engine.event_bus.emit(
            EventType.ON_HIT,
            source=None, target=char, damage=100,
        )
        assert self._get_source_total(char, StatType.ATK, self._SOURCE_4PC) == pytest.approx(0.10)

    # ── 卸载 ──

    def test_unequip_cleans_sources(self) -> None:
        char = self._make_char()
        self._equip_4pc(char)
        state, engine = self._make_state(char)
        start_relic_set_effects(state, char)

        engine.event_bus.emit(
            EventType.AFTER_ACTION,
            unit=char, target=None, action_type=ActionType.BASIC_ATTACK,
        )
        assert any(m.source.startswith("RelicSet_105_") for m in char.stats.active_modifiers)

        for part in (RelicPart.HEAD, RelicPart.HANDS, RelicPart.BODY, RelicPart.FEET):
            char.equip_relic(Relic(part=part, set_id="OtherSet",
                                    main_stat=StatModifier(StatType.ATK, StatModifierType.PERCENT, 0.30)))

        assert not any(m.source.startswith("RelicSet_105_") for m in char.stats.active_modifiers)


# ============================================================
#  TestEagleOfTwilightLine — 晨昏交界的翔鹰 (110)
# ============================================================


class TestEagleOfTwilightLine:
    """2件: 风属性伤害+10% / 4件: 施放终结技后行动提前25%"""

    _SET_ID = "110"
    _SOURCE_2PC = "RelicSet_110_2pc"

    def _make_char(self):
        return create_test_character("T", hp=1000, speed=100, atk=500.0, crit_rate=0.05, crit_dmg=0.50)

    def _make_state(self, char):
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])
        engine = CombatEngine(state)
        return state, engine

    def _equip_4pc(self, char):
        for part in (RelicPart.HEAD, RelicPart.HANDS, RelicPart.BODY, RelicPart.FEET):
            if part == RelicPart.HEAD:
                m = StatModifier(StatType.HP, StatModifierType.FLAT, 705.0)
            elif part == RelicPart.HANDS:
                m = StatModifier(StatType.ATK, StatModifierType.FLAT, 352.0)
            else:
                m = StatModifier(StatType.ATK, StatModifierType.PERCENT, 0.30)
            char.equip_relic(Relic(part=part, set_id=self._SET_ID, main_stat=m))

    def _get_source_mods(self, char, stat_type, source):
        return [m for m in char.stats.active_modifiers
                if m.stat_type == stat_type and m.source == source]

    # ── 2件套 ──

    def test_2pc_wind_dmg_bonus(self) -> None:
        char = self._make_char()
        char.equip_relic(Relic(part=RelicPart.HEAD, set_id=self._SET_ID,
                                main_stat=StatModifier(StatType.HP, StatModifierType.FLAT, 705.0)))
        char.equip_relic(Relic(part=RelicPart.HANDS, set_id=self._SET_ID,
                                main_stat=StatModifier(StatType.ATK, StatModifierType.FLAT, 352.0)))
        mods = self._get_source_mods(char, StatType.WIND_DMG_BONUS, self._SOURCE_2PC)
        assert len(mods) == 1
        assert mods[0].value == pytest.approx(0.10)

    def test_1pc_no_bonus(self) -> None:
        char = self._make_char()
        char.equip_relic(Relic(part=RelicPart.HEAD, set_id=self._SET_ID,
                                main_stat=StatModifier(StatType.HP, StatModifierType.FLAT, 705.0)))
        assert len(self._get_source_mods(char, StatType.WIND_DMG_BONUS, self._SOURCE_2PC)) == 0

    # ── 4件套 ──

    def test_4pc_advance_after_ultimate(self) -> None:
        char = self._make_char()
        self._equip_4pc(char)
        state, engine = self._make_state(char)
        start_relic_set_effects(state, char)

        char.reset_av()
        base_av = char.current_av
        assert base_av == pytest.approx(100.0)

        engine.event_bus.emit(
            EventType.AFTER_ACTION,
            unit=char, target=None, action_type=ActionType.ULTIMATE,
        )
        assert char.current_av < base_av
        assert char.current_av == pytest.approx(75.0)

    def test_4pc_advance_on_queued_ultimate(self) -> None:
        char = self._make_char()
        self._equip_4pc(char)
        state, engine = self._make_state(char)
        start_relic_set_effects(state, char)

        char.reset_av()
        base_av = char.current_av
        assert base_av == pytest.approx(100.0)

        engine.event_bus.emit(
            EventType.ON_ULTIMATE_INSERTED,
            character=char, target=None,
        )
        assert char.current_av < base_av
        assert char.current_av == pytest.approx(75.0)

    def test_4pc_no_advance_on_basic(self) -> None:
        char = self._make_char()
        self._equip_4pc(char)
        state, engine = self._make_state(char)
        start_relic_set_effects(state, char)

        char.reset_av()
        base_av = char.current_av

        engine.event_bus.emit(
            EventType.AFTER_ACTION,
            unit=char, target=None, action_type=ActionType.BASIC_ATTACK,
        )
        assert char.current_av == pytest.approx(base_av)

    def test_4pc_only_for_owner(self) -> None:
        char1 = self._make_char()
        char2 = create_test_character("T2", hp=1000, speed=100, atk=500.0)
        self._equip_4pc(char1)

        state, engine = self._make_state(char1)
        state.characters.append(char2)
        start_relic_set_effects(state, char1)

        char1.reset_av()
        base_av = char1.current_av

        engine.event_bus.emit(
            EventType.AFTER_ACTION,
            unit=char2, target=None, action_type=ActionType.ULTIMATE,
        )
        assert char1.current_av == pytest.approx(base_av)

    # ── 卸载 ──

    def test_unequip_cleans_sources(self) -> None:
        char = self._make_char()
        char.equip_relic(Relic(part=RelicPart.HEAD, set_id=self._SET_ID,
                                main_stat=StatModifier(StatType.HP, StatModifierType.FLAT, 705.0)))
        char.equip_relic(Relic(part=RelicPart.HANDS, set_id=self._SET_ID,
                                main_stat=StatModifier(StatType.ATK, StatModifierType.FLAT, 352.0)))
        assert any(m.source.startswith("RelicSet_110_") for m in char.stats.active_modifiers)

        for part in (RelicPart.HEAD, RelicPart.HANDS, RelicPart.BODY, RelicPart.FEET):
            char.equip_relic(Relic(part=part, set_id="OtherSet",
                                    main_stat=StatModifier(StatType.ATK, StatModifierType.PERCENT, 0.30)))

        assert not any(m.source.startswith("RelicSet_110_") for m in char.stats.active_modifiers)


# ============================================================
#  TestFiresmithOfLavaForging — 熔岩锻铸的火匠 (107)
# ============================================================


class TestFiresmithOfLavaForging:
    """2件: 火伤+10% / 4件: 战技伤+12% + 终结技后下一击火伤+12%"""

    _SET_ID = "107"
    _SOURCE_2PC = "RelicSet_107_2pc"
    _SOURCE_4PC_SKILL = "RelicSet_107_4pc_skill"
    _SOURCE_4PC_ULT = "RelicSet_107_4pc_ult"

    def _make_char(self):
        return create_test_character("T", hp=1000, speed=100, atk=500.0, crit_rate=0.05, crit_dmg=0.50)

    def _make_state(self, char):
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])
        engine = CombatEngine(state)
        return state, engine

    def _equip_4pc(self, char):
        for part in (RelicPart.HEAD, RelicPart.HANDS, RelicPart.BODY, RelicPart.FEET):
            if part == RelicPart.HEAD:
                m = StatModifier(StatType.HP, StatModifierType.FLAT, 705.0)
            elif part == RelicPart.HANDS:
                m = StatModifier(StatType.ATK, StatModifierType.FLAT, 352.0)
            else:
                m = StatModifier(StatType.ATK, StatModifierType.PERCENT, 0.30)
            char.equip_relic(Relic(part=part, set_id=self._SET_ID, main_stat=m))

    def _get_source_mods(self, char, stat_type, source):
        return [m for m in char.stats.active_modifiers
                if m.stat_type == stat_type and m.source == source]

    def _has_source(self, char, source):
        return any(m.source == source for m in char.stats.active_modifiers)

    # ── 2件套 ──

    def test_2pc_fire_dmg_bonus(self) -> None:
        char = self._make_char()
        char.equip_relic(Relic(part=RelicPart.HEAD, set_id=self._SET_ID,
                                main_stat=StatModifier(StatType.HP, StatModifierType.FLAT, 705.0)))
        char.equip_relic(Relic(part=RelicPart.HANDS, set_id=self._SET_ID,
                                main_stat=StatModifier(StatType.ATK, StatModifierType.FLAT, 352.0)))
        mods = self._get_source_mods(char, StatType.FIRE_DMG_BONUS, self._SOURCE_2PC)
        assert len(mods) == 1
        assert mods[0].value == pytest.approx(0.10)

    def test_1pc_no_bonus(self) -> None:
        char = self._make_char()
        char.equip_relic(Relic(part=RelicPart.HEAD, set_id=self._SET_ID,
                                main_stat=StatModifier(StatType.HP, StatModifierType.FLAT, 705.0)))
        assert len(self._get_source_mods(char, StatType.FIRE_DMG_BONUS, self._SOURCE_2PC)) == 0

    # ── 4件套: 战技伤 +12% ──

    def test_4pc_skill_dmg_permanent(self) -> None:
        char = self._make_char()
        self._equip_4pc(char)
        mods = self._get_source_mods(char, StatType.SKILL_DMG, self._SOURCE_4PC_SKILL)
        assert len(mods) == 1
        assert mods[0].value == pytest.approx(0.12)

    # ── 4件套: 终结技后下一击火伤 +12% ──

    def test_4pc_fire_dmg_after_ultimate(self) -> None:
        char = self._make_char()
        self._equip_4pc(char)
        state, engine = self._make_state(char)
        start_relic_set_effects(state, char)

        engine.event_bus.emit(
            EventType.AFTER_ACTION,
            unit=char, target=None, action_type=ActionType.ULTIMATE,
        )
        mods = self._get_source_mods(char, StatType.FIRE_DMG_BONUS, self._SOURCE_4PC_ULT)
        assert len(mods) == 1
        assert mods[0].value == pytest.approx(0.12)

    def test_4pc_consumed_on_next_action(self) -> None:
        char = self._make_char()
        self._equip_4pc(char)
        state, engine = self._make_state(char)
        start_relic_set_effects(state, char)

        engine.event_bus.emit(
            EventType.AFTER_ACTION,
            unit=char, target=None, action_type=ActionType.ULTIMATE,
        )
        assert self._has_source(char, self._SOURCE_4PC_ULT)

        engine.event_bus.emit(
            EventType.AFTER_ACTION,
            unit=char, target=None, action_type=ActionType.SKILL,
        )
        assert not self._has_source(char, self._SOURCE_4PC_ULT)

    def test_4pc_fua_consumes_buff(self) -> None:
        char = self._make_char()
        self._equip_4pc(char)
        state, engine = self._make_state(char)
        start_relic_set_effects(state, char)

        engine.event_bus.emit(
            EventType.AFTER_ACTION,
            unit=char, target=None, action_type=ActionType.ULTIMATE,
        )
        assert self._has_source(char, self._SOURCE_4PC_ULT)

        engine.event_bus.emit(
            EventType.AFTER_ACTION,
            unit=char, target=None, action_type=ActionType.FOLLOW_UP,
        )
        assert not self._has_source(char, self._SOURCE_4PC_ULT)

    def test_4pc_queued_ultimate(self) -> None:
        char = self._make_char()
        self._equip_4pc(char)
        state, engine = self._make_state(char)
        start_relic_set_effects(state, char)

        engine.event_bus.emit(
            EventType.ON_ULTIMATE_INSERTED,
            character=char, target=None,
        )
        assert self._has_source(char, self._SOURCE_4PC_ULT)

    def test_4pc_only_for_owner(self) -> None:
        char1 = self._make_char()
        char2 = create_test_character("T2", hp=1000, speed=100, atk=500.0)
        self._equip_4pc(char1)

        state, engine = self._make_state(char1)
        state.characters.append(char2)
        start_relic_set_effects(state, char1)

        engine.event_bus.emit(
            EventType.AFTER_ACTION,
            unit=char2, target=None, action_type=ActionType.ULTIMATE,
        )
        assert not self._has_source(char1, self._SOURCE_4PC_ULT)

    def test_4pc_ult_after_ult(self) -> None:
        char = self._make_char()
        self._equip_4pc(char)
        state, engine = self._make_state(char)
        start_relic_set_effects(state, char)

        engine.event_bus.emit(
            EventType.AFTER_ACTION,
            unit=char, target=None, action_type=ActionType.ULTIMATE,
        )
        assert self._has_source(char, self._SOURCE_4PC_ULT)

        engine.event_bus.emit(
            EventType.AFTER_ACTION,
            unit=char, target=None, action_type=ActionType.ULTIMATE,
        )
        assert self._has_source(char, self._SOURCE_4PC_ULT)

    # ── 卸载 ──

    def test_unequip_cleans_sources(self) -> None:
        char = self._make_char()
        self._equip_4pc(char)
        state, engine = self._make_state(char)
        start_relic_set_effects(state, char)

        engine.event_bus.emit(
            EventType.AFTER_ACTION,
            unit=char, target=None, action_type=ActionType.ULTIMATE,
        )
        assert any(m.source.startswith("RelicSet_107_") for m in char.stats.active_modifiers)

        for part in (RelicPart.HEAD, RelicPart.HANDS, RelicPart.BODY, RelicPart.FEET):
            char.equip_relic(Relic(part=part, set_id="OtherSet",
                                    main_stat=StatModifier(StatType.ATK, StatModifierType.PERCENT, 0.30)))

        assert not any(m.source.startswith("RelicSet_107_") for m in char.stats.active_modifiers)


# ============================================================
#  TestGeniusOfBrilliantStars — 繁星璀璨的天才 (108)
# ============================================================


class TestGeniusOfBrilliantStars:
    """2件: 量子伤+10% / 4件: 无视10%防御, 量子弱点额外10%"""

    _SET_ID = "108"
    _SOURCE_2PC = "RelicSet_108_2pc"
    _SOURCE_4PC_BASE = "RelicSet_108_4pc_base"
    _SOURCE_4PC_EXTRA = "RelicSet_108_4pc_extra"

    def _make_char(self):
        return create_test_character("T", hp=1000, speed=100, atk=500.0, crit_rate=0.05, crit_dmg=0.50)

    def _make_state(self, char, enemy=None):
        if enemy is None:
            enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                           weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])
        engine = CombatEngine(state)
        return state, engine

    def _equip_4pc(self, char):
        for part in (RelicPart.HEAD, RelicPart.HANDS, RelicPart.BODY, RelicPart.FEET):
            if part == RelicPart.HEAD:
                m = StatModifier(StatType.HP, StatModifierType.FLAT, 705.0)
            elif part == RelicPart.HANDS:
                m = StatModifier(StatType.ATK, StatModifierType.FLAT, 352.0)
            else:
                m = StatModifier(StatType.ATK, StatModifierType.PERCENT, 0.30)
            char.equip_relic(Relic(part=part, set_id=self._SET_ID, main_stat=m))

    def _def_ignore_total(self, char, source):
        return sum(m.value for m in char.stats.active_modifiers
                   if m.stat_type == StatType.DEF_IGNORE and m.source == source)

    def _has_source(self, char, source):
        return any(m.source == source for m in char.stats.active_modifiers)

    # ── 2件套 ──

    def test_2pc_quantum_dmg_bonus(self) -> None:
        char = self._make_char()
        char.equip_relic(Relic(part=RelicPart.HEAD, set_id=self._SET_ID,
                                main_stat=StatModifier(StatType.HP, StatModifierType.FLAT, 705.0)))
        char.equip_relic(Relic(part=RelicPart.HANDS, set_id=self._SET_ID,
                                main_stat=StatModifier(StatType.ATK, StatModifierType.FLAT, 352.0)))
        mods = [m for m in char.stats.active_modifiers
                if m.stat_type == StatType.QUANTUM_DMG_BONUS and m.source == self._SOURCE_2PC]
        assert len(mods) == 1
        assert mods[0].value == pytest.approx(0.10)

    def test_1pc_no_bonus(self) -> None:
        char = self._make_char()
        char.equip_relic(Relic(part=RelicPart.HEAD, set_id=self._SET_ID,
                                main_stat=StatModifier(StatType.HP, StatModifierType.FLAT, 705.0)))
        assert not any(m.stat_type == StatType.QUANTUM_DMG_BONUS and m.source == self._SOURCE_2PC
                       for m in char.stats.active_modifiers)

    # ── 4件套: 基础无视防御 ──

    def test_4pc_base_def_ignore(self) -> None:
        char = self._make_char()
        self._equip_4pc(char)
        assert self._def_ignore_total(char, self._SOURCE_4PC_BASE) == pytest.approx(0.10)

    # ── 4件套: 量子弱点额外无视防御 ──

    def test_4pc_extra_on_quantum_weakness(self) -> None:
        char = self._make_char()
        self._equip_4pc(char)
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.QUANTUM, ElementType.PHYSICAL])
        state, engine = self._make_state(char, enemy)
        start_relic_set_effects(state, char)

        engine.event_bus.emit(
            EventType.ON_BEFORE_TARGET_SELECT,
            unit=char, targets=[enemy],
        )
        assert self._has_source(char, self._SOURCE_4PC_EXTRA)
        assert self._def_ignore_total(char, self._SOURCE_4PC_EXTRA) == pytest.approx(0.10)

    def test_4pc_no_extra_on_no_quantum_weakness(self) -> None:
        char = self._make_char()
        self._equip_4pc(char)
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.FIRE])
        state, engine = self._make_state(char, enemy)
        start_relic_set_effects(state, char)

        engine.event_bus.emit(
            EventType.ON_BEFORE_TARGET_SELECT,
            unit=char, targets=[enemy],
        )
        assert not self._has_source(char, self._SOURCE_4PC_EXTRA)

    def test_4pc_extra_removed_when_target_not_quantum(self) -> None:
        char = self._make_char()
        self._equip_4pc(char)
        enemy_q = Enemy(name="Q", hp=10000, speed=50, base_damage=0, level=1,
                         weaknesses=[ElementType.QUANTUM])
        state, engine = self._make_state(char, enemy_q)
        start_relic_set_effects(state, char)

        engine.event_bus.emit(
            EventType.ON_BEFORE_TARGET_SELECT,
            unit=char, targets=[enemy_q],
        )
        assert self._has_source(char, self._SOURCE_4PC_EXTRA)

        enemy_f = Enemy(name="F", hp=10000, speed=50, base_damage=0, level=1,
                         weaknesses=[ElementType.FIRE])
        engine.event_bus.emit(
            EventType.ON_BEFORE_TARGET_SELECT,
            unit=char, targets=[enemy_f],
        )
        assert not self._has_source(char, self._SOURCE_4PC_EXTRA)

    def test_4pc_only_for_owner(self) -> None:
        char1 = self._make_char()
        char2 = create_test_character("T2", hp=1000, speed=100, atk=500.0)
        self._equip_4pc(char1)

        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.QUANTUM])
        state, engine = self._make_state(char1, enemy)
        start_relic_set_effects(state, char1)

        engine.event_bus.emit(
            EventType.ON_BEFORE_TARGET_SELECT,
            unit=char2, targets=[enemy],
        )
        assert not self._has_source(char1, self._SOURCE_4PC_EXTRA)

    def test_4pc_queued_ultimate_extra(self) -> None:
        char = self._make_char()
        self._equip_4pc(char)
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.QUANTUM])
        state, engine = self._make_state(char, enemy)
        start_relic_set_effects(state, char)

        engine.event_bus.emit(
            EventType.ON_ULTIMATE_INSERTED,
            character=char, target=enemy,
        )
        assert self._has_source(char, self._SOURCE_4PC_EXTRA)

    # ── 卸载 ──

    def test_unequip_cleans_sources(self) -> None:
        char = self._make_char()
        self._equip_4pc(char)
        assert any(m.source.startswith("RelicSet_108_") for m in char.stats.active_modifiers)

        for part in (RelicPart.HEAD, RelicPart.HANDS, RelicPart.BODY, RelicPart.FEET):
            char.equip_relic(Relic(part=part, set_id="OtherSet",
                                    main_stat=StatModifier(StatType.ATK, StatModifierType.PERCENT, 0.30)))

        assert not any(m.source.startswith("RelicSet_108_") for m in char.stats.active_modifiers)


# ============================================================
#  TestGuardOfWutheringSnow — 戍卫风雪的铁卫 (106)
# ============================================================


class TestGuardOfWutheringSnow:
    """2件: 受伤害降低8% / 4件: 回合开始时HP≤50%则回8%生命+5能量"""

    _SET_ID = "106"
    _SOURCE_2PC = "RelicSet_106_2pc"

    def _make_char(self):
        return create_test_character("T", hp=1000, speed=100, atk=500.0, crit_rate=0.05, crit_dmg=0.50)

    def _make_state(self, char):
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])
        engine = CombatEngine(state)
        return state, engine

    def _equip_4pc(self, char):
        for part in (RelicPart.HEAD, RelicPart.HANDS, RelicPart.BODY, RelicPart.FEET):
            if part == RelicPart.HEAD:
                m = StatModifier(StatType.HP, StatModifierType.FLAT, 705.0)
            elif part == RelicPart.HANDS:
                m = StatModifier(StatType.ATK, StatModifierType.FLAT, 352.0)
            else:
                m = StatModifier(StatType.ATK, StatModifierType.PERCENT, 0.30)
            char.equip_relic(Relic(part=part, set_id=self._SET_ID, main_stat=m))

    # ── 2件套 ──

    def test_2pc_dmg_mitigation(self) -> None:
        char = self._make_char()
        char.equip_relic(Relic(part=RelicPart.HEAD, set_id=self._SET_ID,
                                main_stat=StatModifier(StatType.HP, StatModifierType.FLAT, 705.0)))
        char.equip_relic(Relic(part=RelicPart.HANDS, set_id=self._SET_ID,
                                main_stat=StatModifier(StatType.ATK, StatModifierType.FLAT, 352.0)))
        mods = [m for m in char.stats.active_modifiers
                if m.stat_type == StatType.DMG_MITIGATION and m.source == self._SOURCE_2PC]
        assert len(mods) == 1
        assert mods[0].value == pytest.approx(0.08)

    def test_1pc_no_bonus(self) -> None:
        char = self._make_char()
        char.equip_relic(Relic(part=RelicPart.HEAD, set_id=self._SET_ID,
                                main_stat=StatModifier(StatType.HP, StatModifierType.FLAT, 705.0)))
        assert not any(m.source == self._SOURCE_2PC for m in char.stats.active_modifiers)

    # ── 2件套: take_damage 实际减伤 ──

    def test_take_damage_mitigation_reduces(self) -> None:
        char = self._make_char()
        char.equip_relic(Relic(part=RelicPart.HEAD, set_id=self._SET_ID,
                                main_stat=StatModifier(StatType.HP, StatModifierType.FLAT, 705.0)))
        char.equip_relic(Relic(part=RelicPart.HANDS, set_id=self._SET_ID,
                                main_stat=StatModifier(StatType.ATK, StatModifierType.FLAT, 352.0)))
        hp_before = char.hp
        dmg = char.take_damage(100)
        expected_dmg = int(100 * (1 - 0.08))
        assert dmg == expected_dmg  # 92
        assert char.hp == hp_before - expected_dmg

    # ── 4件套 ──

    def test_4pc_heal_and_energy_on_low_hp(self) -> None:
        char = self._make_char()
        char.set_energy(0)
        self._equip_4pc(char)
        char.hp = char.max_hp // 2  # exactly 50%
        expected_heal = int(char.max_hp * 0.08)
        hp_before = char.hp

        state, engine = self._make_state(char)
        start_relic_set_effects(state, char)

        engine.event_bus.emit(EventType.TURN_START, unit=char, engine=engine)
        assert char.hp == hp_before + expected_heal
        assert char.energy == 5

    def test_4pc_no_trigger_on_high_hp(self) -> None:
        char = self._make_char()
        char.set_energy(0)
        self._equip_4pc(char)
        hp_before = char.hp  # 100% HP, well above 50%

        state, engine = self._make_state(char)
        start_relic_set_effects(state, char)

        engine.event_bus.emit(EventType.TURN_START, unit=char, engine=engine)
        assert char.hp == hp_before
        assert char.energy == 0

    def test_4pc_only_for_owner(self) -> None:
        char1 = self._make_char()
        char2 = create_test_character("T2", hp=1000, speed=100, atk=500.0)
        self._equip_4pc(char1)
        char1.hp = char1.max_hp // 2
        hp_before = char1.hp

        state, engine = self._make_state(char1)
        state.characters.append(char2)
        start_relic_set_effects(state, char1)

        engine.event_bus.emit(EventType.TURN_START, unit=char2, engine=engine)
        assert char1.hp == hp_before  # char1 should not have been healed

    # ── 卸载 ──

    def test_unequip_cleans_sources(self) -> None:
        char = self._make_char()
        char.equip_relic(Relic(part=RelicPart.HEAD, set_id=self._SET_ID,
                                main_stat=StatModifier(StatType.HP, StatModifierType.FLAT, 705.0)))
        char.equip_relic(Relic(part=RelicPart.HANDS, set_id=self._SET_ID,
                                main_stat=StatModifier(StatType.ATK, StatModifierType.FLAT, 352.0)))
        assert any(m.source.startswith("RelicSet_106_") for m in char.stats.active_modifiers)

        for part in (RelicPart.HEAD, RelicPart.HANDS, RelicPart.BODY, RelicPart.FEET):
            char.equip_relic(Relic(part=part, set_id="OtherSet",
                                    main_stat=StatModifier(StatType.ATK, StatModifierType.PERCENT, 0.30)))

        assert not any(m.source.startswith("RelicSet_106_") for m in char.stats.active_modifiers)


# ============================================================
#  TestHunterOfGlacialForest — 密林卧雪的猎人 (104)
# ============================================================


class TestHunterOfGlacialForest:
    """2件: 冰伤+10% / 4件: 终结技后暴伤+25%持续2回合"""

    _SET_ID = "104"
    _SOURCE_2PC = "RelicSet_104_2pc"
    _SOURCE_4PC = "RelicSet_104_4pc"

    def _make_char(self):
        return create_test_character("T", hp=1000, speed=100, atk=500.0, crit_rate=0.05, crit_dmg=0.50)

    def _make_state(self, char):
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])
        engine = CombatEngine(state)
        return state, engine

    def _equip_4pc(self, char):
        for part in (RelicPart.HEAD, RelicPart.HANDS, RelicPart.BODY, RelicPart.FEET):
            if part == RelicPart.HEAD:
                m = StatModifier(StatType.HP, StatModifierType.FLAT, 705.0)
            elif part == RelicPart.HANDS:
                m = StatModifier(StatType.ATK, StatModifierType.FLAT, 352.0)
            else:
                m = StatModifier(StatType.ATK, StatModifierType.PERCENT, 0.30)
            char.equip_relic(Relic(part=part, set_id=self._SET_ID, main_stat=m))

    def _get_source_mods(self, char, stat_type, source):
        return [m for m in char.stats.active_modifiers
                if m.stat_type == stat_type and m.source == source]

    # ── 2件套 ──

    def test_2pc_ice_dmg_bonus(self) -> None:
        char = self._make_char()
        char.equip_relic(Relic(part=RelicPart.HEAD, set_id=self._SET_ID,
                                main_stat=StatModifier(StatType.HP, StatModifierType.FLAT, 705.0)))
        char.equip_relic(Relic(part=RelicPart.HANDS, set_id=self._SET_ID,
                                main_stat=StatModifier(StatType.ATK, StatModifierType.FLAT, 352.0)))
        mods = self._get_source_mods(char, StatType.ICE_DMG_BONUS, self._SOURCE_2PC)
        assert len(mods) == 1
        assert mods[0].value == pytest.approx(0.10)

    def test_1pc_no_bonus(self) -> None:
        char = self._make_char()
        char.equip_relic(Relic(part=RelicPart.HEAD, set_id=self._SET_ID,
                                main_stat=StatModifier(StatType.HP, StatModifierType.FLAT, 705.0)))
        assert len(self._get_source_mods(char, StatType.ICE_DMG_BONUS, self._SOURCE_2PC)) == 0

    # ── 4件套 ──

    def test_4pc_crit_dmg_after_ultimate(self) -> None:
        char = self._make_char()
        self._equip_4pc(char)
        state, engine = self._make_state(char)
        start_relic_set_effects(state, char)

        engine.event_bus.emit(
            EventType.AFTER_ACTION,
            unit=char, target=None, action_type=ActionType.ULTIMATE,
        )
        mods = self._get_source_mods(char, StatType.CRIT_DMG, self._SOURCE_4PC)
        assert len(mods) == 1
        assert mods[0].value == pytest.approx(0.25)
        assert mods[0].duration == 2

    def test_4pc_queued_ultimate(self) -> None:
        char = self._make_char()
        self._equip_4pc(char)
        state, engine = self._make_state(char)
        start_relic_set_effects(state, char)

        engine.event_bus.emit(
            EventType.ON_ULTIMATE_INSERTED,
            character=char, target=None,
        )
        mods = self._get_source_mods(char, StatType.CRIT_DMG, self._SOURCE_4PC)
        assert len(mods) == 1
        assert mods[0].value == pytest.approx(0.25)

    def test_4pc_no_buff_on_basic(self) -> None:
        char = self._make_char()
        self._equip_4pc(char)
        state, engine = self._make_state(char)
        start_relic_set_effects(state, char)

        engine.event_bus.emit(
            EventType.AFTER_ACTION,
            unit=char, target=None, action_type=ActionType.BASIC_ATTACK,
        )
        assert len(self._get_source_mods(char, StatType.CRIT_DMG, self._SOURCE_4PC)) == 0

    def test_4pc_only_for_owner(self) -> None:
        char1 = self._make_char()
        char2 = create_test_character("T2", hp=1000, speed=100, atk=500.0)
        self._equip_4pc(char1)

        state, engine = self._make_state(char1)
        state.characters.append(char2)
        start_relic_set_effects(state, char1)

        engine.event_bus.emit(
            EventType.AFTER_ACTION,
            unit=char2, target=None, action_type=ActionType.ULTIMATE,
        )
        assert len(self._get_source_mods(char1, StatType.CRIT_DMG, self._SOURCE_4PC)) == 0

    def test_4pc_refresh_duration(self) -> None:
        char = self._make_char()
        self._equip_4pc(char)
        state, engine = self._make_state(char)
        start_relic_set_effects(state, char)

        for _ in range(2):
            engine.event_bus.emit(
                EventType.AFTER_ACTION,
                unit=char, target=None, action_type=ActionType.ULTIMATE,
            )
        mods = self._get_source_mods(char, StatType.CRIT_DMG, self._SOURCE_4PC)
        assert len(mods) == 1
        assert mods[0].duration == 2

    # ── 卸载 ──

    def test_unequip_cleans_sources(self) -> None:
        char = self._make_char()
        char.equip_relic(Relic(part=RelicPart.HEAD, set_id=self._SET_ID,
                                main_stat=StatModifier(StatType.HP, StatModifierType.FLAT, 705.0)))
        char.equip_relic(Relic(part=RelicPart.HANDS, set_id=self._SET_ID,
                                main_stat=StatModifier(StatType.ATK, StatModifierType.FLAT, 352.0)))
        assert any(m.source.startswith("RelicSet_104_") for m in char.stats.active_modifiers)

        for part in (RelicPart.HEAD, RelicPart.HANDS, RelicPart.BODY, RelicPart.FEET):
            char.equip_relic(Relic(part=part, set_id="OtherSet",
                                    main_stat=StatModifier(StatType.ATK, StatModifierType.PERCENT, 0.30)))

        assert not any(m.source.startswith("RelicSet_104_") for m in char.stats.active_modifiers)


# ============================================================
#  TestKnightOfPurityPalace — 净庭教宗的圣骑士 (103)
# ============================================================


class TestKnightOfPurityPalace:
    """2件: 防御力+15% / 4件: 护盾量+20%"""

    _SET_ID = "103"
    _SOURCE_2PC = "RelicSet_103_2pc"
    _SOURCE_4PC = "RelicSet_103_4pc"

    def _make_char(self):
        return create_test_character("T", hp=1000, speed=100, atk=500.0)

    def _get_source_mods(self, char, stat_type, source):
        return [m for m in char.stats.active_modifiers
                if m.stat_type == stat_type and m.source == source]

    # ── 2件套 ──

    def test_2pc_def_percent(self) -> None:
        char = self._make_char()
        char.equip_relic(Relic(part=RelicPart.HEAD, set_id=self._SET_ID,
                                main_stat=StatModifier(StatType.HP, StatModifierType.FLAT, 705.0)))
        char.equip_relic(Relic(part=RelicPart.HANDS, set_id=self._SET_ID,
                                main_stat=StatModifier(StatType.ATK, StatModifierType.FLAT, 352.0)))
        mods = self._get_source_mods(char, StatType.DEF, self._SOURCE_2PC)
        assert len(mods) == 1
        assert mods[0].value == pytest.approx(0.15)
        assert mods[0].modifier_type.name == "PERCENT"

    def test_1pc_no_bonus(self) -> None:
        char = self._make_char()
        char.equip_relic(Relic(part=RelicPart.HEAD, set_id=self._SET_ID,
                                main_stat=StatModifier(StatType.HP, StatModifierType.FLAT, 705.0)))
        assert len(self._get_source_mods(char, StatType.DEF, self._SOURCE_2PC)) == 0

    # ── 4件套 ──

    def test_4pc_shield_bonus(self) -> None:
        char = self._make_char()
        for part in (RelicPart.HEAD, RelicPart.HANDS, RelicPart.BODY, RelicPart.FEET):
            m = (StatModifier(StatType.HP, StatModifierType.FLAT, 705.0)
                 if part == RelicPart.HEAD
                 else StatModifier(StatType.ATK, StatModifierType.FLAT, 352.0)
                 if part == RelicPart.HANDS
                 else StatModifier(StatType.ATK, StatModifierType.PERCENT, 0.30))
            char.equip_relic(Relic(part=part, set_id=self._SET_ID, main_stat=m))
        mods = self._get_source_mods(char, StatType.SHIELD_BONUS, self._SOURCE_4PC)
        assert len(mods) == 1
        assert mods[0].value == pytest.approx(0.20)

    def test_2pc_and_4pc_combined(self) -> None:
        char = self._make_char()
        for part in (RelicPart.HEAD, RelicPart.HANDS, RelicPart.BODY, RelicPart.FEET):
            m = (StatModifier(StatType.HP, StatModifierType.FLAT, 705.0)
                 if part == RelicPart.HEAD
                 else StatModifier(StatType.ATK, StatModifierType.FLAT, 352.0)
                 if part == RelicPart.HANDS
                 else StatModifier(StatType.ATK, StatModifierType.PERCENT, 0.30))
            char.equip_relic(Relic(part=part, set_id=self._SET_ID, main_stat=m))
        assert len(self._get_source_mods(char, StatType.DEF, self._SOURCE_2PC)) == 1
        assert len(self._get_source_mods(char, StatType.SHIELD_BONUS, self._SOURCE_4PC)) == 1

    # ── 卸载 ──

    def test_unequip_cleans_sources(self) -> None:
        char = self._make_char()
        for part in (RelicPart.HEAD, RelicPart.HANDS, RelicPart.BODY, RelicPart.FEET):
            m = (StatModifier(StatType.HP, StatModifierType.FLAT, 705.0)
                 if part == RelicPart.HEAD
                 else StatModifier(StatType.ATK, StatModifierType.FLAT, 352.0)
                 if part == RelicPart.HANDS
                 else StatModifier(StatType.ATK, StatModifierType.PERCENT, 0.30))
            char.equip_relic(Relic(part=part, set_id=self._SET_ID, main_stat=m))
        assert any(m.source.startswith("RelicSet_103_") for m in char.stats.active_modifiers)

        for part in (RelicPart.HEAD, RelicPart.HANDS, RelicPart.BODY, RelicPart.FEET):
            char.equip_relic(Relic(part=part, set_id="OtherSet",
                                    main_stat=StatModifier(StatType.ATK, StatModifierType.PERCENT, 0.30)))

        assert not any(m.source.startswith("RelicSet_103_") for m in char.stats.active_modifiers)


# ============================================================
#  TestMusketeerOfWildWheat — 野穗伴行的快枪手 (102)
# ============================================================


class TestMusketeerOfWildWheat:
    """2件: ATK+12% / 4件: SPD+6% & 普攻伤害+10%"""

    _SET_ID = "102"
    _SOURCE_4PC = "RelicSet_102_4pc"

    def _make_char(self):
        return create_test_character("T", hp=1000, speed=100, atk=500.0)

    def test_4pc_basic_atk_dmg(self) -> None:
        char = self._make_char()
        for part in (RelicPart.HEAD, RelicPart.HANDS, RelicPart.BODY, RelicPart.FEET):
            m = (StatModifier(StatType.HP, StatModifierType.FLAT, 705.0)
                 if part == RelicPart.HEAD
                 else StatModifier(StatType.ATK, StatModifierType.FLAT, 352.0)
                 if part == RelicPart.HANDS
                 else StatModifier(StatType.ATK, StatModifierType.PERCENT, 0.30))
            char.equip_relic(Relic(part=part, set_id=self._SET_ID, main_stat=m))
        mods = [m for m in char.stats.active_modifiers
                if m.stat_type == StatType.BASIC_ATK_DMG and m.source == self._SOURCE_4PC]
        assert len(mods) == 1
        assert mods[0].value == pytest.approx(0.10)


# ============================================================
#  TestPasserbyOfWanderingCloud — 云无留迹的过客 (101)
# ============================================================


class TestPasserbyOfWanderingCloud:
    """2件: 治疗量+10% / 4件: 战斗开始时恢复1个战技点"""

    _SET_ID = "101"
    _SOURCE_2PC = "RelicSet_101_2pc"

    def _make_char(self):
        return create_test_character("T", hp=1000, speed=100, atk=500.0)

    def _make_state(self, char):
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])
        engine = CombatEngine(state)
        return state, engine

    def _equip_4pc(self, char):
        for part in (RelicPart.HEAD, RelicPart.HANDS, RelicPart.BODY, RelicPart.FEET):
            m = (StatModifier(StatType.HP, StatModifierType.FLAT, 705.0)
                 if part == RelicPart.HEAD
                 else StatModifier(StatType.ATK, StatModifierType.FLAT, 352.0)
                 if part == RelicPart.HANDS
                 else StatModifier(StatType.ATK, StatModifierType.PERCENT, 0.30))
            char.equip_relic(Relic(part=part, set_id=self._SET_ID, main_stat=m))

    def _get_source_mods(self, char, stat_type, source):
        return [m for m in char.stats.active_modifiers
                if m.stat_type == stat_type and m.source == source]

    # ── 2件套 ──

    def test_2pc_healing_bonus(self) -> None:
        char = self._make_char()
        char.equip_relic(Relic(part=RelicPart.HEAD, set_id=self._SET_ID,
                                main_stat=StatModifier(StatType.HP, StatModifierType.FLAT, 705.0)))
        char.equip_relic(Relic(part=RelicPart.HANDS, set_id=self._SET_ID,
                                main_stat=StatModifier(StatType.ATK, StatModifierType.FLAT, 352.0)))
        mods = self._get_source_mods(char, StatType.OUTGOING_HEALING_BOOST, self._SOURCE_2PC)
        assert len(mods) == 1
        assert mods[0].value == pytest.approx(0.10)

    def test_1pc_no_bonus(self) -> None:
        char = self._make_char()
        char.equip_relic(Relic(part=RelicPart.HEAD, set_id=self._SET_ID,
                                main_stat=StatModifier(StatType.HP, StatModifierType.FLAT, 705.0)))
        assert len(self._get_source_mods(char, StatType.OUTGOING_HEALING_BOOST, self._SOURCE_2PC)) == 0

    # ── 4件套 ──

    def test_4pc_restore_sp(self) -> None:
        char = self._make_char()
        self._equip_4pc(char)
        state, engine = self._make_state(char)
        start_relic_set_effects(state, char)

        sp_before = state.skill_points
        engine.event_bus.emit(EventType.BATTLE_START, engine=engine)
        assert state.skill_points == sp_before + 1

    def test_4pc_no_sp_without_4pc(self) -> None:
        char = self._make_char()
        char.equip_relic(Relic(part=RelicPart.HEAD, set_id=self._SET_ID,
                                main_stat=StatModifier(StatType.HP, StatModifierType.FLAT, 705.0)))
        char.equip_relic(Relic(part=RelicPart.HANDS, set_id=self._SET_ID,
                                main_stat=StatModifier(StatType.ATK, StatModifierType.FLAT, 352.0)))
        state, engine = self._make_state(char)
        start_relic_set_effects(state, char)

        sp_before = state.skill_points
        engine.event_bus.emit(EventType.BATTLE_START, engine=engine)
        assert state.skill_points == sp_before

    # ── 卸载 ──

    def test_unequip_cleans_sources(self) -> None:
        char = self._make_char()
        char.equip_relic(Relic(part=RelicPart.HEAD, set_id=self._SET_ID,
                                main_stat=StatModifier(StatType.HP, StatModifierType.FLAT, 705.0)))
        char.equip_relic(Relic(part=RelicPart.HANDS, set_id=self._SET_ID,
                                main_stat=StatModifier(StatType.ATK, StatModifierType.FLAT, 352.0)))
        assert any(m.source.startswith("RelicSet_101_") for m in char.stats.active_modifiers)

        for part in (RelicPart.HEAD, RelicPart.HANDS, RelicPart.BODY, RelicPart.FEET):
            char.equip_relic(Relic(part=part, set_id="OtherSet",
                                    main_stat=StatModifier(StatType.ATK, StatModifierType.PERCENT, 0.30)))

        assert not any(m.source.startswith("RelicSet_101_") for m in char.stats.active_modifiers)


# ============================================================
#  TestThiefOfShootingMeteor — 流星追迹的怪盗 (111)
# ============================================================


class TestThiefOfShootingMeteor:
    """2件: 击破特攻+16% / 4件: 击破特攻+16% & 击破弱点后恢复3能量"""

    _SET_ID = "111"
    _SOURCE_2PC = "RelicSet_111_2pc"
    _SOURCE_4PC_BE = "RelicSet_111_4pc_be"

    def _make_char(self):
        return create_test_character("T", hp=1000, speed=100, atk=500.0)

    def _make_state(self, char):
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])
        engine = CombatEngine(state)
        return state, engine

    def _equip_2pc(self, char):
        char.equip_relic(Relic(part=RelicPart.HEAD, set_id=self._SET_ID,
                                main_stat=StatModifier(StatType.HP, StatModifierType.FLAT, 705.0)))
        char.equip_relic(Relic(part=RelicPart.HANDS, set_id=self._SET_ID,
                                main_stat=StatModifier(StatType.ATK, StatModifierType.FLAT, 352.0)))

    def _equip_4pc(self, char):
        for part in (RelicPart.HEAD, RelicPart.HANDS, RelicPart.BODY, RelicPart.FEET):
            m = (StatModifier(StatType.HP, StatModifierType.FLAT, 705.0)
                 if part == RelicPart.HEAD
                 else StatModifier(StatType.ATK, StatModifierType.FLAT, 352.0)
                 if part == RelicPart.HANDS
                 else StatModifier(StatType.ATK, StatModifierType.PERCENT, 0.30))
            char.equip_relic(Relic(part=part, set_id=self._SET_ID, main_stat=m))

    def _be_total(self, char):
        return sum(m.value for m in char.stats.active_modifiers
                   if m.stat_type == StatType.BREAK_EFFECT
                   and (m.source == self._SOURCE_2PC or m.source == self._SOURCE_4PC_BE))

    # ── 2件套 ──

    def test_2pc_break_effect(self) -> None:
        char = self._make_char()
        self._equip_2pc(char)
        mods = [m for m in char.stats.active_modifiers
                if m.stat_type == StatType.BREAK_EFFECT and m.source == self._SOURCE_2PC]
        assert len(mods) == 1
        assert mods[0].value == pytest.approx(0.16)

    def test_1pc_no_bonus(self) -> None:
        char = self._make_char()
        char.equip_relic(Relic(part=RelicPart.HEAD, set_id=self._SET_ID,
                                main_stat=StatModifier(StatType.HP, StatModifierType.FLAT, 705.0)))
        assert not any(m.stat_type == StatType.BREAK_EFFECT and m.source == self._SOURCE_2PC
                       for m in char.stats.active_modifiers)

    # ── 4件套 ──

    def test_4pc_accumulated_break_effect(self) -> None:
        char = self._make_char()
        self._equip_4pc(char)
        assert self._be_total(char) == pytest.approx(0.32)

    def test_4pc_energy_on_weakness_break(self) -> None:
        char = self._make_char()
        char.set_energy(0)
        self._equip_4pc(char)
        state, engine = self._make_state(char)
        start_relic_set_effects(state, char)

        engine.event_bus.emit(
            EventType.ON_WEAKNESS_BREAK,
            source=char, target=None,
        )
        assert char.energy == 3

    def test_4pc_only_for_owner(self) -> None:
        char1 = self._make_char()
        char1.set_energy(0)
        char2 = create_test_character("T2", hp=1000, speed=100, atk=500.0)
        self._equip_4pc(char1)

        state, engine = self._make_state(char1)
        state.characters.append(char2)
        start_relic_set_effects(state, char1)

        engine.event_bus.emit(
            EventType.ON_WEAKNESS_BREAK,
            source=char2, target=None,
        )
        assert char1.energy == 0

    # ── 卸载 ──

    def test_unequip_cleans_sources(self) -> None:
        char = self._make_char()
        self._equip_4pc(char)
        assert any(m.source.startswith("RelicSet_111_") for m in char.stats.active_modifiers)

        for part in (RelicPart.HEAD, RelicPart.HANDS, RelicPart.BODY, RelicPart.FEET):
            char.equip_relic(Relic(part=part, set_id="OtherSet",
                                    main_stat=StatModifier(StatType.ATK, StatModifierType.PERCENT, 0.30)))

        assert not any(m.source.startswith("RelicSet_111_") for m in char.stats.active_modifiers)

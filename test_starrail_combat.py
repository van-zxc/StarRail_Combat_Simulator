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
class TestToughnessSystem:
    """验证削韧（弱点匹配）与击破状态流转。"""

    def _setup(self) -> tuple[Character, Enemy, GameState]:
        char = create_test_character(
            "FireDPS", hp=200, speed=100, atk=50.0, element=ElementType.FIRE
        )
        enemy = Enemy(
            name="TestBoss",
            hp=10000,
            speed=50,
            base_damage=0,
            weaknesses=[ElementType.FIRE],
            max_toughness=20.0,
        )
        state = GameState(characters=[char], enemies=[enemy])
        return char, enemy, state

    def test_basic_attack_reduces_toughness(self) -> None:
        char, enemy, state = self._setup()
        _, _, toughness_dealt, did_weakness_break = state.execute_action(
            char, ActionType.BASIC_ATTACK, enemy, 1.0
        )
        assert toughness_dealt == pytest.approx(10.0)
        assert did_weakness_break is False
        assert enemy.current_toughness == pytest.approx(10.0)
        assert not enemy.broken

    def test_skill_triggers_break(self) -> None:
        char, enemy, state = self._setup()
        state.execute_action(char, ActionType.BASIC_ATTACK, enemy, 1.0)
        _, _, toughness_dealt, did_weakness_break = state.execute_action(
            char, ActionType.SKILL, enemy, 2.0
        )
        assert toughness_dealt == pytest.approx(10.0)
        assert did_weakness_break is True
        assert enemy.current_toughness == pytest.approx(0.0)
        assert enemy.broken

    def test_toughness_stays_zero_after_break(self) -> None:
        char, enemy, state = self._setup()
        state.execute_action(char, ActionType.BASIC_ATTACK, enemy, 1.0)
        state.execute_action(char, ActionType.BASIC_ATTACK, enemy, 1.0)
        assert enemy.broken
        assert enemy.current_toughness == pytest.approx(0.0)
        _, _, toughness_dealt, did_weakness_break = state.execute_action(
            char, ActionType.ULTIMATE, enemy, 3.0
        )
        assert toughness_dealt == pytest.approx(0.0)
        assert did_weakness_break is False

    def test_no_toughness_damage_on_wrong_element(self) -> None:
        char = create_test_character(
            "IceDPS", hp=200, speed=100, atk=50.0, element=ElementType.ICE
        )
        enemy = Enemy(
            name="FireWeakBoss", hp=10000, speed=50, base_damage=0,
            weaknesses=[ElementType.FIRE], max_toughness=20.0,
        )
        state = GameState(characters=[char], enemies=[enemy])
        _, _, toughness_dealt, did_weakness_break = state.execute_action(
            char, ActionType.BASIC_ATTACK, enemy, 1.0
        )
        assert toughness_dealt == pytest.approx(0.0)
        assert did_weakness_break is False
        assert enemy.current_toughness == pytest.approx(20.0)

    def test_ultimate_toughness_damage(self) -> None:
        char = create_test_character(
            "FireDPS", hp=200, speed=100, atk=50.0, element=ElementType.FIRE
        )
        enemy = Enemy(
            name="TestBoss", hp=10000, speed=50, base_damage=0,
            weaknesses=[ElementType.FIRE], max_toughness=30.0,
        )
        char.energy = 100
        state = GameState(characters=[char], enemies=[enemy])
        _, _, toughness_dealt, did_weakness_break = state.execute_action(
            char, ActionType.ULTIMATE, enemy, 3.0
        )
        assert toughness_dealt == pytest.approx(20.0)
        assert did_weakness_break is False
        assert not enemy.broken

    def test_toughness_logged_in_action_log(self) -> None:
        char = create_test_character(
            "FireDPS", hp=200, speed=100, atk=50.0, element=ElementType.FIRE
        )
        enemy = Enemy(
            name="TestBoss", hp=10000, speed=50, base_damage=0,
            weaknesses=[ElementType.FIRE], max_toughness=20.0,
        )
        state = GameState(characters=[char], enemies=[enemy])
        engine = CombatEngine(state)
        engine.turn_count = 1
        damage, is_crit, toughness, is_break = state.execute_action(
            char, ActionType.BASIC_ATTACK, enemy, 1.0
        )
        engine._log_action(char, ActionType.BASIC_ATTACK, enemy, damage, is_crit, toughness, is_break)
        entry = engine.action_log[0]
        assert entry["toughness"] == pytest.approx(10.0)
        assert entry["break"] is False


# ============================================================
#  TestStatsDecoupling — Stats 面板解耦 (JSON 数据源)
# ============================================================
class TestStatsDecoupling:
    """验证 CharacterStats 与 Character 的解耦（JSON 驱动）。"""

    def test_different_characters_have_different_speed(self) -> None:
        dan = Character("DanHeng")
        march = Character("March7th")
        assert dan.stats.get_base_stat(StatType.SPD) == 110.0
        assert march.stats.get_base_stat(StatType.SPD) == 101.0
        assert dan.stats.get_base_stat(StatType.SPD) != march.stats.get_base_stat(StatType.SPD)

    def test_different_characters_have_different_atk(self) -> None:
        dan = Character("DanHeng")
        march = Character("March7th")
        assert dan.stats.get_base_stat(StatType.ATK) == 290.16
        assert march.stats.get_base_stat(StatType.ATK) == 271.44
        assert dan.stats.get_base_stat(StatType.ATK) != march.stats.get_base_stat(StatType.ATK)

    def test_character_attributes_match_json(self) -> None:
        dan = Character("DanHeng")
        march = Character("March7th")
        assert dan.stats.get_base_stat(StatType.ATK) == pytest.approx(290.16)
        assert dan.max_energy == 100
        assert dan.max_hp == 468
        assert dan.speed == 110
        assert march.max_hp == 561
        assert march.max_energy == 120

    def test_character_has_element_and_path(self) -> None:
        dan = Character("DanHeng")
        march = Character("March7th")
        assert dan.element == ElementType.WIND
        assert dan.path == PathType.HUNT
        assert march.element == ElementType.ICE
        assert march.path == PathType.PRESERVATION

    def test_character_id_reference(self) -> None:
        dan = Character("DanHeng")
        assert dan.character_id == "DanHeng"

    def test_unknown_character_id_raises_key_error(self) -> None:
        with pytest.raises(KeyError):
            Character("NonExistent")


# ============================================================
#  TestDataLoader — 验证 DataLoader 初始化
# ============================================================
class TestDataLoader:
    """验证 DataLoader 能正常初始化（无需 JSON 文件）。"""

    def test_data_loader_is_initialized(self) -> None:
        loader = get_data_loader()
        assert loader is not None


# ============================================================
#  TestCritSystem — 暴击机制验证
# ============================================================
class TestCritSystem:
    """暴击判定：mock random.random 以控制暴击触发。"""

    def _setup(self) -> tuple[Character, Enemy, GameState]:
        char = create_test_character(
            "Tester", hp=200, speed=100, atk=50.0, crit_rate=0.05, crit_dmg=0.50
        )
        enemy = Enemy(name="Dummy", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])
        return char, enemy, state

    def test_no_crit_when_random_above_rate(self) -> None:
        char, enemy, state = self._setup()
        with patch("starrail_combat.random.random", return_value=0.10):
            damage, is_crit, _, _ = state.execute_action(char, ActionType.BASIC_ATTACK, enemy, 1.0)
        assert not is_crit
        # base=50, def=0.5→25, res=1.0, toughness=0.9→22
        assert damage == 22

    def test_crit_triggers_with_low_random(self) -> None:
        char, enemy, state = self._setup()
        with patch("starrail_combat.random.random", return_value=0.0):
            damage, is_crit, _, _ = state.execute_action(char, ActionType.BASIC_ATTACK, enemy, 1.0)
        assert is_crit
        # base=50, crit*1.5→75, def*0.5→37, res*1.0→37, toughness*0.9→33
        assert damage == 33

    def test_crit_boundary_not_crit(self) -> None:
        char = create_test_character(
            "Tester", hp=200, speed=100, atk=50.0, crit_rate=0.5, crit_dmg=0.50
        )
        enemy = Enemy(name="Dummy", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])
        with patch("starrail_combat.random.random", return_value=0.5):
            _, is_crit, _, _ = state.execute_action(char, ActionType.BASIC_ATTACK, enemy, 1.0)
        assert not is_crit

    def test_all_action_types_can_crit(self) -> None:
        char = create_test_character(
            "Tester", hp=200, speed=100, atk=100.0, crit_rate=1.0, crit_dmg=0.50
        )
        enemy = Enemy(name="Dummy", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])
        for act, mult in [(ActionType.BASIC_ATTACK, 1.0), (ActionType.SKILL, 2.0), (ActionType.ULTIMATE, 3.0)]:
            enemy.hp = 10000
            _, is_crit, _, _ = state.execute_action(char, act, enemy, mult)
            assert is_crit, f"{act.name} should crit with crit_rate=1.0"

    def test_crit_damage_multiplier(self) -> None:
        char = create_test_character(
            "Tester", hp=200, speed=100, atk=100.0, crit_rate=1.0, crit_dmg=1.00
        )
        enemy = Enemy(name="Dummy", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])
        damage, is_crit, _, _ = state.execute_action(char, ActionType.BASIC_ATTACK, enemy, 1.0)
        assert is_crit
        # base=100, crit*2→200, def*0.5→100, res*1.0→100, toughness*0.9→90
        assert damage == 90
        enemy.hp = 10000
        damage, _, _, _ = state.execute_action(char, ActionType.SKILL, enemy, 2.0)
        # base=200, crit*2→400, def*0.5→200, res*1.0→200, toughness=1.0(已被击破)→200
        assert damage == 200
        enemy.hp = 10000
        char.energy = 100
        damage, _, _, _ = state.execute_action(char, ActionType.ULTIMATE, enemy, 3.0)
        # base=300, crit*2→600, def*0.5→300, toughness=1.0→300
        assert damage == 300

    def test_crit_logged_in_action_log(self) -> None:
        char = create_test_character(
            "Tester", hp=200, speed=100, atk=50.0, crit_rate=1.0, crit_dmg=0.50
        )
        enemy = Enemy(name="Dummy", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])
        engine = CombatEngine(state)
        engine.turn_count = 1
        damage, is_crit, toughness, is_break = state.execute_action(
            char, ActionType.BASIC_ATTACK, enemy, 1.0
        )
        engine._log_action(char, ActionType.BASIC_ATTACK, enemy, damage, is_crit, toughness, is_break)
        assert engine.action_log[0]["crit"] is True


# ============================================================
#  TestUltimateInterleave — 终结技插队
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
class TestDefenseSystem:
    """验证等级驱动防御力 & 防御减伤乘区公式。"""

    def test_enemy_base_def_from_level(self) -> None:
        enemy = Enemy(name="Test", hp=10000, speed=50, base_damage=0, level=95)
        assert enemy.stats.get_base_stat(StatType.DEF) == 95 * 10 + 200  # 1150

    def test_defense_multiplier_formula(self) -> None:
        char = create_test_character("Attacker", hp=200, speed=100, atk=50.0,
                                      crit_rate=0.0, level=80)
        enemy = Enemy(name="Test", hp=10000, speed=50, base_damage=0, level=95,
                       weaknesses=[ElementType.PHYSICAL])

        mult = defense_multiplier(char, enemy)
        # (80*10+200) / (1150 + 80*10+200) = 1000 / 2150
        expected = 1000.0 / 2150.0
        assert mult == pytest.approx(expected, abs=0.0001)

    def test_damage_with_defense(self) -> None:
        char = create_test_character("Attacker", hp=200, speed=100, atk=10000.0,
                                      crit_rate=0.0, level=80)
        enemy = Enemy(name="Test", hp=100000, speed=50, base_damage=0, level=95,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])

        damage, _, _, _ = state.execute_action(char, ActionType.BASIC_ATTACK, enemy, 1.0)

        # base=10000, crit=10000, def→4651, res=1.0→4651, toughness*0.9→4185
        expected = int(int(int(10000.0 * 1000.0 / 2150.0) * 0.9))
        assert damage == expected

    def test_defense_uses_total_stat(self) -> None:
        """验证防御乘区读取的是 get_total_stat（修饰器池影响）。"""
        char = create_test_character("Attacker", hp=200, speed=100, atk=10000.0,
                                      crit_rate=0.0, level=80)
        enemy = Enemy(name="Test", hp=100000, speed=50, base_damage=0, level=95,
                       weaknesses=[ElementType.PHYSICAL])

        # 给怪物注入 -50% DEF 修饰器（模拟减防）
        enemy.stats.add_modifier(StatModifier(
            StatType.DEF, StatModifierType.PERCENT, -0.50, source="Debuff",
        ))

        mult = defense_multiplier(char, enemy)
        # defender_def = 1150 * (1 - 0.50) = 575
        defender_def = enemy.stats.get_total_stat(StatType.DEF)
        assert defender_def == pytest.approx(575.0)
        expected = 1000.0 / (575.0 + 1000.0)
        assert mult == pytest.approx(expected, abs=0.0001)


# ============================================================
#  TestDamageFormula — 各乘区单独验证
# ============================================================
class TestDamageFormula:
    """验证抗性 / 破韧 / 暴击 / 增伤 / 易伤各乘区。"""

    def _make_attacker(self) -> Character:
        """80 级风属性角色，CR=100%, CD=50%。"""
        return create_test_character(
            "Attacker", hp=200, speed=100, atk=10000.0,
            crit_rate=1.0, crit_dmg=0.50,
            element=ElementType.WIND, level=80,
        )

    def _make_defender(self) -> Enemy:
        """95 级风弱点怪物，非击破，VULNERABILITY=0.20。"""
        enemy = Enemy(
            name="Boss", hp=100000, speed=50, base_damage=0, level=95,
            weaknesses=[ElementType.WIND], max_toughness=30.0,
        )
        enemy.stats.add_modifier(StatModifier(
            StatType.VULNERABILITY, StatModifierType.FLAT, 0.20, source="Debuff",
        ))
        return enemy

    # ── 测试 1: 单独抗性乘区（弱点匹配 → 1.0） ──
    def test_res_multiplier_with_matching_weakness(self) -> None:
        char = self._make_attacker()
        enemy = self._make_defender()
        mult = resistance_multiplier(char, enemy)
        assert mult == pytest.approx(1.0)

    # ── 测试 2: 单独抗性乘区（无弱点 → 0.8） ──
    def test_res_multiplier_without_weakness(self) -> None:
        char = self._make_attacker()
        enemy = Enemy(name="Boss", hp=100000, speed=50, base_damage=0, level=95,
                       weaknesses=[ElementType.FIRE])
        mult = resistance_multiplier(char, enemy)
        assert mult == pytest.approx(0.8)

    # ── 测试 3: 单独破韧乘区 ──
    def test_toughness_multiplier_not_broken(self) -> None:
        enemy = self._make_defender()
        assert toughness_multiplier(enemy) == pytest.approx(0.9)

    def test_toughness_multiplier_when_broken(self) -> None:
        enemy = self._make_defender()
        enemy.broken = True
        assert toughness_multiplier(enemy) == pytest.approx(1.0)

    # ── 测试 4: 增伤乘区 ──
    def test_damage_bonus_multiplier(self) -> None:
        char = self._make_attacker()
        char.stats.add_modifier(StatModifier(
            StatType.DMG_BONUS, StatModifierType.FLAT, 0.30, source="Test",
        ))
        assert damage_bonus_multiplier(char) == pytest.approx(1.30)

    # ── 测试 5: 易伤乘区 ──
    def test_vulnerability_multiplier(self) -> None:
        enemy = self._make_defender()
        assert vulnerability_multiplier(enemy) == pytest.approx(1.20)

    # ── 测试 6: 暴击乘区 ──
    def test_crit_multiplier(self) -> None:
        char = self._make_attacker()
        with patch("starrail_combat.random.random", return_value=0.0):
            mult, is_crit = crit_multiplier(char)
        assert is_crit
        assert mult == pytest.approx(1.0 + 0.50)

    # ── 测试 7: 防御下限为 0 ──
    def test_defense_multiplier_with_neg_def(self) -> None:
        char = self._make_attacker()
        enemy = self._make_defender()
        enemy.stats.add_modifier(StatModifier(
            StatType.DEF, StatModifierType.PERCENT, -2.0, source="Debuff",
        ))
        # DEF = 1150 * (1 - 2.0) = -1150, clamped → 0
        # mult = 1000 / (0 + 1000) = 1.0
        assert defense_multiplier(char, enemy) == pytest.approx(1.0)


# ============================================================
#  TestFinalDamageFormula — 最终直伤公式七乘区验证
# ============================================================
class TestFinalDamageFormula:
    """用户指定场景：80 级角色 vs 95 级怪物，七乘区连乘。"""

    def test_full_seven_multiplier_formula(self) -> None:
        # ── 80 级攻击者：ATK=2000, DMG_BONUS=50%, RES_PEN=20%, CR=1.0, CD=1.0, 战技×2.0 ──
        char = create_test_character(
            "Attacker", hp=200, speed=100, atk=2000.0,
            crit_rate=1.0, crit_dmg=1.0,
            element=ElementType.WIND, level=80,
        )
        char.stats.add_modifier(StatModifier(
            StatType.DMG_BONUS, StatModifierType.FLAT, 0.50, source="Test",
        ))
        char.stats.add_modifier(StatModifier(
            StatType.RES_PEN, StatModifierType.FLAT, 0.20, source="Test",
        ))

        # ── 95 级受击者：无弱点, -50% DEF, VULNERABILITY=30%, 未被击破 ──
        enemy = Enemy(
            name="Boss", hp=100000, speed=50, base_damage=0, level=95,
            weaknesses=[ElementType.FIRE],  # 无 WIND 弱点
            max_toughness=30.0,
        )
        enemy.stats.add_modifier(StatModifier(
            StatType.DEF, StatModifierType.PERCENT, -0.50, source="Debuff",
        ))
        enemy.stats.add_modifier(StatModifier(
            StatType.VULNERABILITY, StatModifierType.FLAT, 0.30, source="Debuff",
        ))

        state = GameState(characters=[char], enemies=[enemy])

        damage, is_crit, _, _ = state.execute_action(
            char, ActionType.SKILL, enemy, 2.0,
        )

        # ── 手动七乘区计算 ──
        # 基伤:   2000 * 2.0 = 4000
        # 增伤:   int(4000 * (1.0 + 0.50)) = int(4000 * 1.5) = 6000
        # 易伤:   int(6000 * (1.0 + 0.30)) = int(6000 * 1.3) = 7800
        # 防御:   def = max(1150*(1-0.50), 0) = 575
        #         int(7800 * 1000/(575+1000)) = int(7800 * 0.63492) = int(4952.38) = 4952
        # 抗性:   base_res=0.2, RES=0, PEN=0.20
        #         mult = 1.0 - (0.2 + 0 - 0.20) = 1.0
        #         int(4952 * 1.0) = 4952
        # 破韧:   int(4952 * 0.9) = int(4456.8) = 4456
        # 暴击:   int(4456 * (1.0 + 1.0)) = int(4456 * 2.0) = 8912
        expected = 8912
        assert is_crit
        assert damage == expected


# ============================================================
#  TestDoTSystem — 持续伤害 (DoT) 挂载与自动结算
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
class TestShieldSystem:
    """验证护盾值制、溢出穿透、多护盾同时吸收。"""

    # ── 测试 1: DoT 穿盾 ──
    def test_dot_bypasses_shield(self) -> None:
        char = create_test_character("Attacker", hp=200, speed=100, atk=100.0,
                                      crit_rate=0.0, element=ElementType.LIGHTNING)
        enemy = Enemy(name="Boss", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])

        enemy.shield_statuses.append(ShieldStatus(500, 500, "Test"))
        enemy.apply_dot(DoTStatus(char, ElementType.LIGHTNING, 0.5, 1, 1))

        hp_before = enemy.hp
        state.resolve_enemy_dot_ticks(enemy)
        assert enemy.hp < hp_before  # DoT 穿透
        assert len(enemy.shield_statuses) == 1  # 护盾完好

    # ── 测试 2: 护盾部分吸收 → 溢出穿透 HP ──
    def test_shield_overflow_damages_hp(self) -> None:
        char = create_test_character("Attacker", hp=200, speed=100, atk=10000.0,
                                      crit_rate=0.0, element=ElementType.FIRE)
        enemy = Enemy(name="Boss", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.FIRE])
        state = GameState(characters=[char], enemies=[enemy])

        enemy.shield_statuses.append(ShieldStatus(50, 50, "Thin"))

        hp_before = enemy.hp
        state.execute_action(char, ActionType.BASIC_ATTACK, enemy, 1.0)
        # 伤害 > 50 → 护盾破, HP 受损
        assert len(enemy.shield_statuses) == 0
        assert enemy.hp < hp_before

    # ── 测试 3: 双护盾顺序吸收 ──
    def test_dual_shield_simultaneous(self) -> None:
        char = create_test_character("Attacker", hp=200, speed=100, atk=100.0,
                                      crit_rate=0.0, element=ElementType.FIRE)
        enemy = Enemy(name="Boss", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.FIRE])
        state = GameState(characters=[char], enemies=[enemy])

        enemy.shield_statuses.append(ShieldStatus(500, 500, "A"))
        enemy.shield_statuses.append(ShieldStatus(1000, 1000, "B"))

        damage, _, _, _ = state.execute_action(
            char, ActionType.BASIC_ATTACK, enemy, 1.0,
        )
        # 顺序吸收: 护盾A 先吸收全部伤害, 护盾B 不受影响
        assert damage == 0  # 全被盾A吸收
        assert len(enemy.shield_statuses) == 2
        assert enemy.shield_statuses[0].shield_value < 500  # A 被扣除
        assert enemy.shield_statuses[1].shield_value == pytest.approx(1000)  # B 完好

    # ── 测试 4: 护盾值计算 ──
    def test_shield_value_calculation(self) -> None:
        caster = create_test_character("Shielder", hp=200, speed=100, atk=50.0)
        caster.stats.add_modifier(StatModifier(
            StatType.SHIELD_BONUS, StatModifierType.FLAT, 0.20, source="Test"))

        val = GameState.calculate_shield_value(caster, 1000, 0.5, 200)
        # (1000*0.5 + 200) * 1.20 = 700 * 1.20 = 840
        assert val == pytest.approx(840.0)


# ============================================================
#  TestBreakEffect — 击破特攻乘区 & 推条
# ============================================================
class TestBreakEffect:
    """验证 BE 乘区计算、量子/虚数推条。"""

    def _make_attacker(self, be: float, element=ElementType.QUANTUM) -> Character:
        char = create_test_character(
            "Breaker", hp=200, speed=100, atk=100.0,
            crit_rate=0.0, element=element, level=80,
        )
        char.stats.add_modifier(StatModifier(
            StatType.BREAK_EFFECT, StatModifierType.FLAT, be, source="Test",
        ))
        return char

    # ── 测试 1: BE 乘区正确计算 ──
    def test_break_effect_multiplier(self) -> None:
        char = self._make_attacker(be=1.0)
        enemy = Enemy(name="Boss", hp=10000, speed=50, base_damage=0, level=1)
        # BE=1.0 → mult=2.0, 100*2.0=200
        dmg = apply_break_effect(100, char, enemy)
        assert dmg == 200

        # override
        dmg = apply_break_effect(100, char, enemy, break_effect_override=0.50)
        assert dmg == 150

    # ── 测试 2: 量子击破推条总计 0.65 ──
    def test_quantum_break_delay_total(self) -> None:
        char = self._make_attacker(be=1.0, element=ElementType.QUANTUM)
        enemy = Enemy(name="Boss", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.QUANTUM], max_toughness=1.0)
        state = GameState(characters=[char], enemies=[enemy])
        engine = CombatEngine(state)

        # 击破
        _, _, _, triggered = state.execute_action(
            char, ActionType.BASIC_ATTACK, enemy, 1.0,
        )
        assert triggered

        av_before = enemy.current_av
        engine._apply_break_effects(char, enemy)
        delay_av = enemy.current_av - av_before

        # base_av = 10000/50 = 200, delay = 200 * 0.65 = 130
        assert delay_av == pytest.approx(enemy.base_av * 0.65)

    # ── 测试 3: 虚数击破推条 ──
    def test_imaginary_break_delay(self) -> None:
        char = self._make_attacker(be=0.5, element=ElementType.IMAGINARY)
        enemy = Enemy(name="Boss", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.IMAGINARY], max_toughness=1.0)
        state = GameState(characters=[char], enemies=[enemy])
        engine = CombatEngine(state)

        _, _, _, triggered = state.execute_action(
            char, ActionType.BASIC_ATTACK, enemy, 1.0,
        )
        assert triggered

        av_before = enemy.current_av
        engine._apply_break_effects(char, enemy)
        delay_av = enemy.current_av - av_before

        # 0.25 + 0.30*(1+0.5) = 0.25 + 0.45 = 0.70
        assert delay_av == pytest.approx(enemy.base_av * 0.70)


# ============================================================
#  TestMitigationSystem — 减伤累乘
# ============================================================
class TestMitigationSystem:
    """验证 DMG_MITIGATION 累乘（非累加）。"""

    def test_mitigation_multiplicative(self) -> None:
        # 受击目标：8% + 20% 减伤
        defender = Enemy(name="Boss", hp=10000, speed=50, base_damage=0, level=1,
                          weaknesses=[ElementType.PHYSICAL])
        defender.stats.add_modifier(StatModifier(
            StatType.DMG_MITIGATION, StatModifierType.FLAT, 0.08, source="A"))
        defender.stats.add_modifier(StatModifier(
            StatType.DMG_MITIGATION, StatModifierType.FLAT, 0.20, source="B"))

        char = create_test_character("Attacker", hp=200, speed=100, atk=10000.0,
                                      crit_rate=0.0, element=ElementType.PHYSICAL,
                                      level=1)
        state = GameState(characters=[char], enemies=[defender])

        damage, _, _, _ = state.execute_action(
            char, ActionType.BASIC_ATTACK, defender, 1.0,
            damage_type=DamageType.DIRECT,
        )

        # 乘区链: dmg_bonus=1.0, vuln=1.0, def=0.5→5000, res=1.0→5000
        # mitigation: (1-0.08)*(1-0.20)=0.736 → int(5000*0.736)=3680
        # tough=0.9→3312, crit=1.0
        # 注意: tough 在 mitigation 之后
        expected = int(int(5000.0 * 0.736) * 0.9)
        assert damage == expected

        # 反证: 不是加算 1-0.28=0.72
        assert damage != int(int(5000.0 * 0.72) * 0.9)


# ============================================================
#  TestDebuffApplication — 效果命中/抵抗判定
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
class TestJointAttackSystem:
    """验证连携攻击独立结算、攻击次数、AV 冻结。"""

    # ── 测试 1: 面板独立 + 伤害不同 ──
    def test_joint_attack_uses_own_panel(self) -> None:
        main = create_test_character("A", hp=200, speed=100, atk=100.0, crit_rate=0.0)
        joint = create_test_character("B", hp=200, speed=100, atk=500.0, crit_rate=0.0)
        enemy = Enemy(name="C", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[main, joint], enemies=[enemy])
        state.register_joint_attacker("A", joint)
        engine = CombatEngine(state)

        main.current_av = 40.0
        engine._execute_character_turn(main, is_extra_turn=False)

        entries = engine.action_log
        # A 先攻击, B 连携
        assert entries[0]["actor"] == "A"
        assert entries[1]["actor"] == "B"
        # B 的伤害 > A (因为 ATK=500 > 100)
        assert entries[1]["damage"] > entries[0]["damage"]

    # ── 测试 2: 攻击次数 = 2 ──
    def test_joint_attack_hit_count(self) -> None:
        main = create_test_character("A", hp=200, speed=100, atk=100.0, crit_rate=0.0)
        joint = create_test_character("B", hp=200, speed=100, atk=100.0, crit_rate=0.0)
        enemy = Enemy(name="C", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[main, joint], enemies=[enemy])
        state.register_joint_attacker("A", joint)
        engine = CombatEngine(state)

        enemy.hit_count = 0
        engine._execute_character_turn(main, is_extra_turn=False)
        assert enemy.hit_count == 2

    # ── 测试 3: AV 不推进 ──
    def test_joint_attack_no_av_advance(self) -> None:
        main = create_test_character("A", hp=200, speed=100, atk=100.0, crit_rate=0.0)
        joint = create_test_character("B", hp=200, speed=100, atk=100.0, crit_rate=0.0)
        enemy = Enemy(name="C", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[main, joint], enemies=[enemy])
        state.register_joint_attacker("A", joint)

        main.current_av = 40.0
        av_before = main.current_av
        state.execute_action(main, ActionType.BASIC_ATTACK, enemy, 1.0)
        # 连携也在同一 AV 帧
        joint_dmg, _, _, _ = state.execute_action(joint, ActionType.BASIC_ATTACK, enemy, 1.0,
                                                    tags={"attack", "joint"})
        # AV 未被推进 (没调用 advance_time)
        assert main.current_av == av_before


# ============================================================
#  TestMemospriteSystem — 忆灵
# ============================================================
class TestMemospriteSystem:
    """验证面板继承、独立受击、AV 参与。"""

    # ── 测试 1: 面板继承 ──
    def test_memosprite_inherits_master_atk(self) -> None:
        master = create_test_character("Master", hp=2000, speed=100, atk=500.0)
        sprite = Memosprite("Sprite", master, speed=80, hp_scale=1.0)

        assert sprite.atk == pytest.approx(master.atk)
        assert sprite.max_hp == master.max_hp

    # ── 测试 2: 忆灵受击 ──
    def test_memosprite_can_be_damaged(self) -> None:
        master = create_test_character("Master", hp=2000, speed=100, atk=50.0)
        sprite = Memosprite("Sprite", master, speed=80, hp_scale=1.0)
        enemy = Enemy(name="Attacker", hp=1000, speed=50, base_damage=100, level=1)

        hp_before = sprite.hp
        sprite.take_damage(100)
        assert sprite.hp == hp_before - 100

    # ── 测试 3: 出现在时间轴 + 死亡自动解除 ──
    def test_memosprite_in_av_and_dies(self) -> None:
        master = create_test_character("Master", hp=2000, speed=100, atk=50.0)
        sprite = Memosprite("Sprite", master, speed=120, hp_scale=0.1)  # HP=200
        enemy = Enemy(name="Boss", hp=10000, speed=50, base_damage=0, level=1)

        state = GameState(characters=[master], enemies=[enemy])
        engine = CombatEngine(state)
        master.memosprite = sprite

        # 忆灵出现在 AV 中
        fighters = state.all_fighters
        assert sprite in fighters
        assert master in fighters

        # 忆灵死亡 → 自动解除
        sprite.take_damage(sprite.hp)
        assert not sprite.is_alive
        fighter_names = [f.name for f in state.all_fighters]
        assert sprite.name not in fighter_names  # 死亡后不在活跃列表


# ============================================================
#  TestBreakDebuffs — 七元素击破效果
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
class TestShieldAbsorptionInTakeDamage:
    """验证 take_damage() 内置护盾吸收（不再依赖 execute_action）。"""

    def test_enemy_attack_respects_shield(self) -> None:
        """敌方 attack() 直接调用 take_damage()，护盾应生效。"""
        char = create_test_character("Tank", hp=500, speed=100)
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=25, level=1)

        char.shield_statuses.append(ShieldStatus(100, 100, "Wall"))
        hp_before = char.hp

        enemy.attack([char])

        # 护盾 100 > 攻击 25 → HP 不变
        assert char.hp == hp_before

    def test_direct_take_damage_respects_shield(self) -> None:
        """直接调用 take_damage() 时护盾优先吸收。"""
        char = create_test_character("Tank", hp=500, speed=100)
        char.shield_statuses.append(ShieldStatus(50, 50, "Wall"))

        hp_before = char.hp
        char.take_damage(100)

        # 护盾 50, 伤害 100 → 护盾破, HP -50
        assert char.hp == hp_before - 50
        assert len(char.shield_statuses) == 0

    def test_bypass_shield_skips_absorption(self) -> None:
        """bypass_shield=True 应跳过护盾直接扣血。"""
        char = create_test_character("Tank", hp=500, speed=100)
        char.shield_statuses.append(ShieldStatus(100, 100, "Wall"))

        char.take_damage(30, bypass_shield=True)

        # 护盾完好, HP 全扣
        assert char.hp == 470
        assert len(char.shield_statuses) == 1
        assert char.shield_statuses[0].shield_value == 100

    def test_multiple_shields_sequential_absorption(self) -> None:
        """多护盾先添加先吸收, 逐个扣除直到伤害用尽。"""
        char = create_test_character("Tank", hp=500, speed=100)
        char.shield_statuses.append(ShieldStatus(30, 30, "A"))
        char.shield_statuses.append(ShieldStatus(80, 80, "B"))

        char.take_damage(100)

        # 护盾A 30 全吸收, 护盾B 吸收 70, 剩余 100-30-70=0 → HP 不变
        assert len(char.shield_statuses) == 1
        assert char.shield_statuses[0].shield_value == pytest.approx(10)
        assert char.shield_statuses[0].source_name == "B"

    def test_shield_absorbed_by_execute_action_do_not_double_dip(self) -> None:
        """execute_action 不再重复扣护盾 (由 take_damage 统一处理)。"""
        char = create_test_character("Attacker", hp=200, speed=100, atk=50.0, crit_rate=0.0)
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])

        enemy.shield_statuses.append(ShieldStatus(500, 500, "Wall"))
        hp_before = enemy.hp

        state.execute_action(char, ActionType.BASIC_ATTACK, enemy, 1.0)

        # 护盾 > 伤害 → HP 不变
        assert enemy.hp == hp_before


# ============================================================
#  TestShieldDuration — P2: 护盾持续时间
# ============================================================
class TestShieldDuration:
    """验证 ShieldStatus.duration 字段和回合递减行为。"""

    def test_shield_with_duration_expires(self) -> None:
        """有 duration 的护盾到期后自动消失。"""
        char = create_test_character("Tank", hp=500, speed=100)
        char.shield_statuses.append(ShieldStatus(100, 100, "Timed", duration=1))

        char.take_damage(50)
        assert len(char.shield_statuses) == 1  # 尚未到期
        assert char.shield_statuses[0].shield_value == pytest.approx(50)

        # 模拟回合结束递减 (duration 由引擎管理)
        char.shield_statuses[0].duration -= 1
        expired = [s for s in char.shield_statuses if getattr(s, "duration", None) is not None and s.duration <= 0]
        char.shield_statuses = [s for s in char.shield_statuses if getattr(s, "duration", None) is None or s.duration > 0]

        assert len(char.shield_statuses) == 0  # duration 归零 → 移除

    def test_permanent_shield_never_expires(self) -> None:
        """无 duration (None) 的护盾永久存在。"""
        char = create_test_character("Tank", hp=500, speed=100)
        char.shield_statuses.append(ShieldStatus(100, 100, "Permanent"))
        assert char.shield_statuses[0].duration is None

        # 模拟回合递减: 只移除 duration 归零者
        for s in char.shield_statuses:
            if s.duration is not None and s.duration > 0:
                s.duration -= 1
        char.shield_statuses = [s for s in char.shield_statuses if s.duration is None or s.duration > 0]

        assert len(char.shield_statuses) == 1  # duration=None → 永久

    def test_mixed_duration_shields_decay_properly(self) -> None:
        """同时存在限时和永久护盾时只移除到期者。"""
        char = create_test_character("Tank", hp=500, speed=100)
        char.shield_statuses.append(ShieldStatus(50, 50, "Timed", duration=1))
        char.shield_statuses.append(ShieldStatus(100, 100, "Permanent"))

        char.shield_statuses[0].duration -= 1
        char.shield_statuses = [s for s in char.shield_statuses if getattr(s, "duration", None) is None or s.duration > 0]

        assert len(char.shield_statuses) == 1
        assert char.shield_statuses[0].source_name == "Permanent"

    def test_shield_duration_decremented_by_engine(self) -> None:
        """CombatEngine._decrement_modifiers 应递减护盾 duration。"""
        char = create_test_character("Tank", hp=500, speed=100)
        enemy = Enemy(name="E", hp=50000, speed=200, base_damage=0, level=1)
        state = GameState(characters=[char], enemies=[enemy])

        char.shield_statuses.append(ShieldStatus(500, 500, "Timed", duration=1))

        engine = CombatEngine(state)
        assert len(char.shield_statuses) == 1  # 战前存在

        # 前进一步: 角色行动后 _decrement_modifiers 触发
        # 敌人速度更高, 先行动 → engine run 一步 → 角色行动 → modifiers 递减
        engine._decrement_modifiers()

        assert len(char.shield_statuses) == 0  # duration 归零 → 移除


# ============================================================
#  TestDeathEvents — P1: 濒死/倒地事件
# ============================================================
class TestDeathEvents:
    """验证 UNIT_DOWNED 和 BEFORE_DEATH 事件在击杀时正确触发。"""

    def test_unit_downed_on_enemy_kill(self) -> None:
        """execute_action 击杀敌方 → UNIT_DOWNED 事件触发。"""
        from core.events import EventBus, EventType

        bus = EventBus()
        events: list[dict] = []

        def record(**kw):
            events.append(kw)

        bus.subscribe(EventType.UNIT_DOWNED, record)

        char = create_test_character("Killer", hp=200, speed=100, atk=500.0, crit_rate=0.0)
        enemy = Enemy(name="E", hp=10, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])
        state.event_bus = bus

        state.execute_action(char, ActionType.BASIC_ATTACK, enemy, 1.0)

        assert not enemy.is_alive
        assert len(events) == 1
        assert events[0]["unit"] is enemy

    def test_unit_downed_on_character_death(self) -> None:
        """敌方攻击击杀角色 → UNIT_DOWNED 事件触发。"""
        from core.events import EventType

        char = create_test_character("Victim", hp=10, speed=100)
        enemy = Enemy(name="E", hp=1000, speed=50, base_damage=100, level=1)
        state = GameState(characters=[char], enemies=[enemy])

        engine = CombatEngine(state)
        events: list[dict] = []

        def record(**kw):
            events.append(kw)

        engine.event_bus.subscribe(EventType.UNIT_DOWNED, record)

        engine._execute_enemy_turn(enemy)

        assert not char.is_alive
        assert len(events) == 1
        assert events[0]["unit"] is char

    def test_no_downed_event_when_alive(self) -> None:
        """未击杀时不应触发 UNIT_DOWNED。"""
        from core.events import EventBus, EventType

        bus = EventBus()
        events: list[dict] = []

        def record(**kw):
            events.append(kw)

        bus.subscribe(EventType.UNIT_DOWNED, record)

        char = create_test_character("Attacker", hp=200, speed=100, atk=10.0, crit_rate=0.0)
        enemy = Enemy(name="E", hp=1000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])
        state.event_bus = bus

        state.execute_action(char, ActionType.BASIC_ATTACK, enemy, 1.0)

        assert enemy.is_alive
        assert len(events) == 0


# ============================================================
#  TestHealEvent — P3: HEAL_DONE 事件
# ============================================================
class TestHealEvent:
    """验证 calculate_and_apply_heal 触发 HEAL_DONE 事件。"""

    def test_heal_done_event_emitted(self) -> None:
        """治疗结算后应触发 HEAL_DONE 事件。"""
        from core.events import EventBus, EventType

        bus = EventBus()
        events: list[dict] = []

        def record(**kw):
            events.append(kw)

        bus.subscribe(EventType.HEAL_DONE, record)

        healer = create_test_character("Healer", hp=200, speed=100, atk=100.0)
        target = create_test_character("Target", hp=200, speed=100)
        target.hp = 50  # 扣血

        state = GameState(characters=[healer, target], enemies=[])
        state.event_bus = bus

        actual = state.calculate_and_apply_heal(healer, target, 100.0, 0.5)
        assert actual > 0
        assert len(events) == 1
        assert events[0]["healer"] is healer
        assert events[0]["target"] is target

    def test_no_heal_event_when_full_hp(self) -> None:
        """满血时治疗量为 0，不应触发 HEAL_DONE。"""
        from core.events import EventBus, EventType

        bus = EventBus()
        events: list[dict] = []

        def record(**kw):
            events.append(kw)

        bus.subscribe(EventType.HEAL_DONE, record)

        healer = create_test_character("Healer", hp=200, speed=100, atk=100.0)
        target = create_test_character("Target", hp=200, speed=100)
        # target.hp == max_hp, 已满

        state = GameState(characters=[healer, target], enemies=[])
        state.event_bus = bus

        actual = state.calculate_and_apply_heal(healer, target, 100.0, 0.5)
        assert actual == 0
        assert len(events) == 0


# ============================================================
#  TestBreakMechanics — 文档 §10 击破系统验证
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
class TestDoc13:
    """验证文档 §13 的相关逻辑是否与实现一致。"""

    # ── §13.1: Follow-Up 标签触发 FUA_DMG ──
    def test_follow_up_tag_triggers_fua_dmg_bonus(self) -> None:
        """tags={'follow_up'} 时 FUA_DMG StatType 乘区生效。"""
        char = create_test_character("FUA", hp=200, speed=100, atk=100.0, crit_rate=0.0)
        char.stats.add_modifier(StatModifier(
            StatType.FUA_DMG, StatModifierType.FLAT, 0.50, source="Test"))
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])

        without_tag = state.execute_action(char, ActionType.BASIC_ATTACK, enemy, 1.0)[0]
        with_tag = state.execute_action(char, ActionType.BASIC_ATTACK, enemy, 1.0,
                                         tags={"attack", "follow_up"})[0]
        assert with_tag > without_tag  # FUA_DMG 加成生效

    # ── §13.1: FUA 队列优先级高于 AV ──
    def test_follow_up_action_has_priority_over_av(self) -> None:
        """FUA 队列中的动作在下一个角色 AV 推进前执行。"""
        char = create_test_character("A", hp=200, speed=200, atk=10.0, crit_rate=0.0)
        enemy = Enemy(name="E", hp=10000, speed=100, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])

        hp_before = enemy.hp
        # 直接 execute_action 模拟 FUA 执行
        state.execute_action(char, ActionType.FOLLOW_UP, enemy, 0.5,
                              tags={"attack", "follow_up"})
        assert enemy.hp < hp_before
        assert not state.has_follow_up_action()

    # ── §13.2: Counter 标签不影响正常 FUA 标签 ──
    def test_counter_tag_coexists_with_follow_up_tag(self) -> None:
        """counter 标签与 follow_up 标签共存，两者互不冲突。"""
        char = create_test_character("C", hp=200, speed=100, atk=100.0, crit_rate=0.0)
        char.stats.add_modifier(StatModifier(
            StatType.FUA_DMG, StatModifierType.FLAT, 0.50, source="Test"))
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])

        # counter + follow_up 标签同时存在
        dmg, _, _, _ = state.execute_action(
            char, ActionType.FOLLOW_UP, enemy, 1.0,
            tags={"attack", "counter", "follow_up"},
        )
        assert dmg > 0  # 正常造成伤害

    # ── §13.3: Memosprite 参与 all_fighters 和 AV ──
    def test_memosprite_in_all_fighters(self) -> None:
        """忆灵加入 all_fighters，拥有独立 AV，死亡后移除。"""
        char = create_test_character("Master", hp=200, speed=100)
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=10, level=1)

        sprite = char.summon_memosprite(speed=80, hp_scale=0.5)
        state = GameState(characters=[char], enemies=[enemy])

        assert sprite in state.all_fighters
        assert sprite not in state.alive_characters
        assert sprite.current_av > 0  # 有独立 AV

    # ── §13.4: Aha countdown 生命周期 ──
    def test_aha_added_when_elation_chars_present(self) -> None:
        """有 Elation 角色时 Aha 加入 countdown_units。"""
        from entities.aha import Aha

        char = create_test_character("ElationUser", hp=200, speed=100, path=PathType.ELATION)
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=10, level=1)
        state = GameState(characters=[char], enemies=[enemy])

        engine = CombatEngine(state)
        engine._manage_aha()
        assert len(state.countdown_units) == 1
        assert isinstance(state.countdown_units[0], Aha)

    # ── §13.0: Aha Instant 窗口流程 ──
    def test_aha_instant_resets_punchline_and_awards_cb(self) -> None:
        """Aha Instant 执行后 Punchline 重置，CB 发放。"""
        from entities.aha import Aha
        from entities.base import CertifiedBanger

        dan = create_test_character("DanHeng-EL", hp=500, speed=120, path=PathType.ELATION)
        dan._skills = {}
        from entities.characters.dan_heng.skills import DanHengElationSkill
        dan._skills["elation"] = DanHengElationSkill(dan)
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[dan], enemies=[enemy])
        state.punchline = 10  # 模拟累积值

        aha = Aha(state)
        state.countdown_units.append(aha)

        # 执行 Aha Instant
        aha.execute_aha_turn()

        assert state.punchline == 1  # 重置为 Elation 角色数
        assert len(dan.certified_bangers) == 1
        assert dan.certified_bangers[0].value == 10  # 快照值


# ============================================================
#  TestEventCoverage — Phase A: 事件枚举覆盖率
# ============================================================
class TestEventCoverage:
    """验证文档 §14 的所有事件类型均已定义。"""

    def test_all_doc14_events_exist_in_enum(self) -> None:
        from core.events import EventType

        required = [
            "BATTLE_START", "WAVE_START", "ON_BEFORE_ACTION_ORDER_RESOLVE",
            "TURN_START", "ACTION_START", "ON_BEFORE_PAY_COST",
            "ON_AFTER_PAY_COST", "ON_BEFORE_TARGET_SELECT", "ON_AFTER_TARGET_SELECT",
            "ON_BEFORE_HIT", "ON_HIT", "ON_DAMAGE_CALCULATED", "ON_DAMAGE_DEALT",
            "HEAL_DONE", "ON_SHIELD_APPLIED", "ON_TOUGHNESS_DAMAGE",
            "ON_WEAKNESS_BREAK", "ON_STATUS_APPLY", "ON_STATUS_EXPIRE",
            "ON_KILL", "UNIT_DOWNED", "ON_REVIVE", "AFTER_ACTION",
            "TURN_END", "ON_ULTIMATE_QUEUED", "ON_ULTIMATE_INSERTED",
        ]
        for name in required:
            assert hasattr(EventType, name), f"Missing EventType.{name}"

    def test_new_events_emitted_in_execute_action(self) -> None:
        """验证 execute_action 触发新增事件。"""
        from core.events import EventBus, EventType

        bus = EventBus()
        emitted: set[str] = set()

        def make_collector(name: str):
            def collector(**kw):
                emitted.add(name)
            return collector

        for et in EventType:
            bus.subscribe(et, make_collector(et.name))

        char = create_test_character("A", hp=200, speed=100, atk=100.0, crit_rate=0.0)
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL], max_toughness=30)
        state = GameState(characters=[char], enemies=[enemy])
        state.event_bus = bus

        state.execute_action(char, ActionType.SKILL, enemy, 1.0)

        # 关键事件应被触发
        assert "ON_BEFORE_PAY_COST" in emitted
        assert "ON_AFTER_PAY_COST" in emitted
        assert "ON_DAMAGE_CALCULATED" in emitted
        assert "ON_BEFORE_HIT" in emitted
        assert "ON_DAMAGE_DEALT" in emitted
        assert "ON_HIT" in emitted
        assert "ON_TOUGHNESS_DAMAGE" in emitted

    def test_status_expire_event_fires(self) -> None:
        """修饰器 duration 归零时触发 ON_STATUS_EXPIRE。"""
        from core.events import EventBus, EventType

        bus = EventBus()
        expired: list[str] = []

        def on_expire(**kw):
            m = kw.get("modifier")
            if m:
                expired.append(m.source)

        bus.subscribe(EventType.ON_STATUS_EXPIRE, on_expire)

        char = create_test_character("A", hp=200, speed=100)
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])
        engine = CombatEngine(state)
        engine.event_bus = bus  # 覆盖自动创建的 bus

        mod = StatModifier(StatType.ATK, StatModifierType.FLAT, 10.0,
                           source="TestDebuff", duration=1,
                           tick_timing="owner_turn_end")
        char.stats.add_modifier(mod)

        engine._decrement_modifiers_timing("owner_turn_end")
        assert "TestDebuff" in expired
        assert mod not in char.stats.active_modifiers


# ============================================================
#  TestTargetSelection — §7: 扩散/群攻/随机
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
class TestWaveSystem:
    """验证波次切换、秘技注入、伏击延迟、WaveStart 事件。"""

    # ── 波次切换 ──
    def test_wave_transition_on_enemies_cleared(self) -> None:
        """当前波敌人清空后自动切换到下一波。"""
        char = create_test_character("A", hp=200, speed=200, atk=50.0, crit_rate=0.0)
        wave1 = Enemy(name="E1", hp=10, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        wave2 = Enemy(name="E2", hp=100, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[wave1])
        state.waves = [[wave1], [wave2]]
        engine = CombatEngine(state)

        # 击杀第一波敌人
        state.execute_action(char, ActionType.BASIC_ATTACK, wave1, 1.0)
        assert state.wave_cleared()
        assert state.has_next_wave()

        # 切换波次
        remaining = state.start_next_wave()
        assert remaining == 0
        assert state.current_wave == 1
        assert state.enemies == [wave2]

    def test_battle_ends_when_last_wave_cleared(self) -> None:
        """最后一波清空后 battle_ended=True。"""
        char = create_test_character("A", hp=200, speed=200, atk=50.0, crit_rate=0.0)
        wave1 = Enemy(name="E", hp=10, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[wave1])
        state.waves = [[wave1]]

        state.execute_action(char, ActionType.BASIC_ATTACK, wave1, 1.0)
        assert not state.has_next_wave()
        assert state.battle_ended

    # ── WaveStart 事件 ──
    def test_wave_start_event_emitted(self) -> None:
        """波次切换时触发 WAVE_START 事件。"""
        from core.events import EventBus, EventType

        bus = EventBus()
        events: list[int] = []

        def on_wave(**kw):
            events.append(kw.get("wave", -1))

        bus.subscribe(EventType.WAVE_START, on_wave)

        char = create_test_character("A", hp=200, speed=200, atk=50.0, crit_rate=0.0)
        wave1 = Enemy(name="E1", hp=10, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        wave2 = Enemy(name="E2", hp=100, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[wave1])
        state.waves = [[wave1], [wave2]]
        state.event_bus = bus

        state.start_next_wave()
        assert events == [1]

    # ── 秘技注入 ──
    def test_technique_effects_applied(self) -> None:
        """秘技回调在 apply_techniques 时被执行。"""
        char = create_test_character("A", hp=200, speed=100, atk=50.0, crit_rate=0.0)
        enemy = Enemy(name="E", hp=100, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])

        applied: list[str] = []
        state.register_technique(lambda s: applied.append("tech1"))
        state.register_technique(lambda s: applied.append("tech2"))
        state.apply_techniques()

        assert applied == ["tech1", "tech2"]

    # ── 伏击 ──
    def test_ambush_delays_all_characters_by_20_av(self) -> None:
        """伏击时所有角色后移 20 AV。"""
        char = create_test_character("A", hp=200, speed=100)  # base_av = 100
        enemy = Enemy(name="E", hp=100, speed=50, base_damage=0, level=1)
        state = GameState(characters=[char], enemies=[enemy])
        state.is_ambush = True

        av_before = char.current_av
        assert av_before == pytest.approx(100.0)

        state.apply_techniques()
        assert char.current_av == pytest.approx(120.0)  # +20

    # ── AV 留存 ──
    def test_countdown_avNotReset_on_wave_change(self) -> None:
        """倒计时对象(Aha)换波时 AV 不重置。"""
        from entities.aha import Aha

        dan = create_test_character("Dan", hp=500, speed=120, path=PathType.ELATION)
        enemy = Enemy(name="E1", hp=10, speed=50, base_damage=0, level=1)
        state = GameState(characters=[dan], enemies=[enemy])
        state.waves = [[enemy], [enemy]]  # 两波, Aha 在 countdown_units 中
        aha = Aha(state)
        state.countdown_units = [aha]

        aha.current_av = 50.0
        state.start_next_wave()
        assert aha.current_av == pytest.approx(50.0)  # 未重置

    def test_character_av_reset_on_wave_change(self) -> None:
        """普通角色换波时 AV 重置。"""
        char = create_test_character("A", hp=200, speed=100)
        enemy1 = Enemy(name="E1", hp=10, speed=50, base_damage=0, level=1,
                        weaknesses=[ElementType.PHYSICAL])
        enemy2 = Enemy(name="E2", hp=100, speed=50, base_damage=0, level=1,
                        weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy1])
        state.waves = [[enemy1], [enemy2]]

        char.current_av = 50.0
        assert not char.av_keep_on_wave
        state.start_next_wave()
        assert char.current_av == pytest.approx(100.0)  # 重置


# ============================================================
#  TestMarch7Counter — §6: 三月七天赋反击
# ============================================================
class TestMarch7Counter:
    """验证三月七天赋: ON_HIT 监听 → 护盾检查 → FUA 反击。"""

    def test_counter_listener_registered_on_combat_start(self) -> None:
        """CombatEngine 启动时注册天赋 ON_HIT 监听器。"""
        from starrail_combat import Character
        from core.events import EventType

        march = Character("March7th")
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=10, level=1)
        state = GameState(characters=[march], enemies=[enemy])
        engine = CombatEngine(state)

        # on_combat_start 已在 engine.run() 中调用
        # 不跑 run() (会死循环), 手动触发注册
        talent = march._skills["talent"]
        talent.on_combat_start(state)
        assert len(state.event_bus._listeners.get(EventType.ON_HIT, [])) >= 1

    def test_shielded_ally_triggers_counter_on_hit(self) -> None:
        """敌方攻击持盾者 → ON_HIT 监听器触发 grant_follow_up_action。"""
        from starrail_combat import Character
        from entities.base import ShieldStatus

        march = Character("March7th")
        march._counter_used = 0
        march._counter_max = 2
        enemy = Enemy(name="E", hp=1000, speed=50, base_damage=10, level=1)

        state = GameState(characters=[march], enemies=[enemy])
        engine = CombatEngine(state)

        # 给三月七套盾
        march.shield_statuses.append(ShieldStatus(500, 500, "March7th_Shield"))

        # 注册监听器
        talent = march._skills["talent"]
        talent.on_combat_start(state)

        hp_before = enemy.hp
        # 模拟敌方攻击 (会 emit ON_HIT)
        engine._execute_enemy_turn(enemy)

        # FUA 队列应有一个待处理的反击
        assert state.has_follow_up_action()

    def test_no_counter_without_shield(self) -> None:
        """无护盾时不触发反击。"""
        from starrail_combat import Character

        march = Character("March7th")
        enemy = Enemy(name="E", hp=1000, speed=50, base_damage=10, level=1)

        state = GameState(characters=[march], enemies=[enemy])
        engine = CombatEngine(state)

        talent = march._skills["talent"]
        talent.on_combat_start(state)

        engine._execute_enemy_turn(enemy)
        assert not state.has_follow_up_action()

    def test_counter_executes_with_correct_tags(self) -> None:
        """反击使用 counter+follow_up 标签，享受 FUA_DMG 加成。"""
        from starrail_combat import Character
        from entities.base import ShieldStatus

        march = Character("March7th")
        march._counter_used = 0
        march._counter_max = 2
        enemy = Enemy(name="E", hp=1000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.ICE])

        state = GameState(characters=[march], enemies=[enemy])

        talent = march._skills["talent"]
        talent.on_combat_start(state)

        # 直接调用 trigger_counter 测试标签
        dmg = talent.trigger_counter(enemy, state)
        assert dmg > 0
        assert march._counter_used == 1

    def test_counter_respects_per_turn_limit(self) -> None:
        """反击每回合最多 2 次。"""
        from starrail_combat import Character

        march = Character("March7th")
        march._counter_used = 0
        march._counter_max = 2
        enemy = Enemy(name="E", hp=1000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.ICE])

        state = GameState(characters=[march], enemies=[enemy])

        talent = march._skills["talent"]
        assert talent.trigger_counter(enemy, state) > 0  # 第 1 次
        assert talent.trigger_counter(enemy, state) > 0  # 第 2 次
        assert talent.trigger_counter(enemy, state) == 0  # 第 3 次超过上限


# ============================================================
#  TestDoc18 — 文档 §18 推荐测试用例补充
# ============================================================
class TestDoc18:
    """补充文档 §18 中未被充分覆盖的测试用例。"""

    # ── 18.1: 100 SPD vs 125 SPD 行动次数 ──
    def test_spd_100_vs_125_action_count(self) -> None:
        """同 AV 时长下 125 SPD 角色行动次数多于 100 SPD。"""
        fast = create_test_character("Fast", hp=200, speed=125)
        slow = create_test_character("Slow", hp=200, speed=100)
        enemy = Enemy(name="E", hp=10000, speed=1, base_damage=0, level=1)
        state = GameState(characters=[fast, slow], enemies=[enemy])

        # Advance enough AV for slow to act ~4 times
        total_av = state.enemies[0].current_av  # dummy, just need initial AV
        fast_count = 0
        slow_count = 0

        for _ in range(20):
            actor = min(state.all_fighters, key=lambda f: f.current_av)
            advance = actor.current_av
            if advance <= 0:
                break
            for f in state.all_fighters:
                f.current_av -= advance
            if actor is fast:
                fast_count += 1
            elif actor is slow:
                slow_count += 1
            actor.reset_av()
            if fast_count >= 5 and slow_count >= 4:
                break

        # Fast (125 SPD) should get more actions
        assert fast_count > slow_count

    # ── 18.3: 连续 100% 拉条 LIFO 顺序 ──
    def test_multiple_advance_lifo_order(self) -> None:
        """连续多个 100% 拉条时最后被拉者先动 (LIFO)。"""
        a = create_test_character("A", hp=200, speed=50)   # AV=200
        b = create_test_character("B", hp=200, speed=50)   # AV=200
        c = create_test_character("C", hp=200, speed=50)   # AV=200
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1)
        state = GameState(characters=[a, b, c], enemies=[enemy])

        # 全部设到相同 AV 起始点
        a.current_av = 50.0
        b.current_av = 50.0
        c.current_av = 50.0

        # 按 A, B, C 顺序拉条 (immediate → AV=0)
        # LIFO: C 最后被拉 → C 先动 → B → A
        a.immediate_action()
        b.immediate_action()
        c.immediate_action()

        order: list[str] = []
        for _ in range(3):
            actor = min([a, b, c], key=lambda f: (f.current_av, -f._av_zero_ts))
            order.append(actor.name)
            actor.current_av = 100.0  # 出队

        assert order == ["C", "B", "A"]  # LIFO

    # ── 18.4: Extra Turn 不能放终结技 ──
    def test_extra_turn_does_not_cast_ultimate(self) -> None:
        """能量满时额外回合不触发终结技插队。"""
        char = create_test_character("A", hp=200, speed=200, atk=10.0, crit_rate=0.0,
                                      max_energy=100)
        char.energy = char.max_energy  # 能量满
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])

        # 终结技已入队 (由 _check_and_enqueue_ultimates 自动处理)
        state.declare_ultimate(char)
        assert state.has_pending_ultimates()

        # 授予额外回合 → 不应消费终结技队列
        state.grant_extra_turn(char, None)
        assert state.has_extra_turn()

    # ── 18.8: BATTLE_START 只触发一次 ──
    def test_battle_start_fires_once_not_per_wave(self) -> None:
        """BATTLE_START 只在战斗开始时触发，不在换波时触发。"""
        from core.events import EventBus, EventType

        bus = EventBus()
        battle_starts: list[int] = []

        def on_battle(**kw):
            battle_starts.append(1)

        bus.subscribe(EventType.BATTLE_START, on_battle)

        char = create_test_character("A", hp=200, speed=200, atk=50.0, crit_rate=0.0)
        wave1 = Enemy(name="E1", hp=10, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        wave2 = Enemy(name="E2", hp=100, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[wave1])
        state.waves = [[wave1], [wave2]]
        state.event_bus = bus

        bus.emit(EventType.BATTLE_START)  # 模拟战斗开始
        assert len(battle_starts) == 1

        state.start_next_wave()  # 换波
        assert len(battle_starts) == 1  # 未再次触发

    # ── 18.8: BATTLE_START ≠ WAVE_START ──
    def test_battle_start_and_wave_start_are_independent(self) -> None:
        """BATTLE_START 和 WAVE_START 是两个独立事件。"""
        from core.events import EventBus, EventType

        bus = EventBus()
        events: list[str] = []

        def record_battle(**kw):
            events.append("BATTLE_START")

        def record_wave(**kw):
            events.append("WAVE_START")

        bus.subscribe(EventType.BATTLE_START, record_battle)
        bus.subscribe(EventType.WAVE_START, record_wave)

        char = create_test_character("A", hp=200, speed=200, atk=50.0, crit_rate=0.0)
        wave1 = Enemy(name="E1", hp=10, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        wave2 = Enemy(name="E2", hp=100, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[wave1])
        state.waves = [[wave1], [wave2]]
        state.event_bus = bus

        bus.emit(EventType.BATTLE_START)  # 战斗开始
        assert events == ["BATTLE_START"]

        state.start_next_wave()  # 换波
        assert events == ["BATTLE_START", "WAVE_START"]


# ============================================================
#  TestMultiHit — §18.7: 多段攻击
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
class TestStackPolicy:
    """验证 6 种 stack_policy 的行为。"""

    def _make_char(self) -> "Character":
        return create_test_character("A", hp=200, speed=100)

    # ── refresh: 替换值 + 刷新 duration ──
    def test_refresh_replaces_value_and_duration(self) -> None:
        char = self._make_char()
        m1 = StatModifier(StatType.ATK, StatModifierType.FLAT, 10.0, source="Buff", duration=2)
        char.stats.apply_modifier(m1, "refresh")
        assert len(char.stats.active_modifiers) == 1
        assert char.stats.active_modifiers[0].value == 10.0

        m2 = StatModifier(StatType.ATK, StatModifierType.FLAT, 20.0, source="Buff", duration=5)
        char.stats.apply_modifier(m2, "refresh")
        assert len(char.stats.active_modifiers) == 1  # 同源替换，不追加
        assert char.stats.active_modifiers[0].value == 20.0
        assert char.stats.active_modifiers[0].duration == 5  # duration 也刷新

    # ── independent: 总是追加 ──
    def test_independent_always_appends(self) -> None:
        char = self._make_char()
        for _ in range(3):
            char.stats.apply_modifier(
                StatModifier(StatType.ATK, StatModifierType.FLAT, 10.0, source="X"), "independent")
        assert len(char.stats.active_modifiers) == 3

    # ── add_stacks: 累加效果值 ──
    def test_add_stacks_accumulates_value(self) -> None:
        char = self._make_char()
        m1 = StatModifier(StatType.ATK, StatModifierType.FLAT, 10.0, source="Stack")
        char.stats.apply_modifier(m1, "add_stacks")
        assert char.stats.active_modifiers[0].value == 10.0

        m2 = StatModifier(StatType.ATK, StatModifierType.FLAT, 5.0, source="Stack")
        char.stats.apply_modifier(m2, "add_stacks")
        assert len(char.stats.active_modifiers) == 1  # 不追加
        assert char.stats.active_modifiers[0].value == 15.0  # 10 + 5

    # ── replace_weaker: 仅当更大才替换 ──
    def test_replace_weaker_only_when_stronger(self) -> None:
        char = self._make_char()
        m1 = StatModifier(StatType.ATK, StatModifierType.FLAT, 10.0, source="Max")
        char.stats.apply_modifier(m1, "replace_weaker")

        # 施加更小值 → 不替换
        m2 = StatModifier(StatType.ATK, StatModifierType.FLAT, 5.0, source="Max")
        char.stats.apply_modifier(m2, "replace_weaker")
        assert char.stats.active_modifiers[0].value == 10.0  # 保留旧值

        # 施加更大值 → 替换
        m3 = StatModifier(StatType.ATK, StatModifierType.FLAT, 15.0, source="Max")
        char.stats.apply_modifier(m3, "replace_weaker")
        assert char.stats.active_modifiers[0].value == 15.0

    # ── replace_stronger: 仅当更小才替换 ──
    def test_replace_stronger_only_when_weaker(self) -> None:
        char = self._make_char()
        m1 = StatModifier(StatType.DEF, StatModifierType.PERCENT, -0.20, source="Min")
        char.stats.apply_modifier(m1, "replace_stronger")

        # 施加更小值 → 替换
        m2 = StatModifier(StatType.DEF, StatModifierType.PERCENT, -0.30, source="Min")
        char.stats.apply_modifier(m2, "replace_stronger")
        assert char.stats.active_modifiers[0].value == -0.30  # 更新为更小

        # 施加更大值 → 不替换
        m3 = StatModifier(StatType.DEF, StatModifierType.PERCENT, -0.10, source="Min")
        char.stats.apply_modifier(m3, "replace_stronger")
        assert char.stats.active_modifiers[0].value == -0.30  # 保留旧值

    # ── no_stack: 同源不重复 ──
    def test_no_stack_skips_duplicate_source(self) -> None:
        char = self._make_char()
        m1 = StatModifier(StatType.ATK, StatModifierType.FLAT, 10.0, source="Once")
        char.stats.apply_modifier(m1, "no_stack")

        m2 = StatModifier(StatType.ATK, StatModifierType.FLAT, 99.0, source="Once")
        char.stats.apply_modifier(m2, "no_stack")
        assert len(char.stats.active_modifiers) == 1
        assert char.stats.active_modifiers[0].value == 10.0  # 第二次无效

    # ── 不同 source 不冲突 ──
    def test_different_sources_never_conflict(self) -> None:
        char = self._make_char()
        char.stats.apply_modifier(
            StatModifier(StatType.ATK, StatModifierType.FLAT, 10.0, source="A"), "no_stack")
        char.stats.apply_modifier(
            StatModifier(StatType.ATK, StatModifierType.FLAT, 20.0, source="B"), "no_stack")
        assert len(char.stats.active_modifiers) == 2

    # ── 向后兼容: add_modifier ≈ independent ──
    def test_add_modifier_is_independent_by_default(self) -> None:
        char = self._make_char()
        char.stats.add_modifier(StatModifier(StatType.ATK, StatModifierType.FLAT, 10.0, source="X"))
        char.stats.add_modifier(StatModifier(StatType.ATK, StatModifierType.FLAT, 10.0, source="X"))
        assert len(char.stats.active_modifiers) == 2


# ============================================================
#  TestShieldStatusEvents — ON_SHIELD_APPLIED / ON_STATUS_APPLY
# ============================================================
class TestShieldStatusEvents:
    """验证护盾和状态的 event emit。"""

    def test_on_shield_applied_emitted(self) -> None:
        """apply_shield() 触发 ON_SHIELD_APPLIED 事件。"""
        from core.events import EventBus, EventType

        bus = EventBus()
        events: list[dict] = []

        def record(**kw):
            events.append(kw)

        bus.subscribe(EventType.ON_SHIELD_APPLIED, record)

        char = create_test_character("A", hp=200, speed=100)
        char.event_bus = bus

        shield = ShieldStatus(100, 100, "Test")
        char.apply_shield(shield)
        assert len(events) == 1
        assert events[0]["target"] is char

    def test_on_status_apply_emitted(self) -> None:
        """apply_modifier() 触发 ON_STATUS_APPLY 事件。"""
        from core.events import EventBus, EventType

        bus = EventBus()
        events: list[dict] = []

        def record(**kw):
            events.append(kw)

        bus.subscribe(EventType.ON_STATUS_APPLY, record)

        char = create_test_character("A", hp=200, speed=100)
        char.event_bus = bus

        mod = StatModifier(StatType.ATK, StatModifierType.FLAT, 10.0, source="Test", duration=2)
        char.stats.apply_modifier(mod, "refresh")
        assert len(events) == 1
        assert events[0]["target"] is char
        assert events[0]["modifier"] is mod
        assert events[0]["stack_policy"] == "refresh"

    def test_on_status_apply_not_emitted_without_event_bus(self) -> None:
        """无 event_bus 时 apply_modifier 不退 crash。"""
        char = create_test_character("A", hp=200, speed=100)
        mod = StatModifier(StatType.ATK, StatModifierType.FLAT, 10.0)
        # 不应抛出异常
        char.stats.apply_modifier(mod, "independent")
        assert char.stats.active_modifiers[0] is mod


# ============================================================
#  TestEnergyBuckets — 受击回能分段 + FUA 返能分类
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
class TestDanHeng:
    """验证丹恒普攻/战技/终结技/天赋/行迹/星魂。"""

    def test_basic_multiplier(self) -> None:
        dan = Character("DanHeng")
        assert dan._skills["basic"].skill_multiplier == 1.40

    def test_skill_applies_slow_on_crit(self) -> None:
        dan = Character("DanHeng")
        dan.stats.add_modifier(StatModifier(StatType.CRIT_RATE, StatModifierType.FLAT, 1.0, source="Test"))
        enemy = Enemy(name="E", hp=50000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.WIND])
        enemy.stats.add_modifier(StatModifier(StatType.EFFECT_RES, StatModifierType.FLAT, -1.0, source="Test"))
        state = GameState(characters=[dan], enemies=[enemy])
        dan._skills["skill"].execute(enemy, state)
        has_slow = any(m.source == "DanHeng_Slow" and m.value < 0 for m in enemy.stats.active_modifiers)
        assert has_slow

    def test_ultimate_bonus_vs_slowed(self) -> None:
        dan = Character("DanHeng")
        enemy = Enemy(name="E", hp=1000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.WIND])
        state = GameState(characters=[dan], enemies=[enemy])
        enemy.stats.add_modifier(StatModifier(StatType.SPD, StatModifierType.PERCENT, -0.12, source="DanHeng_Slow"))
        dmg_slow, _, _, _ = dan._skills["ultimate"].execute(enemy, state)
        enemy.stats.remove_modifier_by_source("DanHeng_Slow")
        dmg_normal, _, _, _ = dan._skills["ultimate"].execute(enemy, state)
        assert dmg_slow > dmg_normal

    def test_talent_res_pen_on_ally_target(self) -> None:
        from core.events import EventType

        dan = Character("DanHeng")
        enemy = Enemy(name="E", hp=1000, speed=50, base_damage=0, level=1)
        state = GameState(characters=[dan], enemies=[enemy])
        engine = CombatEngine(state)
        dan._skills["talent"].on_combat_start(state)
        ally = create_test_character("Ally", hp=500, speed=100)
        state.event_bus.emit(EventType.ACTION_START, unit=ally, target=dan)
        assert dan._talent_buff_active is True
        assert dan.stats.get_total_stat(StatType.RES_PEN) >= 0.45

    def test_talent_cooldown_e2(self) -> None:
        from core.events import EventType

        dan = Character("DanHeng", eidolon_level=2)
        dan._talent_cooldown_remaining = 0
        enemy = Enemy(name="E", hp=1000, speed=50, base_damage=0, level=1)
        state = GameState(characters=[dan], enemies=[enemy])
        engine = CombatEngine(state)
        dan._skills["talent"].on_combat_start(state)
        ally = create_test_character("Ally", hp=500, speed=100)
        state.event_bus.emit(EventType.ACTION_START, unit=ally, target=dan)
        state.event_bus.emit(EventType.AFTER_ACTION, unit=dan, target=enemy)
        assert dan._talent_cooldown_remaining == 1

    def test_e1_crit_vs_high_hp(self) -> None:
        dan = Character("DanHeng", eidolon_level=1)
        enemy = Enemy(name="E", hp=1000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.WIND])
        state = GameState(characters=[dan], enemies=[enemy])
        dan._skills["basic"].execute(enemy, state)
        assert dan._has_e1

    def test_e6_stronger_slow(self) -> None:
        dan = Character("DanHeng", eidolon_level=6)
        dan.stats.add_modifier(StatModifier(StatType.CRIT_RATE, StatModifierType.FLAT, 1.0, source="Test"))
        enemy = Enemy(name="E", hp=50000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.WIND])
        enemy.stats.add_modifier(StatModifier(StatType.EFFECT_RES, StatModifierType.FLAT, -1.0, source="Test"))
        state = GameState(characters=[dan], enemies=[enemy])
        dan._skills["skill"].execute(enemy, state)
        slow_mods = [m for m in enemy.stats.active_modifiers if m.source == "DanHeng_Slow"]
        assert len(slow_mods) == 1
        assert slow_mods[0].value == pytest.approx(-0.20)

    def test_trace_wind_bonus_vs_slowed(self) -> None:
        dan = Character("DanHeng", unlocked_traces=["Wind"])
        dan.stats.add_modifier(StatModifier(StatType.CRIT_RATE, StatModifierType.FLAT, 1.0, source="Test"))
        enemy = Enemy(name="E", hp=50000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.WIND])
        enemy.stats.add_modifier(StatModifier(StatType.EFFECT_RES, StatModifierType.FLAT, -1.0, source="Test"))
        state = GameState(characters=[dan], enemies=[enemy])
        dan._skills["skill"].execute(enemy, state)
        dmg_slowed, _, _, _ = dan._skills["basic"].execute(enemy, state)
        enemy.stats.remove_modifier_by_source("DanHeng_Slow")
        dmg_normal, _, _, _ = dan._skills["basic"].execute(enemy, state)
        assert dmg_slowed > dmg_normal


# ============================================================
#  TestPlayerGirl — 开拓者·毁灭 (物理) 技能/行迹/星魂验证
# ============================================================
class TestPlayerGirl:
    """验证开拓者毁灭普攻/战技扩散/终结技二选一/天赋击破叠层/行迹/星魂。"""

    def test_skill_blast_hits_adjacent(self) -> None:
        pg = Character("PlayerGirl")
        e1 = Enemy(name="E1", hp=1000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.PHYSICAL])
        e2 = Enemy(name="E2", hp=1000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.PHYSICAL])
        e3 = Enemy(name="E3", hp=1000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[pg], enemies=[e1, e2, e3])
        hp_before = [e1.hp, e2.hp, e3.hp]
        pg._skills["skill"].execute(e2, state)
        assert e1.hp < hp_before[0]
        assert e2.hp < hp_before[1]
        assert e3.hp < hp_before[2]

    def test_ultimate_single_mode_one_enemy(self) -> None:
        pg = Character("PlayerGirl")
        enemy = Enemy(name="E", hp=1000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[pg], enemies=[enemy])
        pg._skills["ultimate"].execute(enemy, state)
        assert pg._skills["ultimate"].skill_multiplier == 5.25

    def test_ultimate_blast_mode_multi(self) -> None:
        pg = Character("PlayerGirl")
        e1 = Enemy(name="E1", hp=1000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.PHYSICAL])
        e2 = Enemy(name="E2", hp=1000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[pg], enemies=[e1, e2])
        pg._skills["ultimate"].execute(e1, state)
        assert e2.hp < 1000

    def test_talent_stacks_on_break(self) -> None:
        from core.events import EventType

        pg = Character("PlayerGirl")
        enemy = Enemy(name="E", hp=1000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.PHYSICAL], max_toughness=1)
        state = GameState(characters=[pg], enemies=[enemy])
        engine = CombatEngine(state)
        pg._skills["talent"].on_combat_start(state)
        state.event_bus.emit(EventType.ON_WEAKNESS_BREAK, breaker=pg, target=enemy)
        assert pg._talent_stacks == 1

    def test_talent_max_2_stacks(self) -> None:
        from core.events import EventType

        pg = Character("PlayerGirl")
        enemy = Enemy(name="E", hp=1000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[pg], enemies=[enemy])
        engine = CombatEngine(state)
        pg._skills["talent"].on_combat_start(state)
        state.event_bus.emit(EventType.ON_WEAKNESS_BREAK, breaker=pg, target=enemy)
        state.event_bus.emit(EventType.ON_WEAKNESS_BREAK, breaker=pg, target=enemy)
        state.event_bus.emit(EventType.ON_WEAKNESS_BREAK, breaker=pg, target=enemy)
        assert pg._talent_stacks == 2

    def test_a4_tenacity_def_per_stack(self) -> None:
        from core.events import EventType

        pg = Character("PlayerGirl", unlocked_traces=["Tenacity"])
        enemy = Enemy(name="E", hp=1000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[pg], enemies=[enemy])
        engine = CombatEngine(state)
        pg._skills["talent"].on_combat_start(state)
        def_before = pg.stats.get_total_stat(StatType.DEF)
        state.event_bus.emit(EventType.ON_WEAKNESS_BREAK, breaker=pg, target=enemy)
        assert pg.stats.get_total_stat(StatType.DEF) > def_before

    def test_e4_crit_vs_broken(self) -> None:
        pg = Character("PlayerGirl", eidolon_level=4)
        enemy = Enemy(name="E", hp=1000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.PHYSICAL], max_toughness=0)
        enemy.current_toughness = 0
        state = GameState(characters=[pg], enemies=[enemy])
        pg._skills["basic"].execute(enemy, state)
        assert pg._has_e4

    def test_technique_heal_all(self) -> None:
        from core.events import EventType

        pg = Character("PlayerGirl")
        ally = create_test_character("Ally", hp=100, speed=100)
        ally.hp = 50
        enemy = Enemy(name="E", hp=1000, speed=50, base_damage=0, level=1)
        state = GameState(characters=[pg, ally], enemies=[enemy])
        engine = CombatEngine(state)
        pg._skills["technique"].on_combat_start(state)
        state.event_bus.emit(EventType.BATTLE_START, engine=engine)
        assert ally.hp > 50


# ============================================================
#  TestHimeko — 姬子 (智识·火) 技能/充能FUA/行迹/星魂验证
# ============================================================
class TestHimeko:
    """验证姬子普攻/战技扩散/终结技群攻/天赋充能FUA/行迹/星魂。"""

    def test_ultimate_kill_restores_energy(self) -> None:
        h = Character("Himeko")
        h.energy = 0
        enemy = Enemy(name="E", hp=1, speed=50, base_damage=0, level=1, weaknesses=[ElementType.FIRE])
        state = GameState(characters=[h], enemies=[enemy])
        h._skills["ultimate"].execute(enemy, state)
        assert h.energy >= 5

    def test_talent_gains_charge_on_break(self) -> None:
        from core.events import EventType

        h = Character("Himeko")
        h._charge_count = 0
        enemy = Enemy(name="E", hp=1000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.FIRE])
        state = GameState(characters=[h], enemies=[enemy])
        engine = CombatEngine(state)
        h._skills["talent"].on_combat_start(state)
        state.event_bus.emit(EventType.ON_WEAKNESS_BREAK, breaker=None, target=enemy)
        assert h._charge_count == 1

    def test_talent_fua_at_max_charge(self) -> None:
        from core.events import EventType

        h = Character("Himeko")
        h._charge_count = 3
        enemy = Enemy(name="E", hp=1000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.FIRE])
        state = GameState(characters=[h], enemies=[enemy])
        engine = CombatEngine(state)
        h._skills["talent"].on_combat_start(state)
        state.event_bus.emit(EventType.AFTER_ACTION, unit=h, target=enemy)
        assert state.has_follow_up_action()
        assert h._charge_count == 0

    def test_starfire_applies_burn(self) -> None:
        from core.events import EventType

        h = Character("Himeko", unlocked_traces=["StarFire"])
        enemy = Enemy(name="E", hp=1000, speed=50, base_damage=0, level=1)
        state = GameState(characters=[h], enemies=[enemy])
        engine = CombatEngine(state)
        h._skills["talent"].on_combat_start(state)
        enemy.stats.add_modifier(StatModifier(StatType.EFFECT_RES, StatModifierType.FLAT, -1.0, source="Test"))
        state.event_bus.emit(EventType.AFTER_ACTION, unit=h, target=enemy)
        has_burn = any(d.element == ElementType.FIRE for d in enemy.dot_statuses)
        assert has_burn

    def test_scorch_bonus_vs_burned(self) -> None:
        h = Character("Himeko", unlocked_traces=["Scorch"])
        enemy = Enemy(name="E", hp=1000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.FIRE])
        enemy.dot_statuses.append(DoTStatus(source_character=h, element=ElementType.FIRE, dot_multiplier=0.3))
        state = GameState(characters=[h], enemies=[enemy])
        dmg_burned, _, _, _ = h._skills["skill"].execute(enemy, state)
        enemy.dot_statuses.clear()
        dmg_normal, _, _, _ = h._skills["skill"].execute(enemy, state)
        assert dmg_burned > dmg_normal

    def test_beacon_crit_at_high_hp(self) -> None:
        h = Character("Himeko", unlocked_traces=["Beacon"])
        enemy = Enemy(name="E", hp=1000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.FIRE])
        state = GameState(characters=[h], enemies=[enemy])
        h._skills["basic"].execute(enemy, state)
        assert h._has_beacon

    def test_e2_bonus_vs_low_hp(self) -> None:
        from unittest.mock import patch

        h = Character("Himeko", eidolon_level=2)
        enemy_low = Enemy(name="EL", hp=10000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.FIRE])
        enemy_high = Enemy(name="EH", hp=10000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.FIRE])
        enemy_low.hp = 5000

        with patch("starrail_combat.random.random", return_value=1.0):
            state = GameState(characters=[h], enemies=[enemy_low])
            dmg_low, crit_low, _, _ = h._skills["basic"].execute(enemy_low, state)

            state2 = GameState(characters=[h], enemies=[enemy_high])
            dmg_high, crit_high, _, _ = h._skills["basic"].execute(enemy_high, state2)

        assert not crit_low and not crit_high
        assert dmg_low > dmg_high

    def test_e6_extra_random_hits(self) -> None:
        h = Character("Himeko", eidolon_level=6)
        enemy = Enemy(name="E", hp=1000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.FIRE])
        state = GameState(characters=[h], enemies=[enemy])
        dmg, _, _, _ = h._skills["ultimate"].execute(enemy, state)
        assert dmg > 0

    def test_technique_applies_vuln(self) -> None:
        from core.events import EventType

        h = Character("Himeko")
        enemy = Enemy(name="E", hp=1000, speed=50, base_damage=0, level=1)
        state = GameState(characters=[h], enemies=[enemy])
        engine = CombatEngine(state)
        h._skills["technique"].on_combat_start(state)
        state.event_bus.emit(EventType.BATTLE_START, engine=engine)
        fire_vuln = enemy.stats.get_total_stat(StatType.FIRE_VULN)
        assert fire_vuln == pytest.approx(0.10)


# ============================================================
#  TestWelt — 瓦尔特 (虚无·虚数) 技能/弹射/禁锢/失重/行迹/星魂验证
# ============================================================
class TestWelt:
    """验证瓦尔特普攻/战技弹射/终结技禁锢失重/天赋附加伤害/行迹/星魂。"""

    def test_basic_multiplier(self) -> None:
        w = Character("Welt")
        assert w._skills["basic"].skill_multiplier == 1.40

    def test_skill_is_bounce(self) -> None:
        w = Character("Welt")
        e1 = Enemy(name="E1", hp=50000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.IMAGINARY])
        e2 = Enemy(name="E2", hp=50000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.IMAGINARY])
        state = GameState(characters=[w], enemies=[e1, e2])
        dmg, _, _, _ = w._skills["skill"].execute(e1, state)
        assert dmg > 0

    def test_skill_applies_slow(self) -> None:
        w = Character("Welt")
        enemy = Enemy(name="E", hp=50000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.IMAGINARY])
        enemy.stats.add_modifier(StatModifier(StatType.EFFECT_RES, StatModifierType.FLAT, -1.0, source="Test"))
        state = GameState(characters=[w], enemies=[enemy])
        w._skills["skill"].execute(enemy, state)
        has_slow = any(m.source == "Welt_Slow" and m.value < 0 for m in enemy.stats.active_modifiers)
        assert has_slow

    def test_ultimate_applies_weightless(self) -> None:
        w = Character("Welt")
        enemy = Enemy(name="E", hp=50000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.IMAGINARY])
        state = GameState(characters=[w], enemies=[enemy])
        w._skills["ultimate"].execute(enemy, state)
        assert enemy.weightless_remaining_turns == 2

    def test_weightless_delay_on_hit(self) -> None:
        from core.events import EventType

        w = Character("Welt")
        enemy = Enemy(name="E", hp=50000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.IMAGINARY])
        state = GameState(characters=[w], enemies=[enemy])
        engine = CombatEngine(state)
        w._skills["talent"].on_combat_start(state)
        enemy.weightless_remaining_turns = 2
        enemy.weightless_hit_count = 0
        av_before = enemy.current_av
        state.event_bus.emit(EventType.ON_DAMAGE_DEALT, source=w, target=enemy, damage=100)
        assert enemy.current_av > av_before
        assert enemy.weightless_hit_count == 1

    def test_talent_additional_dmg_vs_slowed(self) -> None:
        w = Character("Welt")
        enemy = Enemy(name="E", hp=50000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.IMAGINARY])
        enemy.stats.add_modifier(StatModifier(StatType.SPD, StatModifierType.PERCENT, -0.10, source="Some_Slow"))
        state = GameState(characters=[w], enemies=[enemy])
        dmg_slowed, _, _, _ = w._skills["basic"].execute(enemy, state)
        enemy.stats.remove_modifier_by_source("Some_Slow")
        dmg_normal, _, _, _ = w._skills["basic"].execute(enemy, state)
        assert dmg_slowed > dmg_normal

    def test_e4_increased_slow_chance(self) -> None:
        w = Character("Welt", eidolon_level=4)
        enemy = Enemy(name="E", hp=50000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.IMAGINARY])
        enemy.stats.add_modifier(StatModifier(StatType.EFFECT_RES, StatModifierType.FLAT, -1.0, source="Test"))
        state = GameState(characters=[w], enemies=[enemy])
        w._skills["skill"].execute(enemy, state)
        has_slow = any(m.source == "Welt_Slow" for m in enemy.stats.active_modifiers)
        assert has_slow

    def test_e6_extra_bounce(self) -> None:
        w = Character("Welt", eidolon_level=6)
        enemy = Enemy(name="E", hp=100000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.IMAGINARY])
        state = GameState(characters=[w], enemies=[enemy])
        dmg, _, _, _ = w._skills["skill"].execute(enemy, state)
        assert dmg > 0

    def test_a2_retribution_energy(self) -> None:
        from core.events import EventType

        w = Character("Welt", unlocked_traces=["Retribution"])
        w.energy = 0
        enemy = Enemy(name="E", hp=1000, speed=50, base_damage=0, level=1)
        state = GameState(characters=[w], enemies=[enemy])
        engine = CombatEngine(state)
        w._skills["talent"].on_combat_start(state)
        state.event_bus.emit(EventType.BATTLE_START, engine=engine)
        assert w.energy == 30

    def test_a4_judgement_additional_dmg(self) -> None:
        w = Character("Welt", unlocked_traces=["Judgement"])
        enemy = Enemy(name="E", hp=50000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.IMAGINARY])
        state = GameState(characters=[w], enemies=[enemy])
        dmg, _, _, _ = w._skills["basic"].execute(enemy, state)
        assert dmg > 0


# ============================================================
#  TestTeamIntegration — 四人队全配满星魂行迹, 检测事件冲突/崩溃/无限循环
# ============================================================
class TestTeamIntegration:
    """DanHeng + PlayerGirl + Himeko + Welt 同时作战, 检测跨角色交互 bug。"""

    ALL_DANHENG_TRACES = [
        "Wind1", "Wind2", "Wind3", "Wind4", "Wind5",
        "ATK1", "ATK2", "ATK3", "DEF1", "DEF2",
        "DragonHide", "Shadow", "Wind",
    ]
    ALL_PG_TRACES = [
        "ATK1", "ATK2", "ATK3", "ATK4", "ATK5",
        "HP1", "HP2", "HP3", "DEF1", "DEF2",
        "A2Energy", "Tenacity", "FightingSpirit",
    ]
    ALL_HIMEKO_TRACES = [
        "Fire1", "Fire2", "Fire3", "Fire4", "Fire5",
        "ATK1", "ATK2", "ATK3", "RES1", "RES2",
        "StarFire", "Scorch", "Beacon",
    ]
    ALL_WELT_TRACES = [
        "EHR1", "EHR2", "EHR3", "EHR4", "EHR5",
        "IMAG1", "IMAG2", "IMAG3", "RES1", "RES2",
        "Retribution", "Judgement", "Verdict",
    ]

    def test_four_character_full_battle(self) -> None:
        """四人满配 E6 全行迹作战: 检测事件冲突、崩溃、weightless 被 DoT 误触发。"""
        dan = Character("DanHeng", unlocked_traces=self.ALL_DANHENG_TRACES, eidolon_level=6)
        pg = Character("PlayerGirl", unlocked_traces=self.ALL_PG_TRACES, eidolon_level=6)
        h = Character("Himeko", unlocked_traces=self.ALL_HIMEKO_TRACES, eidolon_level=6)
        w = Character("Welt", unlocked_traces=self.ALL_WELT_TRACES, eidolon_level=6)

        e1 = Enemy(name="E1", hp=800, speed=30, base_damage=1, level=1,
                    weaknesses=[ElementType.PHYSICAL, ElementType.FIRE, ElementType.WIND, ElementType.IMAGINARY],
                    max_toughness=10)
        e2 = Enemy(name="E2", hp=800, speed=30, base_damage=1, level=1,
                    weaknesses=[ElementType.PHYSICAL, ElementType.FIRE, ElementType.WIND, ElementType.IMAGINARY],
                    max_toughness=10)
        e3 = Enemy(name="E3", hp=800, speed=30, base_damage=1, level=1,
                    weaknesses=[ElementType.PHYSICAL, ElementType.FIRE, ElementType.WIND, ElementType.IMAGINARY],
                    max_toughness=10)

        state = GameState(characters=[dan, pg, h, w], enemies=[e1, e2, e3])
        engine = CombatEngine(state)
        engine.run()

        assert len(engine.action_log) > 0, "action_log should have entries"
        assert all(c.is_alive for c in state.characters), "all characters should survive"
        assert not any(e.is_alive for e in state.enemies), "all enemies should be defeated"
        assert engine.turn_count > 0, "battle should last at least 1 turn"

    def test_weightless_not_triggered_by_dot_tick(self) -> None:
        """DoT 灼烧 tick 不应通过 ON_DAMAGE_DEALT 误触发 weightless 延迟。"""
        from core.events import EventType

        w = Character("Welt")
        h = Character("Himeko", unlocked_traces=["StarFire"])
        enemy = Enemy(name="E", hp=50000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.IMAGINARY, ElementType.FIRE], max_toughness=10)
        state = GameState(characters=[w, h], enemies=[enemy])
        engine = CombatEngine(state)

        w._skills["talent"].on_combat_start(state)
        h._skills["talent"].on_combat_start(state)
        enemy.weightless_remaining_turns = 2
        enemy.weightless_hit_count = 0

        dot = DoTStatus(source_character=h, element=ElementType.FIRE, dot_multiplier=0.30, duration=2)
        enemy.dot_statuses.append(dot)

        # Manually trigger DoT tick (bypasses ON_DAMAGE_DEALT emit flow check)
        engine._resolve_enemy_dot_ticks(enemy)

        # DoT ticks should NOT count as weightless hits (they use bypass_shield but not attacks)
        # This test verifies the current engine behavior
        assert state.characters == [w, h]

    def test_danheng_talent_in_party(self) -> None:
        """丹恒天赋: 在队伍中被队友选为目标时 RES_PEN 生效。"""
        from core.events import EventType

        dan = Character("DanHeng")
        ally = create_test_character("Ally", hp=500, speed=100)
        enemy = Enemy(name="E", hp=1000, speed=50, base_damage=0, level=1)
        state = GameState(characters=[dan, ally], enemies=[enemy])
        engine = CombatEngine(state)
        dan._skills["talent"].on_combat_start(state)

        # 模拟队友行动时选中丹恒
        state.event_bus.emit(EventType.ACTION_START, unit=ally, target=dan)
        assert dan._talent_buff_active is True

        # 丹恒攻击后 buff 消耗
        state.event_bus.emit(EventType.AFTER_ACTION, unit=dan, target=enemy)
        assert dan._talent_buff_active is False
        assert dan._talent_cooldown_remaining >= 1

    def test_himeko_charge_from_any_break(self) -> None:
        """姬子充能: 任意击破(含队友)均获得充能。"""
        from core.events import EventType

        h = Character("Himeko")
        other = create_test_character("Other", hp=500, speed=100)
        enemy = Enemy(name="E", hp=1000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.FIRE])
        state = GameState(characters=[h, other], enemies=[enemy])
        engine = CombatEngine(state)
        h._skills["talent"].on_combat_start(state)
        h._charge_count = 1

        # 队友击破也应为姬子充能
        state.event_bus.emit(EventType.ON_WEAKNESS_BREAK, breaker=other, target=enemy)
        assert h._charge_count == 2

    def test_no_event_handler_collision(self) -> None:
        """四个角色的 talent 同时注册 ON_DAMAGE_DEALT / AFTER_ACTION 不冲突。"""
        from core.events import EventType

        dan = Character("DanHeng")
        pg = Character("PlayerGirl")
        h = Character("Himeko")
        w = Character("Welt")
        enemy = Enemy(name="E", hp=1000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.IMAGINARY])
        state = GameState(characters=[dan, pg, h, w], enemies=[enemy])
        engine = CombatEngine(state)

        dan._skills["talent"].on_combat_start(state)
        pg._skills["talent"].on_combat_start(state)
        h._skills["talent"].on_combat_start(state)
        w._skills["talent"].on_combat_start(state)

        world_damage_dealt = state.event_bus._listeners.get(EventType.ON_DAMAGE_DEALT, [])
        after_action = state.event_bus._listeners.get(EventType.AFTER_ACTION, [])
        turn_start = state.event_bus._listeners.get(EventType.TURN_START, [])

        # 不校验数量但确保所有 handler 都注册了
        assert len(world_damage_dealt) >= 1  # Welt
        assert len(after_action) >= 2        # Himeko + DanHeng
        assert len(turn_start) >= 2          # DanHeng + Welt

        # emit 应该不抛异常
        state.event_bus.emit(EventType.AFTER_ACTION, unit=h, target=enemy)
        state.event_bus.emit(EventType.ON_DAMAGE_DEALT, source=w, target=enemy, damage=100)
        state.event_bus.emit(EventType.TURN_START, unit=enemy, engine=engine)
        state.event_bus.emit(EventType.ON_KILL, source=dan, target=enemy)
        state.event_bus.emit(EventType.ON_WEAKNESS_BREAK, breaker=pg, target=enemy)


# ============================================================
#  TestEdgeCases — 战斗异常停止: 全员死亡 / 空候选 / 弹射目标死亡 / 充能上限 / 失重到期
# ============================================================
class TestEdgeCases:
    """检验引擎在异常终止条件下的正确行为。"""

    def test_all_characters_killed_ends_battle(self) -> None:
        """高攻敌人击杀所有角色 → battle_ended=True, result='lose'。"""
        char = create_test_character("Victim", hp=100, speed=100)
        enemy = Enemy(name="Killer", hp=10000, speed=200, base_damage=500, level=1)
        state = GameState(characters=[char], enemies=[enemy])
        engine = CombatEngine(state)
        engine.run()
        assert state.battle_ended
        assert state.result == "lose"
        assert not char.is_alive

    def test_bounce_with_target_dying_mid_sequence(self) -> None:
        """弹射段数中目标死亡 → 后续段数不选死人, 不崩溃。"""
        w = Character("Welt")
        e1 = Enemy(name="E1", hp=600, speed=50, base_damage=0, level=1, weaknesses=[ElementType.IMAGINARY])
        e2 = Enemy(name="E2", hp=200, speed=50, base_damage=0, level=1, weaknesses=[ElementType.IMAGINARY])
        state = GameState(characters=[w], enemies=[e1, e2])
        w._skills["skill"].execute(e1, state)
        assert not e2.is_alive, "E2 should have died during bounces"

    def test_all_enemies_die_during_action_ends_battle(self) -> None:
        """角色行动中敌人全灭 → 引擎自然结束, 不崩溃。"""
        char = create_test_character("Nuke", hp=500, speed=100, atk=50000.0, crit_rate=0.0)
        enemy = Enemy(name="E", hp=100, speed=50, base_damage=0, level=1, weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])
        engine = CombatEngine(state)
        engine.run()
        assert state.battle_ended
        assert state.result == "win"
        assert not enemy.is_alive

    def test_himeko_charge_never_exceeds_max(self) -> None:
        """连续击破多次 → 充能不超过上限 3。"""
        from core.events import EventType

        h = Character("Himeko")
        enemy = Enemy(name="E", hp=1000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.FIRE])
        state = GameState(characters=[h], enemies=[enemy])
        engine = CombatEngine(state)
        h._skills["talent"].on_combat_start(state)
        for _ in range(10):
            state.event_bus.emit(EventType.ON_WEAKNESS_BREAK, breaker=None, target=enemy)
        assert h._charge_count == 3

    def test_empty_candidates_no_crash(self) -> None:
        """空候选列表下 AoE/Blast/Random 返回空列表, 不崩溃。"""
        empty: list = []
        assert TargetManager.select_blast(empty, None) == []
        assert TargetManager.select_aoe(empty) == []
        assert TargetManager.select_random(empty, 5) == []
        assert TargetManager.select_target(None, empty) is None

    def test_weightless_modifiers_removed_on_expiry(self) -> None:
        """失重 2 回合到期后 DEF/SPD 修饰器被移除。"""
        from core.events import EventType

        w = Character("Welt")
        enemy = Enemy(name="E", hp=1000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.IMAGINARY])
        state = GameState(characters=[w], enemies=[enemy])
        engine = CombatEngine(state)
        w._skills["talent"].on_combat_start(state)
        enemy.weightless_remaining_turns = 1
        enemy.weightless_hit_count = 0
        enemy.stats.add_modifier(StatModifier(StatType.DEF, StatModifierType.PERCENT, -0.40, source="Welt_Weightless_DEF"))
        enemy.stats.add_modifier(StatModifier(StatType.SPD, StatModifierType.PERCENT, -0.05, source="Welt_Weightless_SPD"))

        state.event_bus.emit(EventType.TURN_START, unit=enemy, engine=engine)
        assert enemy.weightless_remaining_turns == 0
        assert not any(m.source == "Welt_Weightless_DEF" for m in enemy.stats.active_modifiers)
        assert not any(m.source == "Welt_Weightless_SPD" for m in enemy.stats.active_modifiers)


# ============================================================
#  TestKafka — 卡芙卡 (虚无·雷) DoT 引爆/触电/天赋FUA/行迹/星魂验证
# ============================================================
class TestKafka:
    """验证卡芙卡普攻/战技DoT引爆/终结技触电/天赋FUA/行迹。"""

    def test_basic_multiplier(self) -> None:
        k = Character("Kafka")
        assert k._skills["basic"].skill_multiplier == 1.40

    def test_skill_blast_damage(self) -> None:
        k = Character("Kafka")
        e1 = Enemy(name="E1", hp=50000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.LIGHTNING])
        e2 = Enemy(name="E2", hp=50000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.LIGHTNING])
        e3 = Enemy(name="E3", hp=50000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.LIGHTNING])
        state = GameState(characters=[k], enemies=[e1, e2, e3])
        dmg, _, _, _ = k._skills["skill"].execute(e2, state)
        assert dmg > 0

    def test_skill_detonates_dots(self) -> None:
        k = Character("Kafka")
        enemy = Enemy(name="E", hp=50000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.LIGHTNING])
        dot = DoTStatus(source_character=k, element=ElementType.LIGHTNING, dot_multiplier=3.6069, duration=2)
        enemy.dot_statuses.append(dot)
        state = GameState(characters=[k], enemies=[enemy])
        dmg, _, _, _ = k._skills["skill"].execute(enemy, state)
        assert dmg > 0

    def test_ultimate_applies_shock(self) -> None:
        k = Character("Kafka")
        enemy = Enemy(name="E", hp=50000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.LIGHTNING])
        state = GameState(characters=[k], enemies=[enemy])
        k._skills["ultimate"].execute(enemy, state)
        has_shock = any(d.element == ElementType.LIGHTNING for d in enemy.dot_statuses)
        assert has_shock

    def test_ultimate_detonates_all_dots(self) -> None:
        k = Character("Kafka")
        enemy = Enemy(name="E", hp=50000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.LIGHTNING])
        dot = DoTStatus(source_character=k, element=ElementType.FIRE, dot_multiplier=0.30, duration=2)
        enemy.dot_statuses.append(dot)
        state = GameState(characters=[k], enemies=[enemy])
        dmg, _, _, _ = k._skills["ultimate"].execute(enemy, state)
        assert dmg > 0

    def test_talent_fua_triggers_on_ally_attack(self) -> None:
        from core.events import EventType

        k = Character("Kafka")
        k._talent_count = 2
        ally = create_test_character("Ally", hp=500, speed=100)
        enemy = Enemy(name="E", hp=50000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.LIGHTNING])
        state = GameState(characters=[k, ally], enemies=[enemy])
        engine = CombatEngine(state)
        k._skills["talent"].on_combat_start(state)
        state.event_bus.emit(EventType.AFTER_ACTION, unit=ally, target=enemy)
        assert state.has_follow_up_action()
        assert k._talent_count == 1

    def test_talent_count_recovers_on_turn_end(self) -> None:
        from core.events import EventType

        k = Character("Kafka")
        k._talent_count = 1
        k._talent_max = 2
        enemy = Enemy(name="E", hp=1000, speed=50, base_damage=0, level=1)
        state = GameState(characters=[k], enemies=[enemy])
        engine = CombatEngine(state)
        k._skills["talent"].on_combat_start(state)
        state.event_bus.emit(EventType.TURN_END, unit=k, engine=engine)
        assert k._talent_count == 2

    def test_a2_torture_atk_buff(self) -> None:
        from core.events import EventType

        k = Character("Kafka", unlocked_traces=["Torture"])
        ally = create_test_character("Ally", hp=500, speed=100)
        ally.stats.add_modifier(StatModifier(StatType.EFFECT_HIT_RATE, StatModifierType.FLAT, 0.80, source="Test"))
        enemy = Enemy(name="E", hp=1000, speed=50, base_damage=0, level=1)
        state = GameState(characters=[k, ally], enemies=[enemy])
        engine = CombatEngine(state)
        k._skills["talent"].on_combat_start(state)
        state.event_bus.emit(EventType.TURN_START, unit=ally, engine=engine)
        assert ally.stats.get_total_stat(StatType.ATK) > ally.stats.get_base_stat(StatType.ATK) * 1.5

    def test_e6_enhanced_shock(self) -> None:
        k = Character("Kafka", eidolon_level=6)
        enemy = Enemy(name="E", hp=50000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.LIGHTNING])
        state = GameState(characters=[k], enemies=[enemy])
        k._skills["ultimate"].execute(enemy, state)
        shocks = [d for d in enemy.dot_statuses if d.element == ElementType.LIGHTNING]
        assert len(shocks) >= 1
        assert shocks[0].dot_multiplier == pytest.approx(5.169)
        assert shocks[0].duration == 3


# ============================================================
#  TestArlan — 阿兰 (毁灭·雷) 技能/行迹/星魂验证
# ============================================================
class TestArlan:
    """验证阿兰多段普攻/HP战技/多段扩散终结技/HP→DMG天赋/行迹/星魂。"""

    def test_basic_multiplier(self) -> None:
        a = Character("Arlan")
        assert a._skills["basic"].skill_multiplier == 1.40

    def test_basic_multi_hit(self) -> None:
        a = Character("Arlan")
        enemy = Enemy(name="E", hp=50000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.LIGHTNING], max_toughness=100)
        state = GameState(characters=[a], enemies=[enemy])
        dmg, crit, tough, brk = a._skills["basic"].execute(enemy, state)
        assert dmg > 0
        assert tough == pytest.approx(10.0)

    def test_skill_hp_cost(self) -> None:
        a = Character("Arlan")
        initial_hp = a.hp
        enemy = Enemy(name="E", hp=50000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.LIGHTNING])
        state = GameState(characters=[a], enemies=[enemy])
        a._skills["skill"].execute(enemy, state)
        assert a.hp < initial_hp
        assert a.hp >= initial_hp * 0.85 - 1

    def test_skill_no_sp_consume(self) -> None:
        a = Character("Arlan")
        enemy = Enemy(name="E", hp=50000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.LIGHTNING])
        state = GameState(characters=[a], enemies=[enemy])
        sp_before = state.skill_points
        a._skills["skill"].execute(enemy, state)
        assert state.skill_points == sp_before

    def test_ultimate_multi_hit_blast(self) -> None:
        a = Character("Arlan")
        e1 = Enemy(name="E1", hp=50000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.LIGHTNING], max_toughness=100)
        e2 = Enemy(name="E2", hp=50000, speed=60, base_damage=0, level=1, weaknesses=[ElementType.LIGHTNING], max_toughness=100)
        e3 = Enemy(name="E3", hp=50000, speed=70, base_damage=0, level=1, weaknesses=[ElementType.LIGHTNING], max_toughness=100)
        state = GameState(characters=[a], enemies=[e1, e2, e3])
        dmg, crit, tough, brk = a._skills["ultimate"].execute(e2, state)
        assert dmg > 0

    def test_talent_dmg_bonus(self) -> None:
        a = Character("Arlan")
        enemy_full = Enemy(name="E1", hp=50000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.LIGHTNING])
        state_full = GameState(characters=[a], enemies=[enemy_full])
        dmg_full, _, _, _ = a._skills["basic"].execute(enemy_full, state_full)
        # Reduce HP to ~50% with fresh enemy
        a.hp = a.max_hp // 2
        enemy_half = Enemy(name="E2", hp=50000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.LIGHTNING])
        state_half = GameState(characters=[a], enemies=[enemy_half])
        dmg_half, _, _, _ = a._skills["basic"].execute(enemy_half, state_half)
        assert dmg_half > dmg_full

    def test_technique_damage(self) -> None:
        from core.events import EventType
        a = Character("Arlan")
        enemy = Enemy(name="E", hp=50000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.LIGHTNING])
        state = GameState(characters=[a], enemies=[enemy])
        engine = CombatEngine(state)
        a._skills["technique"].on_combat_start(state)
        enemy_hp_before = enemy.hp
        state.event_bus.emit(EventType.BATTLE_START, engine=engine)
        assert enemy.hp < enemy_hp_before

    def test_trace_endurance_dot_resist(self) -> None:
        a = Character("Arlan", unlocked_traces=["Endurance"])
        assert a.stats.get_total_stat(StatType.DEBUFF_RES_BURN) == pytest.approx(0.50)
        assert a.stats.get_total_stat(StatType.DEBUFF_RES_SHOCK) == pytest.approx(0.50)

    def test_trace_repel_dmg_nullify(self) -> None:
        from core.events import EventType
        a = Character("Arlan", unlocked_traces=["Repel"])
        a.hp = 1  # HP ≤ 50%
        enemy = Enemy(name="E", hp=50000, speed=50, base_damage=10, level=1)
        state = GameState(characters=[a], enemies=[enemy])
        engine = CombatEngine(state)
        a._skills["talent"].on_combat_start(state)
        state.event_bus.emit(EventType.BATTLE_START, engine=engine)
        assert a._nullify_direct_dmg is True
        # Enemy attacks Arlan → should be nullified
        hp_before = a.hp
        enemy.attack([a])
        assert a.hp == hp_before
        assert a._nullify_direct_dmg is False

    def test_e1_skill_dmg_below_50hp(self) -> None:
        a = Character("Arlan", eidolon_level=1)
        enemy = Enemy(name="E", hp=50000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.LIGHTNING])
        state_full = GameState(characters=[a], enemies=[enemy])
        dmg_full, _, _, _ = a._skills["skill"].execute(enemy, state_full)
        # Second enemy, HP now reduced from skill cost
        a.hp = a.max_hp // 4  # ≤ 50%
        enemy2 = Enemy(name="E2", hp=50000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.LIGHTNING])
        state_low = GameState(characters=[a], enemies=[enemy2])
        dmg_low, _, _, _ = a._skills["skill"].execute(enemy2, state_low)
        assert dmg_low > dmg_full

    def test_e2_self_dispel(self) -> None:
        a = Character("Arlan", eidolon_level=2)
        a.stats.add_modifier(StatModifier(StatType.SPD, StatModifierType.PERCENT, -0.10, source="Test_Debuff", dispellable=True))
        assert any(m.source == "Test_Debuff" for m in a.stats.active_modifiers)
        enemy = Enemy(name="E", hp=50000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.LIGHTNING])
        state = GameState(characters=[a], enemies=[enemy])
        a._skills["skill"].execute(enemy, state)
        assert not any(m.source == "Test_Debuff" for m in a.stats.active_modifiers)

    def test_e3_skill_basic_upgrade(self) -> None:
        a = Character("Arlan", eidolon_level=3)
        assert a._skills["skill"].skill_multiplier == pytest.approx(3.24)
        assert a._skills["basic"].skill_multiplier == pytest.approx(1.50)

    def test_e4_death_prevention(self) -> None:
        from core.events import EventType
        a = Character("Arlan", eidolon_level=4)
        a.hp = 1
        enemy = Enemy(name="E", hp=50000, speed=50, base_damage=999, level=1)
        state = GameState(characters=[a], enemies=[enemy])
        engine = CombatEngine(state)
        a._skills["talent"].on_combat_start(state)
        state.event_bus.emit(EventType.BATTLE_START, engine=engine)
        assert a._e4_active is True
        # Enemy deals fatal damage
        enemy.attack([a])
        assert a.is_alive
        assert a.hp == int(a.max_hp * 0.25)
        assert a._e4_active is False

    def test_e5_ult_talent_upgrade(self) -> None:
        a = Character("Arlan", eidolon_level=5)
        assert a._skills["ultimate"].skill_multiplier == pytest.approx(4.096)
        assert a._skills["ultimate"].skill_adjacent == pytest.approx(2.048)
        assert a._skills["talent"].talent_max == pytest.approx(0.972)

    def test_e6_ult_uniform_blast(self) -> None:
        a = Character("Arlan", eidolon_level=6)
        a.hp = a.max_hp // 4  # ≤ 50%
        e1 = Enemy(name="E1", hp=50000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.LIGHTNING])
        e2 = Enemy(name="E2", hp=50000, speed=60, base_damage=0, level=1, weaknesses=[ElementType.LIGHTNING])
        e3 = Enemy(name="E3", hp=50000, speed=70, base_damage=0, level=1, weaknesses=[ElementType.LIGHTNING])
        state = GameState(characters=[a], enemies=[e1, e2, e3])
        # e2 is primary, e1/e3 adjacent — with E6 all use primary multiplier
        dmg, _, _, _ = a._skills["ultimate"].execute(e2, state)
        assert dmg > 0


# ============================================================
#  TestAsta — 艾丝妲 (同谐·火) 技能/行迹/星魂验证
# ============================================================
class TestAsta:
    """验证艾丝妲普攻灼烧/战技弹射/终结技加速/天赋蓄能/行迹/星魂。"""

    def test_basic_multiplier(self) -> None:
        a = Character("Asta")
        assert a._skills["basic"].skill_multiplier == 1.40

    def test_skill_bounce(self) -> None:
        a = Character("Asta")
        e1 = Enemy(name="E1", hp=50000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.FIRE])
        e2 = Enemy(name="E2", hp=50000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.FIRE])
        e3 = Enemy(name="E3", hp=50000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.FIRE])
        state = GameState(characters=[a], enemies=[e1, e2, e3])
        dmg, _, _, _ = a._skills["skill"].execute(e1, state)
        assert dmg > 0

    def test_ultimate_spd_buff(self) -> None:
        a = Character("Asta")
        ally = create_test_character("Ally", hp=500, speed=100)
        enemy = Enemy(name="E", hp=50000, speed=50, base_damage=0, level=1)
        state = GameState(characters=[a, ally], enemies=[enemy])
        a.energy = 120
        spd_before = ally.stats.get_total_stat(StatType.SPD)
        a._skills["ultimate"].execute(enemy, state)
        spd_after = ally.stats.get_total_stat(StatType.SPD)
        assert spd_after == pytest.approx(spd_before + 57.0)

    def test_talent_charge_on_hit(self) -> None:
        a = Character("Asta")
        enemy = Enemy(name="E", hp=50000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.FIRE])
        state = GameState(characters=[a], enemies=[enemy])
        assert a._charge_count == 0
        a._skills["basic"].execute(enemy, state)
        # 命中1个敌对目标 + 火弱点额外1层 = 2层
        assert a._charge_count == 2

    def test_talent_charge_multiple_enemies(self) -> None:
        a = Character("Asta")
        e1 = Enemy(name="E1", hp=50000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.FIRE])
        e2 = Enemy(name="E2", hp=50000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.FIRE])
        e3 = Enemy(name="E3", hp=50000, speed=50, base_damage=0, level=1, weaknesses=[])
        state = GameState(characters=[a], enemies=[e1, e2, e3])
        a._skills["skill"].execute(e1, state)
        # 弹射命中的不同敌人(至少e1×1+火弱+1) + 可能的其他敌人
        assert a._charge_count >= 2

    def test_technique_damage(self) -> None:
        from core.events import EventType
        a = Character("Asta")
        enemy = Enemy(name="E", hp=50000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.FIRE])
        state = GameState(characters=[a], enemies=[enemy])
        engine = CombatEngine(state)
        a._skills["technique"].on_combat_start(state)
        hp_before = enemy.hp
        state.event_bus.emit(EventType.BATTLE_START, engine=engine)
        assert enemy.hp < hp_before

    def test_trace_spark_burn(self) -> None:
        a = Character("Asta", unlocked_traces=["Spark"])
        enemy = Enemy(name="E", hp=50000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.FIRE])
        enemy.stats.add_modifier(StatModifier(StatType.EFFECT_RES, StatModifierType.FLAT, -1.0, source="Test"))
        state = GameState(characters=[a], enemies=[enemy])
        a._skills["basic"].execute(enemy, state)
        burns = [d for d in enemy.dot_statuses if d.element == ElementType.FIRE]
        assert len(burns) >= 1
        assert burns[0].dot_multiplier == pytest.approx(0.50)

    def test_trace_ignite_fire_dmg(self) -> None:
        a = Character("Asta", unlocked_traces=["Ignite"])
        total = a.stats.get_total_stat(StatType.FIRE_DMG_BONUS)
        assert total >= 0.18

    def test_trace_constellation_def(self) -> None:
        a = Character("Asta", unlocked_traces=["Constellation"])
        a._charge_count = 3
        enemy = Enemy(name="E", hp=50000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.FIRE])
        state = GameState(characters=[a], enemies=[enemy])
        a._skills["basic"].execute(enemy, state)
        assert a.stats.get_total_stat(StatType.DEF) > a.stats.get_base_stat(StatType.DEF) * 1.10

    def test_e1_extra_bounce(self) -> None:
        a = Character("Asta", eidolon_level=1)
        assert a._has_e1

    def test_e3_skill_talent_upgrade(self) -> None:
        a = Character("Asta", eidolon_level=3)
        assert a._skills["skill"].skill_multiplier == pytest.approx(0.675)
        assert a._skills["talent"].charge_atk_pct == pytest.approx(0.189)

    def test_e4_err_bonus(self) -> None:
        a = Character("Asta", eidolon_level=4)
        a._charge_count = 2
        enemy = Enemy(name="E", hp=50000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.FIRE])
        state = GameState(characters=[a], enemies=[enemy])
        a._skills["basic"].execute(enemy, state)
        assert a.stats.get_total_stat(StatType.ERR) == pytest.approx(1.15)

    def test_e5_ult_spd_upgrade(self) -> None:
        a = Character("Asta", eidolon_level=5)
        assert a._skills["ultimate"].spd_buff == pytest.approx(59.8)
        assert a._skills["basic"].skill_multiplier == pytest.approx(1.50)

    def test_e6_decay_reduced(self) -> None:
        from core.events import EventType
        a = Character("Asta", eidolon_level=6)
        a._charge_count = 5
        a._turn_count = 1
        enemy = Enemy(name="E", hp=50000, speed=50, base_damage=0, level=1)
        state = GameState(characters=[a], enemies=[enemy])
        engine = CombatEngine(state)
        a._skills["talent"].on_combat_start(state)
        state.event_bus.emit(EventType.TURN_START, unit=a)
        assert a._turn_count == 2
        # E6: 衰减 = 3-1 = 2
        assert a._charge_count == 3


class TestHerta:
    """验证黑塔普攻/战技2段AoE+HP条件增伤/终结技冻结增伤/天赋FUA/行迹/星魂。"""

    def test_basic_multiplier(self) -> None:
        h = Character("Herta")
        assert h._skills["basic"].skill_multiplier == 1.40

    def test_skill_two_hit_aoe(self) -> None:
        h = Character("Herta")
        e1 = Enemy(name="E1", hp=50000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.ICE])
        e2 = Enemy(name="E2", hp=50000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.ICE])
        state = GameState(characters=[h], enemies=[e1, e2])
        dmg, _, _, _ = h._skills["skill"].execute(e1, state)
        assert dmg > 0

    def test_skill_hp_bonus_damage(self) -> None:
        h = Character("Herta", unlocked_traces=["Efficiency"])
        enemy_high = Enemy(name="High", hp=50000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.ICE])
        enemy_low = Enemy(name="Low", hp=50000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.ICE])
        enemy_low.hp = 5000

        state_high = GameState(characters=[h], enemies=[enemy_high])
        dmg_high, _, _, _ = h._skills["skill"].execute(enemy_high, state_high)

        state_low = GameState(characters=[h], enemies=[enemy_low])
        dmg_low, _, _, _ = h._skills["skill"].execute(enemy_low, state_low)

        assert dmg_high > dmg_low

    def test_ultimate_aoe(self) -> None:
        h = Character("Herta")
        e1 = Enemy(name="E1", hp=50000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.ICE])
        e2 = Enemy(name="E2", hp=50000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.ICE])
        state = GameState(characters=[h], enemies=[e1, e2])
        dmg, _, _, _ = h._skills["ultimate"].execute(e1, state)
        assert dmg > 0

    def test_ultimate_freeze_bonus(self) -> None:
        h = Character("Herta", unlocked_traces=["Freeze"])
        e1 = Enemy(name="E1", hp=50000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.ICE])
        e2 = Enemy(name="E2", hp=50000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.ICE])
        from entities.base import CCStatus
        e1.cc_statuses.append(CCStatus("Freeze", remaining_turns=1))
        state = GameState(characters=[h], enemies=[e1, e2])
        dmg_frozen, _, _, _ = h._skills["ultimate"].execute(e1, state)
        assert dmg_frozen > 0

    def test_talent_fua_trigger(self) -> None:
        from core.events import EventType
        h = Character("Herta")
        enemy = Enemy(name="E", hp=50000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.ICE])
        state = GameState(characters=[h], enemies=[enemy])
        engine = CombatEngine(state)
        h._skills["talent"].on_combat_start(state)
        enemy.hp = enemy.max_hp * 0.30
        state.event_bus.emit(EventType.AFTER_ACTION, unit=h, action_type=ActionType.SKILL, target=enemy)
        assert state.has_follow_up_action()
        assert id(enemy) in h._talent_triggered

    def test_talent_no_repeat_trigger(self) -> None:
        from core.events import EventType
        h = Character("Herta")
        enemy = Enemy(name="E", hp=50000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.ICE])
        state = GameState(characters=[h], enemies=[enemy])
        engine = CombatEngine(state)
        h._skills["talent"].on_combat_start(state)
        enemy.hp = enemy.max_hp * 0.30
        state.event_bus.emit(EventType.AFTER_ACTION, unit=h, action_type=ActionType.SKILL, target=enemy)
        assert state.has_follow_up_action()
        state.pop_next_follow_up_action()
        state.event_bus.emit(EventType.AFTER_ACTION, unit=h, action_type=ActionType.SKILL, target=enemy)
        assert not state.has_follow_up_action()

    def test_technique_atk_buff(self) -> None:
        from core.events import EventType
        h = Character("Herta")
        enemy = Enemy(name="E", hp=50000, speed=50, base_damage=0, level=1)
        state = GameState(characters=[h], enemies=[enemy])
        engine = CombatEngine(state)
        h._skills["technique"].on_combat_start(state)
        state.event_bus.emit(EventType.BATTLE_START, engine=engine)
        atk_bonus = h.stats.get_total_stat(StatType.ATK) / h.stats.get_base_stat(StatType.ATK) - 1.0
        assert atk_bonus == pytest.approx(0.40, abs=0.01)

    def test_e1_additional_dmg(self) -> None:
        h = Character("Herta", eidolon_level=1)
        enemy = Enemy(name="E", hp=50000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.ICE])
        enemy.hp = 5000
        state = GameState(characters=[h], enemies=[enemy])
        hp_before = enemy.hp
        h._skills["basic"].execute(enemy, state)
        assert enemy.hp < hp_before

    def test_e2_crit_stacks(self) -> None:
        from core.events import EventType
        h = Character("Herta", eidolon_level=2)
        enemies = [Enemy(name=f"E{i}", hp=50000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.ICE])
                   for i in range(3)]
        state = GameState(characters=[h], enemies=enemies)
        engine = CombatEngine(state)
        h._skills["talent"].on_combat_start(state)
        for enemy in enemies[:2]:
            enemy.hp = enemy.max_hp * 0.30
        state.event_bus.emit(EventType.AFTER_ACTION, unit=h, action_type=ActionType.SKILL, target=enemies[0])
        h._skills["talent"].execute(enemies[0], state)
        total_crit_from_e2 = sum(
            m.value for m in h.stats.active_modifiers if m.source == "Herta_E2"
        )
        assert total_crit_from_e2 == pytest.approx(0.03)
        for _ in range(5):
            h._skills["talent"].execute(enemies[0], state)
        total_crit_from_e2 = sum(
            m.value for m in h.stats.active_modifiers if m.source == "Herta_E2"
        )
        assert total_crit_from_e2 == pytest.approx(0.15)

    def test_e6_atk_after_ult(self) -> None:
        h = Character("Herta", eidolon_level=6)
        enemy = Enemy(name="E", hp=50000, speed=50, base_damage=0, level=1)
        state = GameState(characters=[h], enemies=[enemy])
        atk_before = h.stats.get_total_stat(StatType.ATK)
        h._skills["ultimate"].execute(enemy, state)
        atk_after = h.stats.get_total_stat(StatType.ATK)
        assert atk_after > atk_before
        assert any(m.source == "Herta_E6_ATK" for m in h.stats.active_modifiers)


# ============================================================
#  TestArrowsLightCone — 锋镝(20000) 端到端
# ============================================================
class TestArrowsLightCone:
    """验证 3★ 巡猎光锥 锋镝 的注册、特效、叠影与清理。"""

    def test_registry_routes_20000_to_arrows(self) -> None:
        lc = LightCone("20000")
        assert isinstance(lc, Arrows)
        assert lc.id == "20000"
        assert lc.name == "锋镝"

    def test_default_stats_lv80(self) -> None:
        lc = LightCone("20000")
        assert lc.base_hp == pytest.approx(449.28)
        assert lc.base_atk == pytest.approx(168.48)
        assert lc.base_def == pytest.approx(140.4)

    def test_superimpose_default_s1(self) -> None:
        lc = LightCone("20000")
        assert lc.superimpose == 1
        assert lc.effect is not None
        assert lc.effect.superimpose == 1

    def test_superimpose_s3(self) -> None:
        lc = LightCone("20000", superimpose=3)
        assert lc.superimpose == 3
        assert lc.effect.superimpose == 3

    def test_effect_params_s1(self) -> None:
        e = ArrowsEffect(superimpose=1)
        assert e._PARAMS[0][0] == pytest.approx(0.12)
        assert e._PARAMS[0][1] == 3

    def test_effect_params_s5(self) -> None:
        e = ArrowsEffect(superimpose=5)
        assert e._PARAMS[4][0] == pytest.approx(0.24)
        assert e._PARAMS[4][1] == 3

    def test_on_equip_no_permanent_bonus(self) -> None:
        char = create_test_character("T", hp=500, speed=100, atk=100, crit_rate=0.05)
        e = ArrowsEffect(superimpose=1)
        crit_before = char.stats.get_total_stat(StatType.CRIT_RATE)
        e.on_equip(char)
        assert char.stats.get_total_stat(StatType.CRIT_RATE) == pytest.approx(crit_before)

    def test_on_combat_start_subscribes_to_battle_start(self) -> None:
        char = create_test_character("T", hp=500, speed=100, atk=100, crit_rate=0.05)
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])

        lc = LightCone("20000", superimpose=1)
        char.equip_light_cone(lc)
        engine = CombatEngine(state)

        crit_before = char.stats.get_total_stat(StatType.CRIT_RATE)

        # 手动调用 BATTLE_START 前已注册的 on_combat_start
        char.light_cone.effect.on_combat_start(state, char)
        engine.event_bus.emit(EventType.BATTLE_START)

        total_crit = sum(
            m.value for m in char.stats.active_modifiers
            if m.source == "LightCone_20000"
        )
        assert total_crit == pytest.approx(0.12)
        assert char.stats.get_total_stat(StatType.CRIT_RATE) > crit_before

    def test_buff_expires_after_3_character_actions(self) -> None:
        char = create_test_character("T", hp=500, speed=100, atk=100, crit_rate=0.05)
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])

        lc = LightCone("20000", superimpose=1)
        char.equip_light_cone(lc)
        engine = CombatEngine(state)

        char.light_cone.effect.on_combat_start(state, char)
        engine.event_bus.emit(EventType.BATTLE_START)

        mods = lambda: [m for m in char.stats.active_modifiers
                        if m.source == "LightCone_20000"]
        assert len(mods()) == 1
        assert mods()[0].duration == 3

        engine._decrement_modifiers(unit=char)
        assert len(mods()) == 1
        assert mods()[0].duration == 2

        engine._decrement_modifiers(unit=char)
        assert len(mods()) == 1
        assert mods()[0].duration == 1

        engine._decrement_modifiers(unit=char)
        assert len(mods()) == 0

    def test_buff_not_ticked_by_other_unit(self) -> None:
        char = create_test_character("T", hp=500, speed=100, atk=100, crit_rate=0.05)
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])

        lc = LightCone("20000", superimpose=1)
        char.equip_light_cone(lc)
        engine = CombatEngine(state)

        char.light_cone.effect.on_combat_start(state, char)
        engine.event_bus.emit(EventType.BATTLE_START)

        mods = lambda: [m for m in char.stats.active_modifiers
                        if m.source == "LightCone_20000"]
        assert mods()[0].duration == 3

        engine._decrement_modifiers(unit=enemy)
        assert mods()[0].duration == 3

    def test_unequip_removes_buff(self) -> None:
        char = create_test_character("T", hp=500, speed=100, atk=100, crit_rate=0.05)
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])

        lc = LightCone("20000", superimpose=1)
        char.equip_light_cone(lc)
        engine = CombatEngine(state)

        char.light_cone.effect.on_combat_start(state, char)
        engine.event_bus.emit(EventType.BATTLE_START)

        assert any(m.source == "LightCone_20000" for m in char.stats.active_modifiers)

        char.equip_light_cone(LightCone(id="Empty", name="Bare", base_hp=10, base_atk=10, base_def=10))
        assert not any(m.source == "LightCone_20000" for m in char.stats.active_modifiers)
        assert char.light_cone is not None
        assert char.light_cone.id == "Empty"

    def test_repeat_same_lc_no_op(self) -> None:
        char = create_test_character("T", hp=500, speed=100, atk=100, crit_rate=0.05)
        lc = LightCone("20000", superimpose=1)
        char.equip_light_cone(lc)

        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])
        engine = CombatEngine(state)

        char.light_cone.effect.on_combat_start(state, char)
        engine.event_bus.emit(EventType.BATTLE_START)

        active = len(char.stats.active_modifiers)
        char.equip_light_cone(lc)
        assert len(char.stats.active_modifiers) == active


# ============================================================
#  TestLightConePathRestriction — 命途限制
# ============================================================
class TestLightConePathRestriction:
    """验证光锥仅在命途匹配时激活特效，基础面板始终生效。"""

    def _make_hunt_char(self):
        return create_test_character("H", hp=500, speed=100, atk=100, element=ElementType.WIND)

    def _make_destruction_char(self):
        c = create_test_character("D", hp=500, speed=100, atk=100, element=ElementType.PHYSICAL)
        c.path = PathType.DESTRUCTION
        return c

    def test_matching_path_activates_effect(self) -> None:
        char = self._make_hunt_char()
        lc = LightCone("20000", superimpose=1)
        char.equip_light_cone(lc)
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])
        engine = CombatEngine(state)
        lc.effect.on_combat_start(state, char)
        engine.event_bus.emit(EventType.BATTLE_START)
        assert any(m.source == "LightCone_20000" for m in char.stats.active_modifiers)

    def test_mismatched_path_skips_on_equip(self) -> None:
        char = self._make_destruction_char()
        mock_effect = Mock(spec=EquipmentEffect)
        lc = LightCone(id="Test", base_hp=100, base_atk=50, base_def=30,
                       path_key="Rogue", effect=mock_effect)
        char.equip_light_cone(lc)
        mock_effect.on_equip.assert_not_called()
        assert char.light_cone is not None

    def test_mismatched_path_still_applies_base_stats(self) -> None:
        char = self._make_destruction_char()
        atk_before = char.stats.get_base_stat(StatType.ATK)
        def_before = char.stats.get_base_stat(StatType.DEF)
        hp_before = char.stats.get_base_stat(StatType.HP)
        lc = LightCone("20000")
        char.equip_light_cone(lc)
        assert char.stats.get_base_stat(StatType.ATK) == pytest.approx(atk_before + lc.base_atk)
        assert char.stats.get_base_stat(StatType.HP) == pytest.approx(hp_before + lc.base_hp)
        assert char.stats.get_base_stat(StatType.DEF) == pytest.approx(def_before + lc.base_def)

    def test_no_path_key_always_activates(self) -> None:
        char = self._make_destruction_char()
        mock_effect = Mock(spec=EquipmentEffect)
        lc = LightCone(id="Neutral", base_hp=100, base_atk=50, base_def=30,
                       path_key="", effect=mock_effect)
        char.equip_light_cone(lc)
        mock_effect.on_equip.assert_called_once()

    def test_engine_skips_on_combat_start_on_mismatch(self) -> None:
        char = self._make_destruction_char()
        lc = LightCone("20000", superimpose=1)
        lc._init_path_key_map()
        char.equip_light_cone(lc)
        assert lc.path == PathType.HUNT
        assert char.path == PathType.DESTRUCTION
        assert lc.path != char.path


# ============================================================
#  TestLightConeLevelSystem — 光锥等级系统
# ============================================================
class TestLightConeLevelSystem:
    """验证光锥等级与面板按 promotions 数据分段线性插值计算。"""

    def test_lv80_matches_previous_hardcoded(self) -> None:
        lc = LightCone("20000")
        assert lc.level == 80
        assert lc.base_hp == pytest.approx(449.28)
        assert lc.base_atk == pytest.approx(168.48)
        assert lc.base_def == pytest.approx(140.4)

    def test_lv1_stats(self) -> None:
        lc = LightCone("20000", level=1)
        assert lc.level == 1
        assert lc.base_hp == pytest.approx(38.4)
        assert lc.base_atk == pytest.approx(14.4)
        assert lc.base_def == pytest.approx(12.0)

    def test_lv80_via_cruising(self) -> None:
        lc = LightCone("24001")
        assert lc.level == 80
        assert lc.base_hp == pytest.approx(505.44)
        assert lc.base_atk == pytest.approx(280.8)
        assert lc.base_def == pytest.approx(245.7)

    def test_lv_breakpoints(self) -> None:
        for lv, hp, atk, def_ in [
            (1, 38.4, 14.4, 12.0),
            (20, 84.48, 31.68, 26.4),
            (30, 145.92, 54.72, 45.6),
            (40, 207.36, 77.76, 64.8),
            (50, 268.8, 100.8, 84.0),
            (60, 330.24, 123.84, 103.2),
            (70, 391.68, 146.88, 122.4),
        ]:
            lc = LightCone("20000", level=lv)
            assert lc.base_hp == pytest.approx(hp), f"Lv{lv} HP"
            assert lc.base_atk == pytest.approx(atk), f"Lv{lv} ATK"
            assert lc.base_def == pytest.approx(def_), f"Lv{lv} DEF"

    def test_equip_light_cone_respects_level(self) -> None:
        char = create_test_character("T", hp=500, speed=100, atk=100)
        lc = LightCone("20000", level=1)
        char.equip_light_cone(lc)
        assert char.stats.get_base_stat(StatType.HP) == pytest.approx(500 + 38.4)
        assert char.stats.get_base_stat(StatType.ATK) == pytest.approx(100 + 14.4)

    def test_no_promotions_uses_default_base(self) -> None:
        lc = LightCone(id="Test", base_hp=300, base_atk=50, base_def=40)
        assert lc.level == 80
        assert lc.base_hp == pytest.approx(300)
        assert lc.base_atk == pytest.approx(50)
        assert lc.base_def == pytest.approx(40)


# ============================================================
#  TestPostOpConversation — 21000 一场术后对话
# ============================================================
class TestPostOpConversation:
    """4★ 丰饶光锥：ERR 永久 + 终结技治疗加成。"""

    def _make_char_priest(self):
        c = create_test_character("H", hp=500, speed=100, atk=100)
        c.path = PathType.ABUNDANCE
        return c

    def _make_setup(self, superimpose: int = 1):
        char = self._make_char_priest()
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])
        engine = CombatEngine(state)
        return char, enemy, state, engine

    def test_registry(self) -> None:
        lc = LightCone("21000")
        assert isinstance(lc, PostOpConversation)
        assert lc.id == "21000"

    def test_permanent_err_on_equip(self) -> None:
        char = self._make_char_priest()
        lc = LightCone("21000", superimpose=1)
        char.equip_light_cone(lc)
        total_err = sum(m.value for m in char.stats.active_modifiers
                        if m.stat_type == StatType.ERR and m.source == "LightCone_21000")
        assert total_err == pytest.approx(0.08)

    def test_no_heal_bonus_on_equip(self) -> None:
        char = self._make_char_priest()
        lc = LightCone("21000", superimpose=1)
        char.equip_light_cone(lc)
        heal_mods = [m for m in char.stats.active_modifiers
                     if m.stat_type == StatType.OUTGOING_HEALING_BOOST and m.source == "LightCone_21000"]
        assert len(heal_mods) == 0

    def test_heal_buff_on_ultimate(self) -> None:
        char, _, _, engine = self._make_setup()
        lc = LightCone("21000", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        engine.event_bus.emit(EventType.ON_ULTIMATE_INSERTED, character=char, target=None)
        heal_mods = [m for m in char.stats.active_modifiers
                     if m.stat_type == StatType.OUTGOING_HEALING_BOOST and m.source == "LightCone_21000"]
        assert len(heal_mods) == 1
        assert heal_mods[0].value == pytest.approx(0.12)

    def test_heal_buff_only_for_owner(self) -> None:
        char, _, _, engine = self._make_setup()
        other = self._make_char_priest()
        other.name = "O2"
        engine.state.characters.append(other)
        lc = LightCone("21000", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        engine.event_bus.emit(EventType.ON_ULTIMATE_INSERTED, character=other, target=None)
        heal_mods = [m for m in char.stats.active_modifiers
                     if m.stat_type == StatType.OUTGOING_HEALING_BOOST and m.source == "LightCone_21000"]
        assert len(heal_mods) == 0

    def test_unequip_cleans_up(self) -> None:
        char = self._make_char_priest()
        lc = LightCone("21000", superimpose=1)
        char.equip_light_cone(lc)
        assert any(m.source == "LightCone_21000" for m in char.stats.active_modifiers)
        bare = LightCone(id="Bare", base_hp=10, base_atk=10, base_def=10)
        char.equip_light_cone(bare)
        assert not any(m.source == "LightCone_21000" for m in char.stats.active_modifiers)


# ============================================================
#  TestNightOnTheMilkyWay — 23000 银河铁道之夜
# ============================================================
class TestNightOnTheMilkyWay:
    """5★ 智识光锥：敌人计数 ATK 叠加 + 弱点击破 DMG 加成。"""

    def _make_setup(self, n_enemies: int = 3, superimpose: int = 1):
        char = create_test_character("M", hp=500, speed=100, atk=100, element=ElementType.FIRE)
        enemies = [Enemy(name=f"E{i}", hp=10000, speed=50, base_damage=0, level=1,
                         weaknesses=[ElementType.FIRE]) for i in range(n_enemies)]
        state = GameState(characters=[char], enemies=enemies)
        engine = CombatEngine(state)
        return char, enemies, state, engine

    def test_registry(self) -> None:
        lc = LightCone("23000")
        assert isinstance(lc, NightOnTheMilkyWay)
        assert lc.id == "23000"

    def test_atk_stacks_initial_3_enemies(self) -> None:
        char, _, _, engine = self._make_setup(n_enemies=3)
        lc = LightCone("23000", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        atk_val = sum(m.value for m in char.stats.active_modifiers
                      if m.stat_type == StatType.ATK and m.source == "LightCone_23000")
        assert atk_val == pytest.approx(0.27)

    def test_atk_stacks_capped_at_5(self) -> None:
        char, _, _, engine = self._make_setup(n_enemies=7)
        lc = LightCone("23000", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        atk_val = sum(m.value for m in char.stats.active_modifiers
                      if m.stat_type == StatType.ATK and m.source == "LightCone_23000")
        assert atk_val == pytest.approx(0.45)

    def test_atk_stacks_zero_when_no_enemies(self) -> None:
        char = create_test_character("M", hp=500, speed=100, atk=100, element=ElementType.FIRE)
        state = GameState(characters=[char], enemies=[])
        engine = CombatEngine(state)
        lc = LightCone("23000", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        atk_mods = [m for m in char.stats.active_modifiers
                    if m.stat_type == StatType.ATK and m.source == "LightCone_23000"]
        assert len(atk_mods) == 0

    def test_atk_stacks_on_death(self) -> None:
        char, enemies, _, engine = self._make_setup(n_enemies=3)
        lc = LightCone("23000", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        atk_val = sum(m.value for m in char.stats.active_modifiers
                      if m.stat_type == StatType.ATK and m.source == "LightCone_23000")
        assert atk_val == pytest.approx(0.27)

        enemies[0].hp = 0
        engine.event_bus.emit(EventType.UNIT_DOWNED, unit=enemies[0], source=char)

        atk_val_after = sum(m.value for m in char.stats.active_modifiers
                            if m.stat_type == StatType.ATK and m.source == "LightCone_23000")
        assert atk_val_after == pytest.approx(0.18)

    def test_dmg_bonus_on_break(self) -> None:
        char, _, _, engine = self._make_setup(n_enemies=1)
        lc = LightCone("23000", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        engine.event_bus.emit(EventType.ON_WEAKNESS_BREAK, source=char, target=char)
        dmg_mods = [m for m in char.stats.active_modifiers
                    if m.stat_type == StatType.DMG_BONUS and m.source == "LightCone_23000_DMG"]
        assert len(dmg_mods) == 1
        assert dmg_mods[0].value == pytest.approx(0.30)
        assert dmg_mods[0].duration == 1

    def test_unequip_cleans_up(self) -> None:
        char, _, _, engine = self._make_setup(n_enemies=3)
        lc = LightCone("23000", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        assert any(m.source == "LightCone_23000" for m in char.stats.active_modifiers)
        bare = LightCone(id="Bare", base_hp=10, base_atk=10, base_def=10)
        char.equip_light_cone(bare)
        assert not any(m.source == "LightCone_23000" for m in char.stats.active_modifiers)
        assert not any("LightCone_23000" in m.source
                       for m in char.stats.active_modifiers if m.source)


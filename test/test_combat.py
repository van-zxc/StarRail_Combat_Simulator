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

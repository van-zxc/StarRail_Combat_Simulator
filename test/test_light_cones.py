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
from entities.light_cones.darting_arrow import DartingArrow, DartingArrowEffect
from entities.light_cones.adversarial import Adversarial, AdversarialEffect
from entities.light_cones.sagacity import Sagacity, SagacityEffect
from entities.light_cones.defense import Defense, DefenseEffect
from entities.light_cones.pioneering import Pioneering, PioneeringEffect
from entities.light_cones.fine_fruit import FineFruit, FineFruitEffect
from entities.light_cones.mediation import Mediation, MediationEffect
from entities.light_cones.mutual_demise import MutualDemise, MutualDemiseEffect
from entities.light_cones.multiplication import Multiplication, MultiplicationEffect
from entities.light_cones.collapsing_sky import CollapsingSky, CollapsingSkyEffect
from entities.light_cones.loop import Loop, LoopEffect
from entities.light_cones.meshing_cogs import MeshingCogs, MeshingCogsEffect
from entities.light_cones.passkey import Passkey, PasskeyEffect
from entities.light_cones.hidden_shadow import HiddenShadow, HiddenShadowEffect
from entities.light_cones.cruising import Cruising, CruisingEffect
from entities.light_cones.before_dawn import BeforeDawn, BeforeDawnEffect
from entities.light_cones.but_battle_isnt_over import ButBattleIsntOver, ButBattleIsntOverEffect
from entities.light_cones.landaus_choice import LandausChoice, LandausChoiceEffect
from entities.light_cones.nwhere_to_run import NowhereToRun, NowhereToRunEffect
from entities.light_cones.only_silence_remains import OnlySilenceRemains, OnlySilenceRemainsEffect
from entities.light_cones.make_world_clamor import MakeWorldClamor, MakeWorldClamorEffect
from entities.light_cones.memories_of_the_past import MemoriesOfThePast, MemoriesOfThePastEffect
from entities.light_cones.planetary_rendezvous import PlanetaryRendezvous, PlanetaryRendezvousEffect
from entities.light_cones.quid_pro_quo import QuidProQuo, QuidProQuoEffect
from entities.light_cones.return_to_darkness import ReturnToDarkness, ReturnToDarknessEffect
from entities.light_cones.past_and_future import PastAndFuture, PastAndFutureEffect
from entities.light_cones.river_flows_in_spring import RiverFlowsInSpring, RiverFlowsInSpringEffect
from entities.light_cones.perfect_timing import PerfectTiming, PerfectTimingEffect
from entities.light_cones.resolution_shines import ResolutionShines, ResolutionShinesEffect
from entities.light_cones.shared_feeling import SharedFeeling, SharedFeelingEffect
from entities.light_cones.seriousness_of_breakfast import SeriousnessOfBreakfast, SeriousnessOfBreakfastEffect
from entities.light_cones.under_the_blue_sky import UnderTheBlueSky, UnderTheBlueSkyEffect
from entities.light_cones.warmth_shortens_cold_nights import WarmthShortensColdNights, WarmthShortensColdNightsEffect
from entities.light_cones.woof_walk_time import WoofWalkTime, WoofWalkTimeEffect
from entities.light_cones.birth_of_the_self import BirthOfTheSelf, BirthOfTheSelfEffect
from entities.light_cones.subscribe_for_more import SubscribeForMore, SubscribeForMoreEffect
from entities.light_cones.we_are_wildfire import WeAreWildfire, WeAreWildfireEffect
from entities.light_cones.moles_welcome_you import MolesWelcomeYou, MolesWelcomeYouEffect
from entities.light_cones.we_will_meet_again import WeWillMeetAgain, WeWillMeetAgainEffect
from entities.light_cones.today_is_peaceful import TodayIsPeaceful, TodayIsPeacefulEffect
from entities.light_cones.trend_universal_market import TrendUniversalMarket, TrendUniversalMarketEffect
from entities.light_cones.swordplay import Swordplay, SwordplayEffect
from entities.light_cones.this_is_me import ThisIsMe, ThisIsMeEffect
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
                        if m.stat_type == StatType.ERR and m.source == "LightCone_21000_ERR")
        assert total_err == pytest.approx(0.08)

    def test_no_heal_bonus_on_equip(self) -> None:
        char = self._make_char_priest()
        lc = LightCone("21000", superimpose=1)
        char.equip_light_cone(lc)
        heal_mods = [m for m in char.stats.active_modifiers
                     if m.stat_type == StatType.OUTGOING_HEALING_BOOST and m.source == "LightCone_21000_HEAL"]
        assert len(heal_mods) == 0

    def test_heal_buff_on_ultimate(self) -> None:
        char, _, _, engine = self._make_setup()
        lc = LightCone("21000", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        engine.event_bus.emit(EventType.ON_ULTIMATE_INSERTED, character=char, target=None)
        heal_mods = [m for m in char.stats.active_modifiers
                     if m.stat_type == StatType.OUTGOING_HEALING_BOOST and m.source == "LightCone_21000_HEAL"]
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
                     if m.stat_type == StatType.OUTGOING_HEALING_BOOST and m.source == "LightCone_21000_HEAL"]
        assert len(heal_mods) == 0

    def test_unequip_cleans_up(self) -> None:
        char = self._make_char_priest()
        lc = LightCone("21000", superimpose=1)
        char.equip_light_cone(lc)
        assert any(m.source in ("LightCone_21000_ERR", "LightCone_21000_HEAL") for m in char.stats.active_modifiers)
        bare = LightCone(id="Bare", base_hp=10, base_atk=10, base_def=10)
        char.equip_light_cone(bare)
        assert not any(m.source in ("LightCone_21000_ERR", "LightCone_21000_HEAL") for m in char.stats.active_modifiers)


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


# ============================================================
#  TestCollateral — 20001 物穰 (3★ 丰饶)
# ============================================================


class TestCollateral:
    """验证 3★ 丰饶光锥 物穰 的注册、面板、特效与清理。"""

    def test_registry_routes_20001_to_collateral(self) -> None:
        lc = LightCone("20001")
        assert isinstance(lc, Collateral)
        assert lc.id == "20001"
        assert lc.name == "物穰"

    def test_default_stats_lv80(self) -> None:
        lc = LightCone("20001")
        assert lc.base_hp == pytest.approx(505.44)
        assert lc.base_atk == pytest.approx(140.4)
        assert lc.base_def == pytest.approx(140.4)

    def test_superimpose_default_s1(self) -> None:
        lc = LightCone("20001")
        assert lc.superimpose == 1
        assert lc.effect is not None
        assert lc.effect.superimpose == 1

    def test_superimpose_s5(self) -> None:
        lc = LightCone("20001", superimpose=5)
        assert lc.superimpose == 5
        assert lc.effect.superimpose == 5

    def test_effect_params_s1(self) -> None:
        e = CollateralEffect(superimpose=1)
        assert e._PARAMS[0][0] == pytest.approx(0.12)

    def test_effect_params_s5(self) -> None:
        e = CollateralEffect(superimpose=5)
        assert e._PARAMS[4][0] == pytest.approx(0.24)

    def test_on_equip_no_permanent_bonus(self) -> None:
        char = create_test_character("T", hp=500, speed=100, atk=100, crit_rate=0.05)
        e = CollateralEffect(superimpose=1)
        heal_before = char.stats.get_total_stat(StatType.OUTGOING_HEALING_BOOST)
        e.on_equip(char)
        assert char.stats.get_total_stat(StatType.OUTGOING_HEALING_BOOST) == pytest.approx(heal_before)

    def test_on_combat_start_subscribes_to_action_start(self) -> None:
        char = create_test_character("T", hp=500, speed=100, atk=100, crit_rate=0.05)
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])

        lc = LightCone("20001", superimpose=1)
        char.equip_light_cone(lc)
        engine = CombatEngine(state)

        char.light_cone.effect.on_combat_start(state, char)

        heal_before = char.stats.get_total_stat(StatType.OUTGOING_HEALING_BOOST)
        engine.event_bus.emit(EventType.ACTION_START, unit=char, target=enemy,
                               action_type=ActionType.SKILL)
        assert char.stats.get_total_stat(StatType.OUTGOING_HEALING_BOOST) > heal_before

    def test_basic_attack_triggers_no_buff(self) -> None:
        char = create_test_character("T", hp=500, speed=100, atk=100, crit_rate=0.05)
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])

        lc = LightCone("20001", superimpose=1)
        char.equip_light_cone(lc)
        engine = CombatEngine(state)

        char.light_cone.effect.on_combat_start(state, char)

        mods_before = len(char.stats.active_modifiers)
        engine.event_bus.emit(EventType.ACTION_START, unit=char, target=enemy,
                               action_type=ActionType.BASIC_ATTACK)
        assert len(char.stats.active_modifiers) == mods_before

    def test_ultimate_triggers_buff(self) -> None:
        char = create_test_character("T", hp=500, speed=100, atk=100, crit_rate=0.05)
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])

        lc = LightCone("20001", superimpose=1)
        char.equip_light_cone(lc)
        engine = CombatEngine(state)

        char.light_cone.effect.on_combat_start(state, char)

        heal_before = char.stats.get_total_stat(StatType.OUTGOING_HEALING_BOOST)
        engine.event_bus.emit(EventType.ACTION_START, unit=char, target=enemy,
                               action_type=ActionType.ULTIMATE)
        assert char.stats.get_total_stat(StatType.OUTGOING_HEALING_BOOST) > heal_before

    def test_unequip_removes_buff(self) -> None:
        char = create_test_character("T", hp=500, speed=100, atk=100, crit_rate=0.05)
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])

        lc = LightCone("20001", superimpose=1)
        char.equip_light_cone(lc)
        engine = CombatEngine(state)

        char.light_cone.effect.on_combat_start(state, char)
        engine.event_bus.emit(EventType.ACTION_START, unit=char, target=enemy,
                               action_type=ActionType.SKILL)
        assert any(m.source == "LightCone_20001" for m in char.stats.active_modifiers)

        char.equip_light_cone(LightCone(id="Empty", base_hp=10, base_atk=10, base_def=10))
        assert not any(m.source == "LightCone_20001" for m in char.stats.active_modifiers)


# ============================================================
#  TestSkyfall — 20002 天倾 (3★ 毁灭)
# ============================================================


class TestSkyfall:
    """验证 3★ 毁灭光锥 天倾 的注册、面板、特效与清理。"""

    def test_registry_routes_20002_to_skyfall(self) -> None:
        lc = LightCone("20002")
        assert isinstance(lc, Skyfall)
        assert lc.id == "20002"
        assert lc.name == "天倾"

    def test_default_stats_lv80(self) -> None:
        lc = LightCone("20002")
        assert lc.base_hp == pytest.approx(449.28)
        assert lc.base_atk == pytest.approx(196.56)
        assert lc.base_def == pytest.approx(105.3)

    def test_superimpose_default_s1(self) -> None:
        lc = LightCone("20002")
        assert lc.superimpose == 1
        assert lc.effect.superimpose == 1

    def test_effect_params_s1(self) -> None:
        e = SkyfallEffect(superimpose=1)
        assert e._PARAMS[0][0] == pytest.approx(0.20)

    def test_effect_params_s5(self) -> None:
        e = SkyfallEffect(superimpose=5)
        assert e._PARAMS[4][0] == pytest.approx(0.40)

    def test_on_equip_boosts_basic_and_skill_dmg(self) -> None:
        char = create_test_character("T", hp=500, speed=100, atk=100, crit_rate=0.05)
        e = SkyfallEffect(superimpose=1)
        e.on_equip(char)
        assert char.stats.get_total_stat(StatType.BASIC_ATK_DMG) == pytest.approx(0.20)
        assert char.stats.get_total_stat(StatType.SKILL_DMG) == pytest.approx(0.20)

    def test_superimpose_s5_boosts_more(self) -> None:
        char = create_test_character("T", hp=500, speed=100, atk=100, crit_rate=0.05)
        e = SkyfallEffect(superimpose=5)
        e.on_equip(char)
        assert char.stats.get_total_stat(StatType.BASIC_ATK_DMG) == pytest.approx(0.40)
        assert char.stats.get_total_stat(StatType.SKILL_DMG) == pytest.approx(0.40)

    def test_unequip_removes_buff(self) -> None:
        char = create_test_character("T", hp=500, speed=100, atk=100, crit_rate=0.05)
        e = SkyfallEffect(superimpose=1)
        e.on_equip(char)
        assert char.stats.get_total_stat(StatType.BASIC_ATK_DMG) == pytest.approx(0.20)
        e.on_unequip(char)
        assert char.stats.get_total_stat(StatType.BASIC_ATK_DMG) == pytest.approx(0.0)
        assert char.stats.get_total_stat(StatType.SKILL_DMG) == pytest.approx(0.0)


# ============================================================
#  TestAmber — 20003 琥珀 (3★ 存护)
# ============================================================


class TestAmber:
    """验证 3★ 存护光锥 琥珀 的注册、面板、条件DEF特效与清理。"""

    def test_registry_routes_20003_to_amber(self) -> None:
        lc = LightCone("20003")
        assert isinstance(lc, Amber)
        assert lc.id == "20003"
        assert lc.name == "琥珀"

    def test_default_stats_lv80(self) -> None:
        lc = LightCone("20003")
        assert lc.base_hp == pytest.approx(449.28)
        assert lc.base_atk == pytest.approx(140.4)
        assert lc.base_def == pytest.approx(175.5)

    def test_superimpose_default_s1(self) -> None:
        lc = LightCone("20003")
        assert lc.superimpose == 1
        assert lc.effect.superimpose == 1

    def test_effect_params_s1(self) -> None:
        e = AmberEffect(superimpose=1)
        assert e._PARAMS[0][0] == pytest.approx(0.16)
        assert e._PARAMS[0][1] == pytest.approx(0.50)
        assert e._PARAMS[0][2] == pytest.approx(0.16)

    def test_on_equip_boosts_def(self) -> None:
        char = create_test_character("T", hp=500, speed=100, atk=100, crit_rate=0.05)
        def_before = char.stats.get_total_stat(StatType.DEF)
        e = AmberEffect(superimpose=1)
        e.on_equip(char)
        assert char.stats.get_total_stat(StatType.DEF) > def_before

    def test_conditional_def_not_active_initially(self) -> None:
        char = create_test_character("T", hp=500, speed=100, atk=100, crit_rate=0.05)
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])

        lc = LightCone("20003", superimpose=1)
        char.equip_light_cone(lc)
        engine = CombatEngine(state)

        def_before = char.stats.get_total_stat(StatType.DEF)
        char.light_cone.effect.on_combat_start(state, char)

        assert not any(m.source == "LightCone_20003_COND" for m in char.stats.active_modifiers)

    def test_hp_below_threshold_adds_cond_def(self) -> None:
        char = create_test_character("T", hp=500, speed=100, atk=100, crit_rate=0.05)
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])

        lc = LightCone("20003", superimpose=1)
        char.equip_light_cone(lc)
        engine = CombatEngine(state)

        char.light_cone.effect.on_combat_start(state, char)

        assert not any(m.source == "LightCone_20003_COND" for m in char.stats.active_modifiers)

        char.hp = int(char.max_hp * 0.4)
        engine.event_bus.emit(EventType.ON_DAMAGE_DEALT, source=enemy, target=char,
                               damage=50, damage_type=DamageType.DIRECT)

        assert any(m.source == "LightCone_20003_COND" for m in char.stats.active_modifiers)

    def test_hp_above_threshold_removes_cond_def(self) -> None:
        char = create_test_character("T", hp=500, speed=100, atk=100, crit_rate=0.05)
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])

        lc = LightCone("20003", superimpose=1)
        char.equip_light_cone(lc)
        engine = CombatEngine(state)

        char.light_cone.effect.on_combat_start(state, char)

        char.hp = int(char.max_hp * 0.4)
        engine.event_bus.emit(EventType.ON_DAMAGE_DEALT, source=enemy, target=char,
                               damage=50, damage_type=DamageType.DIRECT)
        assert any(m.source == "LightCone_20003_COND" for m in char.stats.active_modifiers)

        char.hp = int(char.max_hp * 0.7)
        engine.event_bus.emit(EventType.HEAL_DONE, healer=char, target=char, amount=300)
        assert not any(m.source == "LightCone_20003_COND" for m in char.stats.active_modifiers)

    def test_other_target_events_not_affect(self) -> None:
        char = create_test_character("T", hp=500, speed=100, atk=100, crit_rate=0.05)
        enemy1 = Enemy(name="E1", hp=10000, speed=50, base_damage=0, level=1,
                        weaknesses=[ElementType.PHYSICAL])
        enemy2 = Enemy(name="E2", hp=10000, speed=50, base_damage=0, level=1,
                        weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy1, enemy2])

        lc = LightCone("20003", superimpose=1)
        char.equip_light_cone(lc)
        engine = CombatEngine(state)

        char.light_cone.effect.on_combat_start(state, char)

        enemy1.hp = 100
        engine.event_bus.emit(EventType.ON_DAMAGE_DEALT, source=char, target=enemy1,
                               damage=50, damage_type=DamageType.DIRECT)
        assert not any(m.source == "LightCone_20003_COND" for m in char.stats.active_modifiers)

    def test_unequip_removes_all_def_buffs(self) -> None:
        char = create_test_character("T", hp=500, speed=100, atk=100, crit_rate=0.05)
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])

        def_before = char.stats.get_total_stat(StatType.DEF)

        lc = LightCone("20003", superimpose=1)
        char.equip_light_cone(lc)
        engine = CombatEngine(state)

        assert char.stats.get_total_stat(StatType.DEF) > def_before
        char.light_cone.effect.on_combat_start(state, char)

        char.hp = int(char.max_hp * 0.4)
        engine.event_bus.emit(EventType.ON_DAMAGE_DEALT, source=enemy, target=char,
                               damage=50, damage_type=DamageType.DIRECT)
        assert any(m.source == "LightCone_20003_COND" for m in char.stats.active_modifiers)

        char.equip_light_cone(LightCone(id="Empty", base_hp=10, base_atk=10, base_def=10))
        assert not any(m.source.startswith("LightCone_20003") for m in char.stats.active_modifiers)


# ============================================================
#  TestDeepDark — 20004 幽邃 (3★ 虚无)
# ============================================================


class TestDeepDark:
    """验证 3★ 虚无光锥 幽邃 的注册、面板、BATTLE_START特效与清理。"""

    def test_registry_routes_20004_to_deepdark(self) -> None:
        lc = LightCone("20004")
        assert isinstance(lc, DeepDark)
        assert lc.id == "20004"
        assert lc.name == "幽邃"

    def test_default_stats_lv80(self) -> None:
        lc = LightCone("20004")
        assert lc.base_hp == pytest.approx(449.28)
        assert lc.base_atk == pytest.approx(168.48)
        assert lc.base_def == pytest.approx(140.4)

    def test_superimpose_default_s1(self) -> None:
        lc = LightCone("20004")
        assert lc.superimpose == 1
        assert lc.effect.superimpose == 1

    def test_effect_params_s1(self) -> None:
        e = DeepDarkEffect(superimpose=1)
        assert e._PARAMS[0][0] == pytest.approx(0.20)
        assert e._PARAMS[0][1] == 3

    def test_effect_params_s5(self) -> None:
        e = DeepDarkEffect(superimpose=5)
        assert e._PARAMS[4][0] == pytest.approx(0.40)
        assert e._PARAMS[4][1] == 3

    def test_on_equip_no_permanent_bonus(self) -> None:
        char = create_test_character("T", hp=500, speed=100, atk=100, crit_rate=0.05)
        e = DeepDarkEffect(superimpose=1)
        ehr_before = char.stats.get_total_stat(StatType.EFFECT_HIT_RATE)
        e.on_equip(char)
        assert char.stats.get_total_stat(StatType.EFFECT_HIT_RATE) == pytest.approx(ehr_before)

    def test_on_combat_start_grants_ehr_for_3_turns(self) -> None:
        char = create_test_character("T", hp=500, speed=100, atk=100, crit_rate=0.05)
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])

        lc = LightCone("20004", superimpose=1)
        char.equip_light_cone(lc)
        engine = CombatEngine(state)

        ehr_before = char.stats.get_total_stat(StatType.EFFECT_HIT_RATE)
        char.light_cone.effect.on_combat_start(state, char)
        engine.event_bus.emit(EventType.BATTLE_START)

        assert char.stats.get_total_stat(StatType.EFFECT_HIT_RATE) > ehr_before
        total_ehr = sum(
            m.value for m in char.stats.active_modifiers
            if m.source == "LightCone_20004"
        )
        assert total_ehr == pytest.approx(0.20)

    def test_buff_expires_after_3_character_actions(self) -> None:
        char = create_test_character("T", hp=500, speed=100, atk=100, crit_rate=0.05)
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])

        lc = LightCone("20004", superimpose=1)
        char.equip_light_cone(lc)
        engine = CombatEngine(state)

        char.light_cone.effect.on_combat_start(state, char)
        engine.event_bus.emit(EventType.BATTLE_START)

        mods = lambda: [m for m in char.stats.active_modifiers
                        if m.source == "LightCone_20004"]
        assert len(mods()) == 1
        assert mods()[0].duration == 3

        engine._decrement_modifiers(unit=char)
        assert mods()[0].duration == 2

        engine._decrement_modifiers(unit=char)
        assert mods()[0].duration == 1

        engine._decrement_modifiers(unit=char)
        assert len(mods()) == 0

    def test_unequip_removes_buff(self) -> None:
        char = create_test_character("T", hp=500, speed=100, atk=100, crit_rate=0.05)
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])

        lc = LightCone("20004", superimpose=1)
        char.equip_light_cone(lc)
        engine = CombatEngine(state)

        char.light_cone.effect.on_combat_start(state, char)
        engine.event_bus.emit(EventType.BATTLE_START)
        assert any(m.source == "LightCone_20004" for m in char.stats.active_modifiers)

        char.equip_light_cone(LightCone(id="Empty", base_hp=10, base_atk=10, base_def=10))
        assert not any(m.source == "LightCone_20004" for m in char.stats.active_modifiers)


# ============================================================
#  TestChorus — 20005 齐颂 (3★ 同谐)
# ============================================================


class TestChorus:
    """验证 3★ 同谐光锥 齐颂 的注册、面板、全队ATK特效与清理。"""

    def test_registry_routes_20005_to_chorus(self) -> None:
        lc = LightCone("20005")
        assert isinstance(lc, Chorus)
        assert lc.id == "20005"
        assert lc.name == "齐颂"

    def test_default_stats_lv80(self) -> None:
        lc = LightCone("20005")
        assert lc.base_hp == pytest.approx(449.28)
        assert lc.base_atk == pytest.approx(168.48)
        assert lc.base_def == pytest.approx(140.4)

    def test_superimpose_default_s1(self) -> None:
        lc = LightCone("20005")
        assert lc.superimpose == 1
        assert lc.effect.superimpose == 1

    def test_effect_params_s1(self) -> None:
        e = ChorusEffect(superimpose=1)
        assert e._PARAMS[0][0] == pytest.approx(0.08)

    def test_effect_params_s5(self) -> None:
        e = ChorusEffect(superimpose=5)
        assert e._PARAMS[4][0] == pytest.approx(0.12)

    def test_on_combat_start_grants_atk_to_all_characters(self) -> None:
        char1 = create_test_character("T1", hp=500, speed=100, atk=100, crit_rate=0.05)
        char2 = create_test_character("T2", hp=500, speed=100, atk=100, crit_rate=0.05)
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char1, char2], enemies=[enemy])

        lc = LightCone("20005", superimpose=1)
        char1.equip_light_cone(lc)
        engine = CombatEngine(state)

        char1.light_cone.effect.on_combat_start(state, char1)
        atk_before_c1 = char1.stats.get_total_stat(StatType.ATK)
        atk_before_c2 = char2.stats.get_total_stat(StatType.ATK)

        engine.event_bus.emit(EventType.BATTLE_START)

        assert char1.stats.get_total_stat(StatType.ATK) > atk_before_c1
        assert char2.stats.get_total_stat(StatType.ATK) > atk_before_c2
        atk_mods_1 = [m for m in char1.stats.active_modifiers if m.source == "LightCone_20005"]
        atk_mods_2 = [m for m in char2.stats.active_modifiers if m.source == "LightCone_20005"]
        assert len(atk_mods_1) == 1
        assert len(atk_mods_2) == 1

    def test_multiple_chorus_only_applies_once(self) -> None:
        char1 = create_test_character("T1", hp=500, speed=100, atk=100, crit_rate=0.05)
        char2 = create_test_character("T2", hp=500, speed=100, atk=100, crit_rate=0.05)
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char1, char2], enemies=[enemy])

        lc1 = LightCone("20005", superimpose=1)
        lc2 = LightCone("20005", superimpose=5)
        char1.equip_light_cone(lc1)
        char2.equip_light_cone(lc2)
        engine = CombatEngine(state)

        char1.light_cone.effect.on_combat_start(state, char1)
        engine.event_bus.emit(EventType.BATTLE_START)

        char2.light_cone.effect.on_combat_start(state, char2)
        engine.event_bus.emit(EventType.BATTLE_START)

        atk_mods_1 = [m for m in char1.stats.active_modifiers if m.source == "LightCone_20005"]
        atk_mods_2 = [m for m in char2.stats.active_modifiers if m.source == "LightCone_20005"]
        assert len(atk_mods_1) == 1
        assert len(atk_mods_2) == 1
        assert atk_mods_1[0].value == pytest.approx(0.08)
        assert atk_mods_2[0].value == pytest.approx(0.08)

    def test_unequip_removes_atk_from_wearer(self) -> None:
        char = create_test_character("T", hp=500, speed=100, atk=100, crit_rate=0.05)
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])

        lc = LightCone("20005", superimpose=1)
        char.equip_light_cone(lc)
        engine = CombatEngine(state)

        char.light_cone.effect.on_combat_start(state, char)
        engine.event_bus.emit(EventType.BATTLE_START)
        assert any(m.source == "LightCone_20005" for m in char.stats.active_modifiers)

        char.equip_light_cone(LightCone(id="Empty", base_hp=10, base_atk=10, base_def=10))
        assert not any(m.source == "LightCone_20005" for m in char.stats.active_modifiers)


# ============================================================
#  TestDataBank — 20006 智库 (3★ 智识)
# ============================================================


class TestDataBank:
    """验证 3★ 智识光锥 智库 的注册、面板、ULT_DMG特效与清理。"""

    def test_registry_routes_20006_to_databank(self) -> None:
        lc = LightCone("20006")
        assert isinstance(lc, DataBank)
        assert lc.id == "20006"
        assert lc.name == "智库"

    def test_default_stats_lv80(self) -> None:
        lc = LightCone("20006")
        assert lc.base_hp == pytest.approx(393.12)
        assert lc.base_atk == pytest.approx(196.56)
        assert lc.base_def == pytest.approx(140.4)

    def test_superimpose_default_s1(self) -> None:
        lc = LightCone("20006")
        assert lc.superimpose == 1
        assert lc.effect.superimpose == 1

    def test_effect_params_s1(self) -> None:
        e = DataBankEffect(superimpose=1)
        assert e._PARAMS[0][0] == pytest.approx(0.28)

    def test_effect_params_s5(self) -> None:
        e = DataBankEffect(superimpose=5)
        assert e._PARAMS[4][0] == pytest.approx(0.56)

    def test_on_equip_boosts_ult_dmg(self) -> None:
        char = create_test_character("T", hp=500, speed=100, atk=100, crit_rate=0.05)
        e = DataBankEffect(superimpose=1)
        e.on_equip(char)
        assert char.stats.get_total_stat(StatType.ULT_DMG) == pytest.approx(0.28)

    def test_superimpose_s5_boosts_more(self) -> None:
        char = create_test_character("T", hp=500, speed=100, atk=100, crit_rate=0.05)
        e = DataBankEffect(superimpose=5)
        e.on_equip(char)
        assert char.stats.get_total_stat(StatType.ULT_DMG) == pytest.approx(0.56)

    def test_unequip_removes_buff(self) -> None:
        char = create_test_character("T", hp=500, speed=100, atk=100, crit_rate=0.05)
        e = DataBankEffect(superimpose=1)
        e.on_equip(char)
        assert char.stats.get_total_stat(StatType.ULT_DMG) == pytest.approx(0.28)
        e.on_unequip(char)
        assert char.stats.get_total_stat(StatType.ULT_DMG) == pytest.approx(0.0)


# ============================================================
#  TestDartingArrow — 20007 离弦 (3★ 巡猎)
# ============================================================


class TestDartingArrow:
    """验证 3★ 巡猎光锥 离弦: ON_KILL → ATK% 3回合。"""

    def _make_char(self):
        return create_test_character("T", hp=500, speed=100, atk=100, crit_rate=0.05)

    def _make_setup(self):
        char = self._make_char()
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])
        engine = CombatEngine(state)
        return char, enemy, state, engine

    def test_registry(self):
        lc = LightCone("20007")
        assert isinstance(lc, DartingArrow)
        assert lc.id == "20007"
        assert lc.name == "离弦"

    def test_lv80_stats(self):
        lc = LightCone("20007")
        assert lc.base_hp == pytest.approx(393.12)
        assert lc.base_atk == pytest.approx(196.56)
        assert lc.base_def == pytest.approx(140.4)

    def test_superimpose_default_s1(self):
        lc = LightCone("20007")
        assert lc.superimpose == 1
        assert lc.effect.superimpose == 1

    def test_effect_params_s1(self):
        e = DartingArrowEffect(superimpose=1)
        assert e._PARAMS[0] == pytest.approx(0.24)

    def test_effect_params_s5(self):
        e = DartingArrowEffect(superimpose=5)
        assert e._PARAMS[4] == pytest.approx(0.48)

    def test_on_kill_triggers_atk_buff(self):
        char, _, _, engine = self._make_setup()
        lc = LightCone("20007", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        engine.event_bus.emit(EventType.ON_KILL, source=char, target=None, action_type=ActionType.BASIC_ATTACK)
        atk_mods = [m for m in char.stats.active_modifiers if m.source == "LightCone_20007"]
        assert len(atk_mods) == 1
        assert atk_mods[0].value == pytest.approx(0.24)
        assert atk_mods[0].duration == 3

    def test_other_unit_kill_no_trigger(self):
        char, _, _, engine = self._make_setup()
        other = self._make_char()
        other.name = "O2"
        engine.state.characters.append(other)
        lc = LightCone("20007", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        engine.event_bus.emit(EventType.ON_KILL, source=other, target=None, action_type=ActionType.SKILL)
        assert not any(m.source == "LightCone_20007" for m in char.stats.active_modifiers)

    def test_buff_duration_expires(self):
        char, _, _, engine = self._make_setup()
        lc = LightCone("20007", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        engine.event_bus.emit(EventType.ON_KILL, source=char, target=None, action_type=ActionType.BASIC_ATTACK)
        engine._decrement_modifiers(unit=char)
        engine._decrement_modifiers(unit=char)
        engine._decrement_modifiers(unit=char)
        assert not any(m.source == "LightCone_20007" for m in char.stats.active_modifiers)

    def test_unequip_removes_buff(self):
        char, _, _, engine = self._make_setup()
        lc = LightCone("20007", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        engine.event_bus.emit(EventType.ON_KILL, source=char, target=None, action_type=ActionType.BASIC_ATTACK)
        assert any(m.source == "LightCone_20007" for m in char.stats.active_modifiers)
        char.equip_light_cone(LightCone(id="Bare", base_hp=10, base_atk=10, base_def=10))
        assert not any(m.source == "LightCone_20007" for m in char.stats.active_modifiers)


# ============================================================
#  TestAdversarial — 20014 相抗 (3★ 巡猎)
# ============================================================


class TestAdversarial:
    """验证 3★ 巡猎光锥 相抗: ON_KILL → SPD% 2回合。"""

    def _make_char(self):
        return create_test_character("T", hp=500, speed=100, atk=100, crit_rate=0.05)

    def _make_setup(self):
        char = self._make_char()
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])
        engine = CombatEngine(state)
        return char, enemy, state, engine

    def test_registry(self):
        lc = LightCone("20014")
        assert isinstance(lc, Adversarial)
        assert lc.id == "20014"
        assert lc.name == "相抗"

    def test_lv80_stats(self):
        lc = LightCone("20014")
        assert lc.base_hp == pytest.approx(393.12)
        assert lc.base_atk == pytest.approx(196.56)
        assert lc.base_def == pytest.approx(140.4)

    def test_effect_params_s1(self):
        e = AdversarialEffect(superimpose=1)
        assert e._PARAMS[0] == pytest.approx(0.10)

    def test_effect_params_s5(self):
        e = AdversarialEffect(superimpose=5)
        assert e._PARAMS[4] == pytest.approx(0.18)

    def test_on_kill_triggers_spd_buff(self):
        char, _, _, engine = self._make_setup()
        lc = LightCone("20014", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        spd_before = char.stats.get_total_stat(StatType.SPD)
        engine.event_bus.emit(EventType.ON_KILL, source=char, target=None, action_type=ActionType.BASIC_ATTACK)
        spd_mods = [m for m in char.stats.active_modifiers if m.source == "LightCone_20014"]
        assert len(spd_mods) == 1
        assert spd_mods[0].value == pytest.approx(0.10)
        assert spd_mods[0].duration == 2
        assert char.stats.get_total_stat(StatType.SPD) > spd_before

    def test_buff_duration_expires(self):
        char, _, _, engine = self._make_setup()
        lc = LightCone("20014", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        engine.event_bus.emit(EventType.ON_KILL, source=char, target=None, action_type=ActionType.BASIC_ATTACK)
        engine._decrement_modifiers(unit=char)
        engine._decrement_modifiers(unit=char)
        assert not any(m.source == "LightCone_20014" for m in char.stats.active_modifiers)

    def test_unequip_removes_buff(self):
        char, _, _, engine = self._make_setup()
        lc = LightCone("20014", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        engine.event_bus.emit(EventType.ON_KILL, source=char, target=None, action_type=ActionType.BASIC_ATTACK)
        assert any(m.source == "LightCone_20014" for m in char.stats.active_modifiers)
        char.equip_light_cone(LightCone(id="Bare", base_hp=10, base_atk=10, base_def=10))
        assert not any(m.source == "LightCone_20014" for m in char.stats.active_modifiers)


# ============================================================
#  TestSagacity — 20020 睿见 (3★ 智识)
# ============================================================


class TestSagacity:
    """验证 3★ 智识光锥 睿见: ON_ULTIMATE_INSERTED → ATK% 2回合。"""

    def _make_char(self):
        c = create_test_character("T", hp=500, speed=100, atk=100, crit_rate=0.05)
        c.path = PathType.ERUDITION
        return c

    def _make_setup(self):
        char = self._make_char()
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])
        engine = CombatEngine(state)
        return char, enemy, state, engine

    def test_registry(self):
        lc = LightCone("20020")
        assert isinstance(lc, Sagacity)
        assert lc.id == "20020"
        assert lc.name == "睿见"

    def test_lv80_stats(self):
        lc = LightCone("20020")
        assert lc.base_hp == pytest.approx(393.12)
        assert lc.base_atk == pytest.approx(196.56)
        assert lc.base_def == pytest.approx(140.4)

    def test_effect_params_s1(self):
        e = SagacityEffect(superimpose=1)
        assert e._PARAMS[0] == pytest.approx(0.24)
        assert e._DURATION == 2

    def test_effect_params_s5(self):
        e = SagacityEffect(superimpose=5)
        assert e._PARAMS[4] == pytest.approx(0.48)

    def test_ultimate_triggers_atk_buff(self):
        char, _, _, engine = self._make_setup()
        lc = LightCone("20020", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        atk_before = char.stats.get_total_stat(StatType.ATK)
        engine.event_bus.emit(EventType.ON_ULTIMATE_INSERTED, character=char, target=None)
        atk_mods = [m for m in char.stats.active_modifiers if m.source == "LightCone_20020"]
        assert len(atk_mods) == 1
        assert atk_mods[0].value == pytest.approx(0.24)
        assert char.stats.get_total_stat(StatType.ATK) > atk_before

    def test_other_unit_ult_no_trigger(self):
        char, _, _, engine = self._make_setup()
        other = self._make_char()
        other.name = "O2"
        engine.state.characters.append(other)
        lc = LightCone("20020", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        engine.event_bus.emit(EventType.ON_ULTIMATE_INSERTED, character=other, target=None)
        assert not any(m.source == "LightCone_20020" for m in char.stats.active_modifiers)

    def test_unequip_removes_buff(self):
        char, _, _, engine = self._make_setup()
        lc = LightCone("20020", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        engine.event_bus.emit(EventType.ON_ULTIMATE_INSERTED, character=char, target=None)
        assert any(m.source == "LightCone_20020" for m in char.stats.active_modifiers)
        char.equip_light_cone(LightCone(id="Bare", base_hp=10, base_atk=10, base_def=10))
        assert not any(m.source == "LightCone_20020" for m in char.stats.active_modifiers)


# ============================================================
#  TestDefense — 20010 戍御 (3★ 存护)
# ============================================================


class TestDefense:
    """验证 3★ 存护光锥 戍御: ON_ULTIMATE_INSERTED → heal maxHP%。"""

    def _make_char(self):
        c = create_test_character("T", hp=500, speed=100, atk=100, crit_rate=0.05)
        c.path = PathType.PRESERVATION
        return c

    def _make_setup(self):
        char = self._make_char()
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])
        engine = CombatEngine(state)
        return char, enemy, state, engine

    def test_registry(self):
        lc = LightCone("20010")
        assert isinstance(lc, Defense)
        assert lc.id == "20010"
        assert lc.name == "戍御"

    def test_lv80_stats(self):
        lc = LightCone("20010")
        assert lc.base_hp == pytest.approx(505.44)
        assert lc.base_atk == pytest.approx(140.4)
        assert lc.base_def == pytest.approx(140.4)

    def test_effect_params_s1(self):
        e = DefenseEffect(superimpose=1)
        assert e._PARAMS[0] == pytest.approx(0.18)

    def test_effect_params_s5(self):
        e = DefenseEffect(superimpose=5)
        assert e._PARAMS[4] == pytest.approx(0.30)

    def test_ultimate_heals(self):
        char, _, _, engine = self._make_setup()
        lc = LightCone("20010", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        hp_before = char.hp
        engine.event_bus.emit(EventType.ON_ULTIMATE_INSERTED, character=char, target=None)
        assert char.hp > hp_before

    def test_other_unit_ult_no_heal(self):
        char, _, _, engine = self._make_setup()
        other = self._make_char()
        other.name = "O2"
        engine.state.characters.append(other)
        lc = LightCone("20010", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        hp_before = char.hp
        engine.event_bus.emit(EventType.ON_ULTIMATE_INSERTED, character=other, target=None)
        assert char.hp == hp_before

    def test_superimpose_s5_heals_more(self):
        char, _, _, engine = self._make_setup()
        char.hp = 100
        lc = LightCone("20010", superimpose=5)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        engine.event_bus.emit(EventType.ON_ULTIMATE_INSERTED, character=char, target=None)
        assert char.hp >= 100 + int(500 * 0.30)


# ============================================================
#  TestPioneering — 20017 开疆 (3★ 存护)
# ============================================================


class TestPioneering:
    """验证 3★ 存护光锥 开疆: ON_WEAKNESS_BREAK → heal maxHP%。"""

    def _make_char(self):
        c = create_test_character("T", hp=500, speed=100, atk=100, crit_rate=0.05)
        c.path = PathType.PRESERVATION
        return c

    def _make_setup(self):
        char = self._make_char()
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])
        engine = CombatEngine(state)
        return char, enemy, state, engine

    def test_registry(self):
        lc = LightCone("20017")
        assert isinstance(lc, Pioneering)
        assert lc.id == "20017"
        assert lc.name == "开疆"

    def test_lv80_stats(self):
        lc = LightCone("20017")
        assert lc.base_hp == pytest.approx(505.44)
        assert lc.base_atk == pytest.approx(140.4)
        assert lc.base_def == pytest.approx(140.4)

    def test_effect_params_s1(self):
        e = PioneeringEffect(superimpose=1)
        assert e._PARAMS[0] == pytest.approx(0.12)

    def test_effect_params_s5(self):
        e = PioneeringEffect(superimpose=5)
        assert e._PARAMS[4] == pytest.approx(0.20)

    def test_break_heals(self):
        char, _, _, engine = self._make_setup()
        lc = LightCone("20017", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        hp_before = char.hp
        engine.event_bus.emit(EventType.ON_WEAKNESS_BREAK, source=char, target=None)
        assert char.hp > hp_before

    def test_other_unit_break_no_heal(self):
        char, _, _, engine = self._make_setup()
        other = self._make_char()
        other.name = "O2"
        engine.state.characters.append(other)
        lc = LightCone("20017", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        hp_before = char.hp
        engine.event_bus.emit(EventType.ON_WEAKNESS_BREAK, source=other, target=None)
        assert char.hp == hp_before


# ============================================================
#  TestFineFruit — 20008 嘉果 (3★ 丰饶)
# ============================================================


class TestFineFruit:
    """验证 3★ 丰饶光锥 嘉果: BATTLE_START → team energy。"""

    def _make_char(self):
        c = create_test_character("T", hp=500, speed=100, atk=100, crit_rate=0.05)
        c.path = PathType.ABUNDANCE
        return c

    def test_registry(self):
        lc = LightCone("20008")
        assert isinstance(lc, FineFruit)
        assert lc.id == "20008"
        assert lc.name == "嘉果"

    def test_lv80_stats(self):
        lc = LightCone("20008")
        assert lc.base_hp == pytest.approx(505.44)
        assert lc.base_atk == pytest.approx(168.48)
        assert lc.base_def == pytest.approx(105.3)

    def test_effect_params_s1(self):
        e = FineFruitEffect(superimpose=1)
        assert e._PARAMS[0] == 6

    def test_effect_params_s5(self):
        e = FineFruitEffect(superimpose=5)
        assert e._PARAMS[4] == 12

    def test_battle_start_gives_team_energy(self):
        char1 = self._make_char()
        char2 = self._make_char()
        char2.name = "C2"
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char1, char2], enemies=[enemy])
        engine = CombatEngine(state)
        lc = LightCone("20008", superimpose=1)
        char1.equip_light_cone(lc)
        lc.effect.on_combat_start(state, char1)
        e1_before = char1.energy
        e2_before = char2.energy
        engine.event_bus.emit(EventType.BATTLE_START)
        assert char1.energy > e1_before
        assert char2.energy > e2_before

    def test_superimpose_s5_gives_more_energy(self):
        char1 = self._make_char()
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char1], enemies=[enemy])
        engine = CombatEngine(state)
        lc = LightCone("20008", superimpose=5)
        char1.equip_light_cone(lc)
        lc.effect.on_combat_start(state, char1)
        e_before = char1.energy
        engine.event_bus.emit(EventType.BATTLE_START)
        assert char1.energy >= e_before + 12


# ============================================================
#  TestMediation — 20019 调和 (3★ 同谐)
# ============================================================


class TestMediation:
    """验证 3★ 同谐光锥 调和: BATTLE_START → team SPD 1回合。"""

    def _make_char(self):
        c = create_test_character("T", hp=500, speed=100, atk=100, crit_rate=0.05)
        c.path = PathType.HARMONY
        return c

    def test_registry(self):
        lc = LightCone("20019")
        assert isinstance(lc, Mediation)
        assert lc.id == "20019"
        assert lc.name == "调和"

    def test_lv80_stats(self):
        lc = LightCone("20019")
        assert lc.base_hp == pytest.approx(449.28)
        assert lc.base_atk == pytest.approx(168.48)
        assert lc.base_def == pytest.approx(140.4)

    def test_effect_params_s1(self):
        e = MediationEffect(superimpose=1)
        assert e._PARAMS[0][0] == 12
        assert e._PARAMS[0][1] == 1

    def test_effect_params_s5(self):
        e = MediationEffect(superimpose=5)
        assert e._PARAMS[4][0] == 20

    def test_battle_start_grants_team_spd(self):
        char1 = self._make_char()
        char2 = self._make_char()
        char2.name = "C2"
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char1, char2], enemies=[enemy])
        engine = CombatEngine(state)
        lc = LightCone("20019", superimpose=1)
        char1.equip_light_cone(lc)
        lc.effect.on_combat_start(state, char1)
        engine.event_bus.emit(EventType.BATTLE_START)
        spd_mods_1 = [m for m in char1.stats.active_modifiers if m.source == "LightCone_20019"]
        spd_mods_2 = [m for m in char2.stats.active_modifiers if m.source == "LightCone_20019"]
        assert len(spd_mods_1) == 1
        assert len(spd_mods_2) == 1
        assert spd_mods_1[0].duration == 1
        assert spd_mods_2[0].duration == 1

    def test_spd_expires_after_1_turn(self):
        char1 = self._make_char()
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char1], enemies=[enemy])
        engine = CombatEngine(state)
        lc = LightCone("20019", superimpose=1)
        char1.equip_light_cone(lc)
        lc.effect.on_combat_start(state, char1)
        engine.event_bus.emit(EventType.BATTLE_START)
        assert any(m.source == "LightCone_20019" for m in char1.stats.active_modifiers)
        engine._decrement_modifiers(unit=char1)
        assert not any(m.source == "LightCone_20019" for m in char1.stats.active_modifiers)


# ============================================================
#  TestMutualDemise — 20016 俱殁 (3★ 毁灭)
# ============================================================


class TestMutualDemise:
    """验证 3★ 毁灭光锥 俱殁: HP<80% → CRIT_RATE。"""

    def _make_char(self):
        c = create_test_character("T", hp=500, speed=100, atk=100, crit_rate=0.05)
        c.path = PathType.DESTRUCTION
        return c

    def _make_setup(self):
        char = self._make_char()
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])
        engine = CombatEngine(state)
        return char, enemy, state, engine

    def test_registry(self):
        lc = LightCone("20016")
        assert isinstance(lc, MutualDemise)
        assert lc.id == "20016"
        assert lc.name == "俱殁"

    def test_lv80_stats(self):
        lc = LightCone("20016")
        assert lc.base_hp == pytest.approx(449.28)
        assert lc.base_atk == pytest.approx(196.56)
        assert lc.base_def == pytest.approx(105.3)

    def test_effect_params_s1(self):
        e = MutualDemiseEffect(superimpose=1)
        assert e._PARAMS[0][0] == pytest.approx(0.80)
        assert e._PARAMS[0][1] == pytest.approx(0.12)

    def test_hp_below_threshold_gives_crit(self):
        char, enemy, _, engine = self._make_setup()
        lc = LightCone("20016", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        # max_hp ~949, 80% threshold ~759
        char.hp = 500
        engine.event_bus.emit(EventType.ON_DAMAGE_DEALT, source=enemy, target=char,
                               damage=100, damage_type=DamageType.DIRECT)
        crit_mods = [m for m in char.stats.active_modifiers if m.source == "LightCone_20016"]
        assert len(crit_mods) == 1
        assert crit_mods[0].value == pytest.approx(0.12)

    def test_hp_above_threshold_removes_crit(self):
        char, enemy, _, engine = self._make_setup()
        lc = LightCone("20016", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        char.hp = 500
        engine.event_bus.emit(EventType.ON_DAMAGE_DEALT, source=enemy, target=char,
                               damage=100, damage_type=DamageType.DIRECT)
        assert any(m.source == "LightCone_20016" for m in char.stats.active_modifiers)
        char.hp = char.max_hp
        engine.event_bus.emit(EventType.HEAL_DONE, healer=char, target=char, amount=500)
        assert not any(m.source == "LightCone_20016" for m in char.stats.active_modifiers)

    def test_other_target_events_not_affect(self):
        char, enemy, _, engine = self._make_setup()
        lc = LightCone("20016", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        engine.event_bus.emit(EventType.ON_DAMAGE_DEALT, source=char, target=enemy,
                               damage=50, damage_type=DamageType.DIRECT)
        assert not any(m.source == "LightCone_20016" for m in char.stats.active_modifiers)

    def test_on_equip_initial_check(self):
        char = self._make_char()
        e = MutualDemiseEffect(superimpose=1)
        e.on_equip(char)
        assert not any(m.source == "LightCone_20016" for m in char.stats.active_modifiers)

    def test_unequip_removes(self):
        char, enemy, _, engine = self._make_setup()
        lc = LightCone("20016", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        char.hp = 500
        engine.event_bus.emit(EventType.ON_DAMAGE_DEALT, source=enemy, target=char,
                               damage=100, damage_type=DamageType.DIRECT)
        assert any(m.source == "LightCone_20016" for m in char.stats.active_modifiers)
        char.equip_light_cone(LightCone(id="Bare", base_hp=10, base_atk=10, base_def=10))
        assert not any(m.source == "LightCone_20016" for m in char.stats.active_modifiers)


# ============================================================
#  TestMultiplication — 20015 蕃息 (3★ 丰饶)
# ============================================================


class TestMultiplication:
    """验证 3★ 丰饶光锥 蕃息: AFTER_ACTION(BA) → advance_action。"""

    def _make_char(self):
        c = create_test_character("T", hp=500, speed=100, atk=100, crit_rate=0.05)
        c.path = PathType.ABUNDANCE
        return c

    def _make_setup(self):
        char = self._make_char()
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])
        engine = CombatEngine(state)
        return char, enemy, state, engine

    def test_registry(self):
        lc = LightCone("20015")
        assert isinstance(lc, Multiplication)
        assert lc.id == "20015"
        assert lc.name == "蕃息"

    def test_lv80_stats(self):
        lc = LightCone("20015")
        assert lc.base_hp == pytest.approx(505.44)
        assert lc.base_atk == pytest.approx(168.48)
        assert lc.base_def == pytest.approx(105.3)

    def test_effect_params_s1(self):
        e = MultiplicationEffect(superimpose=1)
        assert e._PARAMS[0] == pytest.approx(0.12)

    def test_effect_params_s5(self):
        e = MultiplicationEffect(superimpose=5)
        assert e._PARAMS[4] == pytest.approx(0.20)

    def test_basic_attack_advances_action(self):
        char, enemy, _, engine = self._make_setup()
        lc = LightCone("20015", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        av_before = char.current_av
        engine.event_bus.emit(EventType.AFTER_ACTION, unit=char, target=enemy,
                               action_type=ActionType.BASIC_ATTACK, damage=100, is_crit=False,
                               engine=engine)
        assert char.current_av < av_before

    def test_non_basic_does_not_advance(self):
        char, enemy, _, engine = self._make_setup()
        lc = LightCone("20015", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        av_before = char.current_av
        engine.event_bus.emit(EventType.AFTER_ACTION, unit=char, target=enemy,
                               action_type=ActionType.SKILL, damage=100, is_crit=False,
                               engine=engine)
        assert char.current_av == pytest.approx(av_before)

    def test_other_unit_does_not_advance(self):
        char, enemy, _, engine = self._make_setup()
        other = self._make_char()
        other.name = "O2"
        engine.state.characters.append(other)
        lc = LightCone("20015", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        av_before = char.current_av
        engine.event_bus.emit(EventType.AFTER_ACTION, unit=other, target=enemy,
                               action_type=ActionType.BASIC_ATTACK, damage=100, is_crit=False,
                               engine=engine)
        assert char.current_av == pytest.approx(av_before)


# ============================================================
#  TestCollapsingSky — 20009 乐圮 (3★ 毁灭)
#  per-target 条件: 攻击 HP>50% 目标时 DMG+20~40%
# ============================================================


class TestCollapsingSky:
    """验证 3★ 毁灭光锥 乐圮: per-target HP 条件增伤。"""

    def _make_char(self):
        c = create_test_character("T", hp=500, speed=100, atk=100, crit_rate=0.05)
        c.path = PathType.DESTRUCTION
        return c

    def _make_setup(self):
        char = self._make_char()
        state = GameState(characters=[char], enemies=[])
        engine = CombatEngine(state)
        return char, state, engine

    def test_registry(self):
        lc = LightCone("20009")
        assert isinstance(lc, CollapsingSky)
        assert lc.id == "20009"
        assert lc.name == "乐圮"

    def test_lv80_stats(self):
        lc = LightCone("20009")
        assert lc.base_hp == pytest.approx(449.28)
        assert lc.base_atk == pytest.approx(196.56)
        assert lc.base_def == pytest.approx(105.3)

    def test_effect_params_s1(self):
        e = CollapsingSkyEffect(superimpose=1)
        assert e._PARAMS[0][0] == pytest.approx(0.50)
        assert e._PARAMS[0][1] == pytest.approx(0.20)

    def test_effect_params_s5(self):
        e = CollapsingSkyEffect(superimpose=5)
        assert e._PARAMS[4][0] == pytest.approx(0.50)
        assert e._PARAMS[4][1] == pytest.approx(0.40)

    def test_dmg_bonus_when_target_hp_above_50pct(self):
        """HP>50% → ACTION_START 时 DMG_BONUS 生效。"""
        char, state, engine = self._make_setup()
        lc = LightCone("20009", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(state, char)
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        enemy.hp = 8000
        engine.event_bus.emit(EventType.ACTION_START, unit=char, target=enemy,
                               action_type=ActionType.BASIC_ATTACK, engine=engine)
        dmg_mods = [m for m in char.stats.active_modifiers if m.source == "LightCone_20009"]
        assert len(dmg_mods) == 1
        assert dmg_mods[0].value == pytest.approx(0.20)

    def test_no_dmg_bonus_when_target_hp_below_50pct(self):
        """HP<50% → ACTION_START 时 DMG_BONUS 不生效。"""
        char, state, engine = self._make_setup()
        lc = LightCone("20009", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(state, char)
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        enemy.hp = 3000
        engine.event_bus.emit(EventType.ACTION_START, unit=char, target=enemy,
                               action_type=ActionType.BASIC_ATTACK, engine=engine)
        assert not any(m.source == "LightCone_20009" for m in char.stats.active_modifiers)

    def test_no_dmg_bonus_when_target_hp_equal_50pct(self):
        """HP=50% 严格 > 条件，不应触发。"""
        char, state, engine = self._make_setup()
        lc = LightCone("20009", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(state, char)
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        enemy.hp = 5000
        engine.event_bus.emit(EventType.ACTION_START, unit=char, target=enemy,
                               action_type=ActionType.BASIC_ATTACK, engine=engine)
        assert not any(m.source == "LightCone_20009" for m in char.stats.active_modifiers)

    def test_dmg_bonus_cleared_after_action(self):
        """AFTER_ACTION 后 DMG_BONUS modifier 被 purge。"""
        char, state, engine = self._make_setup()
        lc = LightCone("20009", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(state, char)
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        enemy.hp = 8000
        engine.event_bus.emit(EventType.ACTION_START, unit=char, target=enemy,
                               action_type=ActionType.BASIC_ATTACK, engine=engine)
        assert any(m.source == "LightCone_20009" for m in char.stats.active_modifiers)
        engine.event_bus.emit(EventType.AFTER_ACTION, unit=char, target=enemy,
                               action_type=ActionType.BASIC_ATTACK, damage=100, is_crit=False,
                               engine=engine)
        assert not any(m.source == "LightCone_20009" for m in char.stats.active_modifiers)

    def test_different_targets_correct_treatment(self):
        """换目标后重新判断条件。"""
        char, state, engine = self._make_setup()
        lc = LightCone("20009", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(state, char)
        e_high = Enemy(name="EH", hp=10000, speed=50, base_damage=0, level=1,
                        weaknesses=[ElementType.PHYSICAL])
        e_high.hp = 8000
        e_low = Enemy(name="EL", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        e_low.hp = 3000
        # 第一刀 vs HP 80%
        engine.event_bus.emit(EventType.ACTION_START, unit=char, target=e_high,
                               action_type=ActionType.BASIC_ATTACK, engine=engine)
        assert any(m.source == "LightCone_20009" for m in char.stats.active_modifiers)
        engine.event_bus.emit(EventType.AFTER_ACTION, unit=char, target=e_high,
                               action_type=ActionType.BASIC_ATTACK, damage=100, is_crit=False,
                               engine=engine)
        assert not any(m.source == "LightCone_20009" for m in char.stats.active_modifiers)
        # 第二刀 vs HP 30%
        engine.event_bus.emit(EventType.ACTION_START, unit=char, target=e_low,
                               action_type=ActionType.BASIC_ATTACK, engine=engine)
        assert not any(m.source == "LightCone_20009" for m in char.stats.active_modifiers)
        engine.event_bus.emit(EventType.AFTER_ACTION, unit=char, target=e_low,
                               action_type=ActionType.BASIC_ATTACK, damage=100, is_crit=False,
                               engine=engine)

    def test_other_unit_action_no_effect(self):
        """非 owner 的 ACTION_START 不影响 owner 的 modifier。"""
        char, state, engine = self._make_setup()
        other = self._make_char()
        other.name = "O2"
        state.characters.append(other)
        lc = LightCone("20009", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(state, char)
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        enemy.hp = 8000
        engine.event_bus.emit(EventType.ACTION_START, unit=other, target=enemy,
                               action_type=ActionType.BASIC_ATTACK, engine=engine)
        assert not any(m.source == "LightCone_20009" for m in char.stats.active_modifiers)

    def test_unequip_cleans_up(self):
        char, state, engine = self._make_setup()
        lc = LightCone("20009", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(state, char)
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        enemy.hp = 8000
        engine.event_bus.emit(EventType.ACTION_START, unit=char, target=enemy,
                               action_type=ActionType.BASIC_ATTACK, engine=engine)
        assert any(m.source == "LightCone_20009" for m in char.stats.active_modifiers)
        char.equip_light_cone(LightCone(id="Bare", base_hp=10, base_atk=10, base_def=10))
        assert not any(m.source == "LightCone_20009" for m in char.stats.active_modifiers)


# ============================================================
#  TestLoop — 20011 渊环 (3★ 虚无)
#  per-target 条件: 攻击减速目标时 DMG+24~48%
# ============================================================


class TestLoop:
    """验证 3★ 虚无光锥 渊环: per-target 减速条件增伤。"""

    def _make_char(self):
        c = create_test_character("T", hp=500, speed=100, atk=100, crit_rate=0.05)
        c.path = PathType.NIHILITY
        return c

    def _make_setup(self):
        char = self._make_char()
        state = GameState(characters=[char], enemies=[])
        engine = CombatEngine(state)
        return char, state, engine

    def test_registry(self):
        lc = LightCone("20011")
        assert isinstance(lc, Loop)
        assert lc.id == "20011"
        assert lc.name == "渊环"

    def test_lv80_stats(self):
        lc = LightCone("20011")
        assert lc.base_hp == pytest.approx(449.28)
        assert lc.base_atk == pytest.approx(168.48)
        assert lc.base_def == pytest.approx(140.4)

    def test_effect_params_s1(self):
        e = LoopEffect(superimpose=1)
        assert e._PARAMS[0] == pytest.approx(0.24)

    def test_effect_params_s5(self):
        e = LoopEffect(superimpose=5)
        assert e._PARAMS[4] == pytest.approx(0.48)

    def _make_slowed_enemy(self, hp=10000) -> Enemy:
        """创建一个含减速debuff的敌人。"""
        enemy = Enemy(name="E", hp=hp, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        slow_mod = StatModifier(StatType.SPD, StatModifierType.PERCENT, -0.20,
                                 source="test_slow", dispellable=True)
        enemy.stats.apply_modifier(slow_mod, "refresh")
        return enemy

    def test_dmg_bonus_when_target_slowed(self):
        """目标有减速 → ACTION_START 时 DMG_BONUS 生效。"""
        char, state, engine = self._make_setup()
        lc = LightCone("20011", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(state, char)
        enemy = self._make_slowed_enemy()
        engine.event_bus.emit(EventType.ACTION_START, unit=char, target=enemy,
                               action_type=ActionType.BASIC_ATTACK, engine=engine)
        dmg_mods = [m for m in char.stats.active_modifiers if m.source == "LightCone_20011"]
        assert len(dmg_mods) == 1
        assert dmg_mods[0].value == pytest.approx(0.24)

    def test_no_dmg_bonus_when_target_not_slowed(self):
        """目标无减速 → DMG_BONUS 不生效。"""
        char, state, engine = self._make_setup()
        lc = LightCone("20011", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(state, char)
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        engine.event_bus.emit(EventType.ACTION_START, unit=char, target=enemy,
                               action_type=ActionType.BASIC_ATTACK, engine=engine)
        assert not any(m.source == "LightCone_20011" for m in char.stats.active_modifiers)

    def test_no_dmg_bonus_when_target_spd_up(self):
        """目标 SPD 为正 → DMG_BONUS 不生效。"""
        char, state, engine = self._make_setup()
        lc = LightCone("20011", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(state, char)
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        spd_up = StatModifier(StatType.SPD, StatModifierType.PERCENT, 0.10,
                               source="test_spd_up", dispellable=True)
        enemy.stats.apply_modifier(spd_up, "refresh")
        engine.event_bus.emit(EventType.ACTION_START, unit=char, target=enemy,
                               action_type=ActionType.BASIC_ATTACK, engine=engine)
        assert not any(m.source == "LightCone_20011" for m in char.stats.active_modifiers)

    def test_dmg_bonus_cleared_after_action(self):
        """AFTER_ACTION 后 modifier 被 purge。"""
        char, state, engine = self._make_setup()
        lc = LightCone("20011", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(state, char)
        enemy = self._make_slowed_enemy()
        engine.event_bus.emit(EventType.ACTION_START, unit=char, target=enemy,
                               action_type=ActionType.BASIC_ATTACK, engine=engine)
        assert any(m.source == "LightCone_20011" for m in char.stats.active_modifiers)
        engine.event_bus.emit(EventType.AFTER_ACTION, unit=char, target=enemy,
                               action_type=ActionType.BASIC_ATTACK, damage=100, is_crit=False,
                               engine=engine)
        assert not any(m.source == "LightCone_20011" for m in char.stats.active_modifiers)

    def test_unequip_cleans_up(self):
        char, state, engine = self._make_setup()
        lc = LightCone("20011", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(state, char)
        enemy = self._make_slowed_enemy()
        engine.event_bus.emit(EventType.ACTION_START, unit=char, target=enemy,
                               action_type=ActionType.BASIC_ATTACK, engine=engine)
        assert any(m.source == "LightCone_20011" for m in char.stats.active_modifiers)
        char.equip_light_cone(LightCone(id="Bare", base_hp=10, base_atk=10, base_def=10))
        assert not any(m.source == "LightCone_20011" for m in char.stats.active_modifiers)


# ============================================================
#  TestMeshingCogs — 20012 轮契 (3★ 同谐)
#  per-turn 门控: 攻击或受击回能 4~8, 1次/回合
# ============================================================


class TestMeshingCogs:
    """验证 3★ 同谐光锥 轮契: 攻击/受击回能 + 回合门控。"""

    def _make_char(self):
        c = create_test_character("T", hp=500, speed=100, atk=100, crit_rate=0.05)
        c.path = PathType.HARMONY
        return c

    def _make_setup(self, superimpose: int = 1):
        char = self._make_char()
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])
        engine = CombatEngine(state)
        lc = LightCone("20012", superimpose=superimpose)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(state, char)
        return char, enemy, state, engine

    def test_registry(self):
        lc = LightCone("20012")
        assert isinstance(lc, MeshingCogs)
        assert lc.id == "20012"
        assert lc.name == "轮契"

    def test_lv80_stats(self):
        lc = LightCone("20012")
        assert lc.base_hp == pytest.approx(449.28)
        assert lc.base_atk == pytest.approx(168.48)
        assert lc.base_def == pytest.approx(140.4)

    def test_effect_params_s1(self):
        e = MeshingCogsEffect(superimpose=1)
        assert e._PARAMS[0] == 4

    def test_effect_params_s5(self):
        e = MeshingCogsEffect(superimpose=5)
        assert e._PARAMS[4] == 8

    def test_energy_on_attack(self):
        """攻击时 (ON_DAMAGE_DEALT) 获得能量。"""
        char, enemy, _, engine = self._make_setup()
        e_before = char.energy
        engine.event_bus.emit(EventType.ON_DAMAGE_DEALT, source=char, target=enemy,
                               damage=100, damage_type=DamageType.DIRECT)
        assert char.energy > e_before

    def test_energy_on_hit(self):
        """受击时 (ON_HIT) 获得能量。"""
        char, enemy, _, engine = self._make_setup()
        e_before = char.energy
        engine.event_bus.emit(EventType.ON_HIT, source=enemy, target=char,
                               damage=50, action_type=ActionType.BASIC_ATTACK,
                               damage_type=DamageType.DIRECT, is_crit=False)
        assert char.energy > e_before

    def test_energy_once_per_turn(self):
        """同回合内多次触发只加一次能量。"""
        char, enemy, _, engine = self._make_setup()
        engine.event_bus.emit(EventType.ON_DAMAGE_DEALT, source=char, target=enemy,
                               damage=100, damage_type=DamageType.DIRECT)
        e_after_first = char.energy
        engine.event_bus.emit(EventType.ON_DAMAGE_DEALT, source=char, target=enemy,
                               damage=100, damage_type=DamageType.DIRECT)
        assert char.energy == e_after_first

    def test_turn_start_resets_gate(self):
        """TURN_START 重置门控，再次触发可获能量。"""
        char, enemy, _, engine = self._make_setup()
        engine.event_bus.emit(EventType.ON_DAMAGE_DEALT, source=char, target=enemy,
                               damage=100, damage_type=DamageType.DIRECT)
        e_after_first = char.energy
        engine.event_bus.emit(EventType.TURN_START, unit=char, engine=engine)
        engine.event_bus.emit(EventType.ON_DAMAGE_DEALT, source=char, target=enemy,
                               damage=100, damage_type=DamageType.DIRECT)
        assert char.energy > e_after_first

    def test_attack_and_hit_share_gate(self):
        """攻击和受击共享同回合门控。"""
        char, enemy, _, engine = self._make_setup()
        engine.event_bus.emit(EventType.ON_DAMAGE_DEALT, source=char, target=enemy,
                               damage=100, damage_type=DamageType.DIRECT)
        e_after_attack = char.energy
        engine.event_bus.emit(EventType.ON_HIT, source=enemy, target=char,
                               damage=50, action_type=ActionType.BASIC_ATTACK,
                               damage_type=DamageType.DIRECT, is_crit=False)
        assert char.energy == e_after_attack

    def test_superimpose_s5_gives_eight(self):
        """S5 = 8 能量。"""
        char, enemy, _, engine = self._make_setup(superimpose=5)
        e_before = char.energy
        engine.event_bus.emit(EventType.ON_DAMAGE_DEALT, source=char, target=enemy,
                               damage=100, damage_type=DamageType.DIRECT)
        assert char.energy >= e_before + 8


# ============================================================
#  TestPasskey — 20013 灵钥 (3★ 智识)
#  per-turn 门控: 战技后回能 8~12, 1次/回合
# ============================================================


class TestPasskey:
    """验证 3★ 智识光锥 灵钥: 战技后回能 + 回合门控。"""

    def _make_char(self):
        c = create_test_character("T", hp=500, speed=100, atk=100, crit_rate=0.05)
        c.path = PathType.ERUDITION
        return c

    def _make_setup(self, superimpose: int = 1):
        char = self._make_char()
        enemy = Enemy(name="E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])
        engine = CombatEngine(state)
        lc = LightCone("20013", superimpose=superimpose)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(state, char)
        return char, enemy, state, engine

    def test_registry(self):
        lc = LightCone("20013")
        assert isinstance(lc, Passkey)
        assert lc.id == "20013"
        assert lc.name == "灵钥"

    def test_lv80_stats(self):
        lc = LightCone("20013")
        assert lc.base_hp == pytest.approx(393.12)
        assert lc.base_atk == pytest.approx(196.56)
        assert lc.base_def == pytest.approx(140.4)

    def test_effect_params_s1(self):
        e = PasskeyEffect(superimpose=1)
        assert e._PARAMS[0] == 8

    def test_effect_params_s5(self):
        e = PasskeyEffect(superimpose=5)
        assert e._PARAMS[4] == 12

    def test_energy_after_skill(self):
        """战技后 (AFTER_ACTION SKILL) 获得能量。"""
        char, enemy, _, engine = self._make_setup()
        e_before = char.energy
        engine.event_bus.emit(EventType.AFTER_ACTION, unit=char, target=enemy,
                               action_type=ActionType.SKILL, damage=100, is_crit=False,
                               engine=engine)
        assert char.energy > e_before

    def test_no_energy_after_basic(self):
        """普攻不触发回能。"""
        char, enemy, _, engine = self._make_setup()
        e_before = char.energy
        engine.event_bus.emit(EventType.AFTER_ACTION, unit=char, target=enemy,
                               action_type=ActionType.BASIC_ATTACK, damage=100, is_crit=False,
                               engine=engine)
        assert char.energy == e_before

    def test_energy_once_per_turn(self):
        """同回合多次 SKILL 只加一次。"""
        char, enemy, _, engine = self._make_setup()
        engine.event_bus.emit(EventType.AFTER_ACTION, unit=char, target=enemy,
                               action_type=ActionType.SKILL, damage=100, is_crit=False,
                               engine=engine)
        e_after_first = char.energy
        engine.event_bus.emit(EventType.AFTER_ACTION, unit=char, target=enemy,
                               action_type=ActionType.SKILL, damage=100, is_crit=False,
                               engine=engine)
        assert char.energy == e_after_first

    def test_turn_start_resets_gate(self):
        """TURN_START 重置门控。"""
        char, enemy, _, engine = self._make_setup()
        engine.event_bus.emit(EventType.AFTER_ACTION, unit=char, target=enemy,
                               action_type=ActionType.SKILL, damage=100, is_crit=False,
                               engine=engine)
        e_after_first = char.energy
        engine.event_bus.emit(EventType.TURN_START, unit=char, engine=engine)
        engine.event_bus.emit(EventType.AFTER_ACTION, unit=char, target=enemy,
                               action_type=ActionType.SKILL, damage=100, is_crit=False,
                               engine=engine)
        assert char.energy > e_after_first

    def test_other_character_skill_no_trigger(self):
        """非 owner 的战技不影响。"""
        char, enemy, _, engine = self._make_setup()
        other = self._make_char()
        other.name = "O2"
        engine.state.characters.append(other)
        e_before = char.energy
        engine.event_bus.emit(EventType.AFTER_ACTION, unit=other, target=enemy,
                               action_type=ActionType.SKILL, damage=100, is_crit=False,
                               engine=engine)
        assert char.energy == e_before


# ============================================================
#  TestHiddenShadow — 20018 匿影 (3★ 虚无)
#  方案B: 战技后→标记→下次普攻→独立 ADDITIONAL_DMG 实例
# ============================================================


class TestHiddenShadow:
    """验证 3★ 虚无光锥 匿影: 战技→标记→普攻→ADDITIONAL_DMG。"""

    def _make_char(self):
        c = create_test_character("T", hp=500, speed=100, atk=100, crit_rate=0.05)
        c.path = PathType.NIHILITY
        return c

    def _make_setup(self, superimpose: int = 1):
        char = self._make_char()
        enemy = Enemy(name="E", hp=100000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])
        engine = CombatEngine(state)
        lc = LightCone("20018", superimpose=superimpose)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(state, char)
        return char, enemy, state, engine

    def test_registry(self):
        lc = LightCone("20018")
        assert isinstance(lc, HiddenShadow)
        assert lc.id == "20018"
        assert lc.name == "匿影"

    def test_lv80_stats(self):
        lc = LightCone("20018")
        assert lc.base_hp == pytest.approx(449.28)
        assert lc.base_atk == pytest.approx(168.48)
        assert lc.base_def == pytest.approx(140.4)

    def test_effect_params_s1(self):
        e = HiddenShadowEffect(superimpose=1)
        assert e._PARAMS[0] == pytest.approx(0.60)

    def test_effect_params_s5(self):
        e = HiddenShadowEffect(superimpose=5)
        assert e._PARAMS[4] == pytest.approx(1.20)

    def test_skill_sets_next_ba_buffed_flag(self):
        """战技后设置 _next_ba_buffed 标记。"""
        char, enemy, _, engine = self._make_setup()
        assert not char.light_cone.effect._next_ba_buffed
        engine.event_bus.emit(EventType.AFTER_ACTION, unit=char, target=enemy,
                               action_type=ActionType.SKILL, damage=100, is_crit=False,
                               engine=engine)
        assert char.light_cone.effect._next_ba_buffed

    def test_basic_attack_deals_additional_damage(self):
        """标记后普攻触发 ADDITIONAL_DMG 实例。"""
        char, enemy, _, engine = self._make_setup()
        engine.event_bus.emit(EventType.AFTER_ACTION, unit=char, target=enemy,
                               action_type=ActionType.SKILL, damage=100, is_crit=False,
                               engine=engine)
        with patch.object(engine.state, 'execute_action',
                          wraps=engine.state.execute_action) as mock_exec:
            engine.event_bus.emit(EventType.AFTER_ACTION, unit=char, target=enemy,
                                   action_type=ActionType.BASIC_ATTACK, damage=100, is_crit=False,
                                   engine=engine)
            additional_calls = [call for call in mock_exec.call_args_list
                                if call[1].get('damage_type') == DamageType.ADDITIONAL_DMG]
            assert len(additional_calls) == 1


# ============================================================
#  TestSwordplay — 21010 论剑 (4★ 巡猎)
#  per-hit 叠层, target 变化重置
# ============================================================


class TestSwordplay:
    """验证 per-hit 叠层: 同目标递增, 不同目标重置。"""

    def _make_char(self):
        return create_test_character("T", hp=500, speed=100, atk=100)

    def _make_setup(self):
        char = self._make_char()
        e1 = Enemy("E1", hp=100000, speed=50, base_damage=0, level=1,
                    weaknesses=[ElementType.PHYSICAL])
        e2 = Enemy("E2", hp=100000, speed=50, base_damage=0, level=1,
                    weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[e1, e2])
        engine = CombatEngine(state)
        return char, [e1, e2], state, engine

    def test_registry(self):
        lc = LightCone("21010")
        assert isinstance(lc, Swordplay)

    def test_lv80_stats(self):
        lc = LightCone("21010")
        assert lc.base_hp == pytest.approx(505.4, abs=0.1)
        assert lc.base_atk == pytest.approx(252.7, abs=0.1)

    def test_effect_params_s1(self):
        e = SwordplayEffect(superimpose=1)
        assert e._PARAMS[0][0] == pytest.approx(0.08)
        assert e._PARAMS[0][1] == 5

    def test_same_target_increments_stacks(self):
        char, enemies, _, engine = self._make_setup()
        lc = LightCone("21010", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        engine.event_bus.emit(EventType.ON_HIT, source=char, target=enemies[0],
                               damage=100, action_type=ActionType.BASIC_ATTACK,
                               damage_type=DamageType.DIRECT, is_crit=False)
        engine.event_bus.emit(EventType.ON_HIT, source=char, target=enemies[0],
                               damage=100, action_type=ActionType.BASIC_ATTACK,
                               damage_type=DamageType.DIRECT, is_crit=False)
        dmg_mod = [m for m in char.stats.active_modifiers if m.source == "LightCone_21010"]
        assert len(dmg_mod) == 1
        assert dmg_mod[0].value == pytest.approx(0.16)

    def test_target_change_resets(self):
        char, enemies, _, engine = self._make_setup()
        lc = LightCone("21010", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        engine.event_bus.emit(EventType.ON_HIT, source=char, target=enemies[0],
                               damage=100, action_type=ActionType.BASIC_ATTACK,
                               damage_type=DamageType.DIRECT, is_crit=False)
        engine.event_bus.emit(EventType.ON_HIT, source=char, target=enemies[0],
                               damage=100, action_type=ActionType.BASIC_ATTACK,
                               damage_type=DamageType.DIRECT, is_crit=False)
        engine.event_bus.emit(EventType.ON_HIT, source=char, target=enemies[1],
                               damage=100, action_type=ActionType.BASIC_ATTACK,
                               damage_type=DamageType.DIRECT, is_crit=False)
        dmg_mod = [m for m in char.stats.active_modifiers if m.source == "LightCone_21010"]
        assert len(dmg_mod) == 1
        assert dmg_mod[0].value == pytest.approx(0.08)

    def test_stack_capped_at_5(self):
        char, enemies, _, engine = self._make_setup()
        lc = LightCone("21010", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        for _ in range(10):
            engine.event_bus.emit(EventType.ON_HIT, source=char, target=enemies[0],
                                   damage=100, action_type=ActionType.BASIC_ATTACK,
                                   damage_type=DamageType.DIRECT, is_crit=False)
        dmg_mod = [m for m in char.stats.active_modifiers if m.source == "LightCone_21010"]
        assert dmg_mod[0].value == pytest.approx(0.40)

    def test_unequip_cleans_up(self):
        char, enemies, _, engine = self._make_setup()
        lc = LightCone("21010", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        engine.event_bus.emit(EventType.ON_HIT, source=char, target=enemies[0],
                               damage=100, action_type=ActionType.BASIC_ATTACK,
                               damage_type=DamageType.DIRECT, is_crit=False)
        assert any(m.source == "LightCone_21010" for m in char.stats.active_modifiers)
        char.equip_light_cone(LightCone(id="Bare", base_hp=10, base_atk=10, base_def=10))
        assert not any(m.source == "LightCone_21010" for m in char.stats.active_modifiers)


# ============================================================
#  TestRiverFlowsInSpring — 21024 春水初生 (4★ 巡猎)
#  状态机: ACTIVE→受击BROKEN→TURN_END恢复
# ============================================================


class TestRiverFlowsInSpring:
    """验证状态机: 受击后失效, 回合结束时恢复。"""

    def _make_char(self):
        return create_test_character("T", hp=500, speed=100, atk=100)

    def _make_setup(self):
        char = self._make_char()
        enemy = Enemy("E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])
        engine = CombatEngine(state)
        return char, enemy, state, engine

    def test_registry(self):
        lc = LightCone("21024")
        assert isinstance(lc, RiverFlowsInSpring)

    def test_lv80_stats(self):
        lc = LightCone("21024")
        assert lc.base_hp == pytest.approx(449.3, abs=0.1)
        assert lc.base_atk == pytest.approx(252.7, abs=0.1)

    def test_effect_params_s1(self):
        e = RiverFlowsInSpringEffect(superimpose=1)
        assert e._PARAMS[0][0] == pytest.approx(0.08)
        assert e._PARAMS[0][1] == pytest.approx(0.12)

    def test_battle_start_activates_buffs(self):
        char, enemy, _, engine = self._make_setup()
        lc = LightCone("21024", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        engine.event_bus.emit(EventType.BATTLE_START)
        mods = [m for m in char.stats.active_modifiers if m.source in ("LightCone_21024_SPD", "LightCone_21024_DMG")]
        assert len(mods) == 2
        assert any(m.stat_type == StatType.SPD for m in mods)
        assert any(m.stat_type == StatType.DMG_BONUS for m in mods)

    def test_hit_breaks_buffs(self):
        char, enemy, _, engine = self._make_setup()
        lc = LightCone("21024", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        engine.event_bus.emit(EventType.BATTLE_START)
        assert any(m.source in ("LightCone_21024_SPD", "LightCone_21024_DMG") for m in char.stats.active_modifiers)
        engine.event_bus.emit(EventType.ON_HIT, source=enemy, target=char,
                               damage=50, action_type=ActionType.BASIC_ATTACK,
                               damage_type=DamageType.DIRECT, is_crit=False)
        assert not any(m.source in ("LightCone_21024_SPD", "LightCone_21024_DMG") for m in char.stats.active_modifiers)
        assert lc.effect._broken_turns_remaining == 2

    def test_turn_end_restores_buffs(self):
        char, enemy, _, engine = self._make_setup()
        lc = LightCone("21024", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        engine.event_bus.emit(EventType.BATTLE_START)
        engine.event_bus.emit(EventType.ON_HIT, source=enemy, target=char,
                               damage=50, action_type=ActionType.BASIC_ATTACK,
                               damage_type=DamageType.DIRECT, is_crit=False)
        assert not any(m.source in ("LightCone_21024_SPD", "LightCone_21024_DMG") for m in char.stats.active_modifiers)
        # Wait 2 turn-end events to restore (下回合结束时恢复)
        engine.event_bus.emit(EventType.TURN_END, unit=char, engine=engine)
        assert not any(m.source in ("LightCone_21024_SPD", "LightCone_21024_DMG") for m in char.stats.active_modifiers)
        engine.event_bus.emit(EventType.TURN_END, unit=char, engine=engine)
        assert any(m.source in ("LightCone_21024_SPD", "LightCone_21024_DMG") for m in char.stats.active_modifiers)

    def test_other_unit_turn_end_does_not_restore(self):
        char, enemy, _, engine = self._make_setup()
        lc = LightCone("21024", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        engine.event_bus.emit(EventType.BATTLE_START)
        engine.event_bus.emit(EventType.ON_HIT, source=enemy, target=char,
                               damage=50, action_type=ActionType.BASIC_ATTACK,
                               damage_type=DamageType.DIRECT, is_crit=False)
        engine.event_bus.emit(EventType.TURN_END, unit=enemy, engine=engine)
        assert not any(m.source in ("LightCone_21024_SPD", "LightCone_21024_DMG") for m in char.stats.active_modifiers)

    def test_unequip_cleans_up(self):
        char, enemy, _, engine = self._make_setup()
        lc = LightCone("21024", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        engine.event_bus.emit(EventType.BATTLE_START)
        assert any(m.source in ("LightCone_21024_SPD", "LightCone_21024_DMG") for m in char.stats.active_modifiers)
        char.equip_light_cone(LightCone(id="Bare", base_hp=10, base_atk=10, base_def=10))
        assert not any(m.source in ("LightCone_21024_SPD", "LightCone_21024_DMG") for m in char.stats.active_modifiers)


# ============================================================
#  TestTrendUniversalMarket — 21016 宇宙市场趋势 (4★ 存护)
#  受击基底概率→灼烧DoT
# ============================================================


class TestTrendUniversalMarket:
    """验证受击后基底概率施加灼烧DoT。"""

    def _make_char(self):
        c = create_test_character("T", hp=500, speed=100, atk=100)
        c.path = PathType.PRESERVATION
        return c

    def _make_setup(self):
        char = self._make_char()
        enemy = Enemy("E", hp=50000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])
        engine = CombatEngine(state)
        return char, enemy, state, engine

    def test_registry(self):
        lc = LightCone("21016")
        assert isinstance(lc, TrendUniversalMarket)

    def test_lv80_stats(self):
        lc = LightCone("21016")
        assert lc.base_hp == pytest.approx(561.6, abs=0.1)
        assert lc.base_atk == pytest.approx(196.6, abs=0.1)

    def test_effect_params_s1(self):
        e = TrendUniversalMarketEffect(superimpose=1)
        assert e._PARAMS[0][0] == pytest.approx(0.16)
        assert e._PARAMS[0][1] == pytest.approx(1.00)
        assert e._PARAMS[0][2] == pytest.approx(0.40)

    def test_on_hit_applies_burn(self):
        char, enemy, _, engine = self._make_setup()
        lc = LightCone("21016", superimpose=3)  # S3: 110% base
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        assert len(enemy.dot_statuses) == 0
        engine.event_bus.emit(EventType.ON_HIT, source=enemy, target=char,
                               damage=50, action_type=ActionType.BASIC_ATTACK,
                               damage_type=DamageType.DIRECT, is_crit=False)
        assert len(enemy.dot_statuses) == 1
        assert enemy.dot_statuses[0].element == ElementType.FIRE

    def test_other_target_does_not_apply(self):
        char, enemy, _, engine = self._make_setup()
        lc = LightCone("21016", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        engine.event_bus.emit(EventType.ON_HIT, source=char, target=enemy,
                               damage=100, action_type=ActionType.BASIC_ATTACK,
                               damage_type=DamageType.DIRECT, is_crit=False)
        assert len(enemy.dot_statuses) == 0

    def test_on_equip_grants_def(self):
        char = self._make_char()
        e = TrendUniversalMarketEffect(superimpose=1)
        e.on_equip(char)
        def_mods = [m for m in char.stats.active_modifiers if m.stat_type == StatType.DEF]
        assert len(def_mods) >= 1


# ============================================================
#  TestReturnToDarkness — 21031 重返幽冥 (4★ 巡猎)
#  暴击固定概率驱散增益
# ============================================================


class TestReturnToDarkness:
    """验证暴击后固定概率驱散敌方增益。"""

    def _make_char(self):
        return create_test_character("T", hp=500, speed=100, atk=100)

    def _make_setup(self):
        char = self._make_char()
        enemy = Enemy("E", hp=50000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        # 给敌人挂一个正面增益buff
        buff = StatModifier(StatType.DEF, StatModifierType.PERCENT, 0.50,
                            source="test_buff", dispellable=True)
        enemy.stats.apply_modifier(buff, "refresh")
        state = GameState(characters=[char], enemies=[enemy])
        engine = CombatEngine(state)
        return char, enemy, state, engine

    def test_registry(self):
        lc = LightCone("21031")
        assert isinstance(lc, ReturnToDarkness)

    def test_lv80_stats(self):
        lc = LightCone("21031")
        assert lc.base_hp == pytest.approx(449.3, abs=0.1)
        assert lc.base_atk == pytest.approx(280.8, abs=0.1)

    def test_crit_hit_dispels_buff(self):
        char, enemy, _, engine = self._make_setup()
        lc = LightCone("21031", superimpose=5)  # S5: 32% fixed
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        buffs_before = [m for m in enemy.stats.active_modifiers if m.source == "test_buff"]
        assert len(buffs_before) == 1
        # Mock random to guarantee success
        with patch("random.random", return_value=0.0):
            engine.event_bus.emit(EventType.ON_HIT, source=char, target=enemy,
                                   damage=100, action_type=ActionType.BASIC_ATTACK,
                                   damage_type=DamageType.DIRECT, is_crit=True)
        buffs_after = [m for m in enemy.stats.active_modifiers if m.source == "test_buff"]
        assert len(buffs_after) == 0

    def test_no_crit_no_dispel(self):
        char, enemy, _, engine = self._make_setup()
        lc = LightCone("21031", superimpose=5)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        engine.event_bus.emit(EventType.ON_HIT, source=char, target=enemy,
                               damage=100, action_type=ActionType.BASIC_ATTACK,
                               damage_type=DamageType.DIRECT, is_crit=False)
        buffs_after = [m for m in enemy.stats.active_modifiers if m.source == "test_buff"]
        assert len(buffs_after) == 1

    def test_on_equip_grants_crit_rate(self):
        char = self._make_char()
        e = ReturnToDarknessEffect(superimpose=1)
        e.on_equip(char)
        assert char.stats.get_total_stat(StatType.CRIT_RATE) >= 0.12


# ============================================================
#  TestResolutionShines — 21015 决心如汗珠闪耀 (4★ 虚无)
#  攻陷debuff基底概率+EHR
# ============================================================


class TestResolutionShines:
    """验证基底概率+EHR施加攻陷DEF reduction。"""

    def _make_char(self):
        c = create_test_character("T", hp=500, speed=100, atk=100)
        c.path = PathType.NIHILITY
        return c

    def _make_setup(self):
        char = self._make_char()
        enemy = Enemy("E", hp=50000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])
        engine = CombatEngine(state)
        return char, enemy, state, engine

    def test_registry(self):
        lc = LightCone("21015")
        assert isinstance(lc, ResolutionShines)

    def test_lv80_stats(self):
        lc = LightCone("21015")
        assert lc.base_hp == pytest.approx(505.4, abs=0.1)
        assert lc.base_atk == pytest.approx(252.7, abs=0.1)

    def test_hit_applies_def_reduction(self):
        char, enemy, _, engine = self._make_setup()
        lc = LightCone("21015", superimpose=5)  # S5: 100% base
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        engine.event_bus.emit(EventType.ON_HIT, source=char, target=enemy,
                               damage=100, action_type=ActionType.BASIC_ATTACK,
                               damage_type=DamageType.DIRECT, is_crit=False)
        def_mods = [m for m in enemy.stats.active_modifiers
                    if m.source == "LightCone_21015" and getattr(m, "tag", "") == "Resolution_21015_Ensnared"]
        assert len(def_mods) == 1
        assert def_mods[0].value == pytest.approx(0.16)

    def test_ensnared_not_reapplied(self):
        char, enemy, _, engine = self._make_setup()
        lc = LightCone("21015", superimpose=5)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        engine.event_bus.emit(EventType.ON_HIT, source=char, target=enemy,
                               damage=100, action_type=ActionType.BASIC_ATTACK,
                               damage_type=DamageType.DIRECT, is_crit=False)
        def_mods = [m for m in enemy.stats.active_modifiers if m.source == "LightCone_21015"]
        assert len(def_mods) == 1
        engine.event_bus.emit(EventType.ON_HIT, source=char, target=enemy,
                               damage=100, action_type=ActionType.BASIC_ATTACK,
                               damage_type=DamageType.DIRECT, is_crit=False)
        assert len(def_mods) == 1

    def test_other_unit_hit_no_effect(self):
        char, enemy, _, engine = self._make_setup()
        other = self._make_char()
        other.name = "O2"
        engine.state.characters.append(other)
        lc = LightCone("21015", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        engine.event_bus.emit(EventType.ON_HIT, source=other, target=enemy,
                               damage=100, action_type=ActionType.BASIC_ATTACK,
                               damage_type=DamageType.DIRECT, is_crit=False)
        assert not any(m.source == "LightCone_21015" for m in enemy.stats.active_modifiers)

    def test_applies_def_reduction_to_enemy(self):
        char, enemy, _, engine = self._make_setup()
        lc = LightCone("21015", superimpose=5)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        engine.event_bus.emit(EventType.ON_HIT, source=char, target=enemy,
                               damage=100, action_type=ActionType.BASIC_ATTACK,
                               damage_type=DamageType.DIRECT, is_crit=False)
        assert any(m.source == "LightCone_21015" for m in enemy.stats.active_modifiers)


# ============================================================
#  TestPerfectTiming — 21014 此时恰好 (4★ 丰饶)
#  动态EFF_RES→heal_boost转换
# ============================================================


class TestPerfectTiming:
    """验证动态属性转换: EFF_RES→OUTGOING_HEALING_BOOST。"""

    def _make_char(self):
        c = create_test_character("T", hp=500, speed=100, atk=100)
        c.path = PathType.ABUNDANCE
        return c

    def _make_setup(self):
        char = self._make_char()
        enemy = Enemy("E", hp=50000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])
        engine = CombatEngine(state)
        return char, enemy, state, engine

    def test_registry(self):
        lc = LightCone("21014")
        assert isinstance(lc, PerfectTiming)

    def test_effect_params_s1(self):
        e = PerfectTimingEffect(superimpose=1)
        assert e._PARAMS[0][0] == pytest.approx(0.16)
        assert e._PARAMS[0][1] == pytest.approx(0.33)
        assert e._PARAMS[0][2] == pytest.approx(0.15)

    def test_on_equip_grants_eff_res(self):
        char = self._make_char()
        e = PerfectTimingEffect(superimpose=1)
        e.on_equip(char)
        assert char.stats.get_total_stat(StatType.EFFECT_RES) == pytest.approx(0.16)

    def test_initial_heal_boost_computed(self):
        char, _, _, engine = self._make_setup()
        lc = LightCone("21014", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        heal_mods = [m for m in char.stats.active_modifiers
                     if m.stat_type == StatType.OUTGOING_HEALING_BOOST]
        assert len(heal_mods) >= 1
        expected = min(0.16 * 0.33, 0.15)
        assert heal_mods[0].value == pytest.approx(expected)

    def test_status_apply_refreshes_heal_boost(self):
        char, _, _, engine = self._make_setup()
        lc = LightCone("21014", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        heal_mods = [m for m in char.stats.active_modifiers
                     if m.stat_type == StatType.OUTGOING_HEALING_BOOST]
        initial_val = heal_mods[0].value
        extra_res = StatModifier(StatType.EFFECT_RES, StatModifierType.PERCENT, 0.30,
                                  source="test_buff", dispellable=True)
        char.stats.apply_modifier(extra_res, "refresh")
        new_heal_mods = [m for m in char.stats.active_modifiers
                         if m.stat_type == StatType.OUTGOING_HEALING_BOOST
                         and m.source == "LightCone_21014_HEAL"]
        assert new_heal_mods[0].value > initial_val


# ============================================================
#  TestPastAndFuture — 21025 过往未来 (4★ 同谐)
#  战技→下一行动队友DMG_BONUS
# ============================================================


class TestPastAndFuture:
    """验证战技后下一个行动队友获得DMG_BONUS。"""

    def _make_char(self):
        return create_test_character("T", hp=500, speed=100, atk=100)

    def _make_setup(self):
        char1 = create_test_character("A", hp=500, speed=100, atk=100)
        char1.path = PathType.HARMONY
        char2 = create_test_character("B", hp=500, speed=80, atk=100)  # slower → bigger AV
        enemy = Enemy("E", hp=50000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char1, char2], enemies=[enemy])
        engine = CombatEngine(state)
        return char1, char2, enemy, state, engine

    def test_registry(self):
        lc = LightCone("21025")
        assert isinstance(lc, PastAndFuture)

    def test_skill_buffs_next_ally(self):
        char1, char2, enemy, _, engine = self._make_setup()
        lc = LightCone("21025", superimpose=1)
        char1.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char1)
        engine.event_bus.emit(EventType.AFTER_ACTION, unit=char1, target=enemy,
                               action_type=ActionType.SKILL, damage=100, is_crit=False,
                               engine=engine)
        dmg_mods = [m for m in char2.stats.active_modifiers if m.source == "LightCone_21025"]
        assert len(dmg_mods) == 1
        assert dmg_mods[0].value == pytest.approx(0.16)

    def test_basic_attack_does_not_buff(self):
        char1, char2, enemy, _, engine = self._make_setup()
        lc = LightCone("21025", superimpose=1)
        char1.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char1)
        engine.event_bus.emit(EventType.AFTER_ACTION, unit=char1, target=enemy,
                               action_type=ActionType.BASIC_ATTACK, damage=100, is_crit=False,
                               engine=engine)
        assert not any(m.source == "LightCone_21025" for m in char2.stats.active_modifiers)

    def test_other_unit_skill_no_effect(self):
        char1, char2, enemy, _, engine = self._make_setup()
        lc = LightCone("21025", superimpose=1)
        char1.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char1)
        engine.event_bus.emit(EventType.AFTER_ACTION, unit=char2, target=enemy,
                               action_type=ActionType.SKILL, damage=100, is_crit=False,
                               engine=engine)
        assert not any(m.source == "LightCone_21025" for m in char2.stats.active_modifiers)


# ============================================================
#  TestThisIsMe — 21030 这就是我啦！ (4★ 存护)
#  终结技DEF flat bonus加到base damage
# ============================================================


class TestThisIsMe:
    """验证终结技时 DEF→base_dmg flat bonus。"""

    def _make_char(self):
        c = create_test_character("T", hp=500, speed=100, atk=100)
        c.path = PathType.PRESERVATION
        return c

    def _make_setup(self):
        char = self._make_char()
        enemy = Enemy("E", hp=100000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])
        engine = CombatEngine(state)
        return char, enemy, state, engine

    def test_registry(self):
        lc = LightCone("21030")
        assert isinstance(lc, ThisIsMe)

    def test_lv80_stats(self):
        lc = LightCone("21030")
        assert lc.base_hp == pytest.approx(449.3, abs=0.1)
        assert lc.base_atk == pytest.approx(196.6, abs=0.1)

    def test_effect_params_s1(self):
        e = ThisIsMeEffect(superimpose=1)
        assert e._PARAMS[0][0] == pytest.approx(0.16)
        assert e._PARAMS[0][1] == pytest.approx(0.60)

    def test_ult_sets_extra_base_dmg(self):
        char, enemy, _, engine = self._make_setup()
        lc = LightCone("21030", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        assert not hasattr(char, "_extra_base_dmg") or char._extra_base_dmg == 0
        engine.event_bus.emit(EventType.ON_ULTIMATE_INSERTED, character=char, target=enemy)
        def_total = char.stats.get_total_stat(StatType.DEF)
        expected = def_total * 0.60
        assert char._extra_base_dmg == pytest.approx(expected)

    def test_ult_after_clears_extra_base_dmg(self):
        char, enemy, _, engine = self._make_setup()
        lc = LightCone("21030", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        engine.event_bus.emit(EventType.ON_ULTIMATE_INSERTED, character=char, target=enemy)
        assert char._extra_base_dmg > 0
        engine.event_bus.emit(EventType.AFTER_ACTION, unit=char, target=enemy,
                               action_type=ActionType.ULTIMATE, damage=100, is_crit=False,
                               engine=engine)
        assert char._extra_base_dmg == 0

    def test_non_ult_does_not_set_extra_dmg(self):
        char, enemy, _, engine = self._make_setup()
        lc = LightCone("21030", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        engine.event_bus.emit(EventType.ON_ULTIMATE_INSERTED, character=enemy, target=enemy)
        assert not hasattr(char, "_extra_base_dmg") or char._extra_base_dmg == 0

    def test_on_equip_grants_def(self):
        char = self._make_char()
        e = ThisIsMeEffect(superimpose=1)
        e.on_equip(char)
        assert char.stats.get_total_stat(StatType.DEF) >= 0.16


# ============================================================
#  TestWeWillMeetAgain — 21029 后会有期 (4★ 虚无)
#  普攻/战技后随机目标ADD_DMG
# ============================================================


class TestWeWillMeetAgain:
    """验证BA/SKILL后随机受击目标追加ADDITIONAL_DMG。"""

    def _make_char(self):
        c = create_test_character("T", hp=500, speed=100, atk=100)
        c.path = PathType.NIHILITY
        return c

    def _make_setup(self):
        char = self._make_char()
        e1 = Enemy("E1", hp=100000, speed=50, base_damage=0, level=1,
                    weaknesses=[ElementType.PHYSICAL])
        e2 = Enemy("E2", hp=100000, speed=50, base_damage=0, level=1,
                    weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[e1, e2])
        engine = CombatEngine(state)
        return char, [e1, e2], state, engine

    def test_registry(self):
        lc = LightCone("21029")
        assert isinstance(lc, WeWillMeetAgain)

    def test_lv80_stats(self):
        lc = LightCone("21029")
        assert lc.base_hp == pytest.approx(449.3, abs=0.1)
        assert lc.base_atk == pytest.approx(280.8, abs=0.1)

    def test_basic_triggers_additional_dmg(self):
        char, enemies, _, engine = self._make_setup()
        lc = LightCone("21029", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        with patch.object(engine.state, 'execute_action',
                          wraps=engine.state.execute_action) as mock_exec:
            engine.event_bus.emit(EventType.AFTER_ACTION, unit=char, target=enemies[0],
                                   action_type=ActionType.BASIC_ATTACK, damage=100, is_crit=False,
                                   engine=engine)
            add_calls = [c for c in mock_exec.call_args_list
                         if c[1].get('damage_type') == DamageType.ADDITIONAL_DMG]
            assert len(add_calls) == 1

    def test_skill_triggers_additional_dmg(self):
        char, enemies, _, engine = self._make_setup()
        lc = LightCone("21029", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        with patch.object(engine.state, 'execute_action',
                          wraps=engine.state.execute_action) as mock_exec:
            engine.event_bus.emit(EventType.AFTER_ACTION, unit=char, target=enemies[0],
                                   action_type=ActionType.SKILL, damage=100, is_crit=False,
                                   engine=engine)
            add_calls = [c for c in mock_exec.call_args_list
                         if c[1].get('damage_type') == DamageType.ADDITIONAL_DMG]
            assert len(add_calls) == 1

    def test_ult_does_not_trigger(self):
        char, enemies, _, engine = self._make_setup()
        lc = LightCone("21029", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        with patch.object(engine.state, 'execute_action',
                          wraps=engine.state.execute_action) as mock_exec:
            engine.event_bus.emit(EventType.AFTER_ACTION, unit=char, target=enemies[0],
                                   action_type=ActionType.ULTIMATE, damage=100, is_crit=False,
                                   engine=engine)
            add_calls = [c for c in mock_exec.call_args_list
                         if c[1].get('damage_type') == DamageType.ADDITIONAL_DMG]
            assert len(add_calls) == 0

    def test_other_unit_does_not_trigger(self):
        char, enemies, _, engine = self._make_setup()
        other = self._make_char()
        other.name = "O2"
        engine.state.characters.append(other)
        lc = LightCone("21029", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        with patch.object(engine.state, 'execute_action',
                          wraps=engine.state.execute_action) as mock_exec:
            engine.event_bus.emit(EventType.AFTER_ACTION, unit=other, target=enemies[0],
                                   action_type=ActionType.BASIC_ATTACK, damage=100, is_crit=False,
                                   engine=engine)
            add_calls = [c for c in mock_exec.call_args_list
                         if c[1].get('damage_type') == DamageType.ADDITIONAL_DMG]
            assert len(add_calls) == 0


# ============================================================
#  TestMolesWelcomeYou — 21005 鼹鼠党欢迎你 (4★ 毁灭)
#  BA/Skill/Ult各1层【淘气值】→ATK%
# ============================================================


class TestMolesWelcomeYou:
    """验证action-type独立叠层, max3。"""

    def _make_char(self):
        c = create_test_character("T", hp=500, speed=100, atk=100)
        c.path = PathType.DESTRUCTION
        return c

    def _make_setup(self):
        char = self._make_char()
        enemy = Enemy("E", hp=50000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])
        engine = CombatEngine(state)
        return char, enemy, state, engine

    def test_registry(self):
        lc = LightCone("21005")
        assert isinstance(lc, MolesWelcomeYou)

    def test_lv80_stats(self):
        lc = LightCone("21005")
        assert lc.base_hp == pytest.approx(561.6, abs=0.1)
        assert lc.base_atk == pytest.approx(252.7, abs=0.1)

    def test_effect_params_s1(self):
        e = MolesWelcomeYouEffect(superimpose=1)
        assert e._PARAMS[0] == pytest.approx(0.12)

    def test_ba_gives_one_stack(self):
        char, enemy, _, engine = self._make_setup()
        lc = LightCone("21005", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        engine.event_bus.emit(EventType.AFTER_ACTION, unit=char, target=enemy,
                               action_type=ActionType.BASIC_ATTACK, damage=100, is_crit=False,
                               engine=engine)
        atk_mods = [m for m in char.stats.active_modifiers if m.source == "LightCone_21005"]
        assert len(atk_mods) == 1
        assert atk_mods[0].value == pytest.approx(0.12)

    def test_skill_and_ba_two_stacks(self):
        char, enemy, _, engine = self._make_setup()
        lc = LightCone("21005", superimpose=5)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        engine.event_bus.emit(EventType.AFTER_ACTION, unit=char, target=enemy,
                               action_type=ActionType.BASIC_ATTACK, damage=100, is_crit=False,
                               engine=engine)
        engine.event_bus.emit(EventType.AFTER_ACTION, unit=char, target=enemy,
                               action_type=ActionType.SKILL, damage=100, is_crit=False,
                               engine=engine)
        atk_mods = [m for m in char.stats.active_modifiers if m.source == "LightCone_21005"]
        assert atk_mods[0].value == pytest.approx(0.48)

    def test_repeat_type_does_not_stack(self):
        char, enemy, _, engine = self._make_setup()
        lc = LightCone("21005", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        engine.event_bus.emit(EventType.AFTER_ACTION, unit=char, target=enemy,
                               action_type=ActionType.SKILL, damage=100, is_crit=False,
                               engine=engine)
        engine.event_bus.emit(EventType.AFTER_ACTION, unit=char, target=enemy,
                               action_type=ActionType.SKILL, damage=100, is_crit=False,
                               engine=engine)
        atk_mods = [m for m in char.stats.active_modifiers if m.source == "LightCone_21005"]
        assert atk_mods[0].value == pytest.approx(0.12)


# ============================================================
#  TestSubscribeForMore — 21017 点个关注吧！ (4★ 巡猎)
#  永久BAS/SKILL_DMG + 满能量额外DMG
# ============================================================


class TestSubscribeForMore:
    """验证永久BAS/SKILL_DMG + 满能量条件额外。"""

    def _make_char(self):
        return create_test_character("T", hp=500, speed=100, atk=100)

    def _make_setup(self):
        char = self._make_char()
        enemy = Enemy("E", hp=50000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])
        engine = CombatEngine(state)
        return char, enemy, state, engine

    def test_registry(self):
        lc = LightCone("21017")
        assert isinstance(lc, SubscribeForMore)

    def test_effect_params_s1(self):
        e = SubscribeForMoreEffect(superimpose=1)
        assert e._PARAMS[0][0] == pytest.approx(0.24)
        assert e._PARAMS[0][1] == pytest.approx(0.24)

    def test_on_equip_grants_ba_and_skill_dmg(self):
        char = self._make_char()
        e = SubscribeForMoreEffect(superimpose=1)
        e.on_equip(char)
        assert char.stats.get_total_stat(StatType.BASIC_ATK_DMG) == pytest.approx(0.24)
        assert char.stats.get_total_stat(StatType.SKILL_DMG) == pytest.approx(0.24)

    def test_full_energy_extra_dmg(self):
        char, enemy, _, engine = self._make_setup()
        char.energy = char.max_energy
        lc = LightCone("21017", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        engine.event_bus.emit(EventType.ACTION_START, unit=char, target=enemy,
                               action_type=ActionType.BASIC_ATTACK, engine=engine)
        cond_mods = [m for m in char.stats.active_modifiers if m.source == "LightCone_21017_COND"]
        assert len(cond_mods) == 1

    def test_not_full_energy_no_extra(self):
        char, enemy, _, engine = self._make_setup()
        char.energy = 0
        lc = LightCone("21017", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        engine.event_bus.emit(EventType.ACTION_START, unit=char, target=enemy,
                               action_type=ActionType.BASIC_ATTACK, engine=engine)
        assert not any(m.source == "LightCone_21017_COND" for m in char.stats.active_modifiers)

    def test_after_clears_extra(self):
        char, enemy, _, engine = self._make_setup()
        char.energy = char.max_energy
        lc = LightCone("21017", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        engine.event_bus.emit(EventType.ACTION_START, unit=char, target=enemy,
                               action_type=ActionType.BASIC_ATTACK, engine=engine)
        assert any(m.source == "LightCone_21017_COND" for m in char.stats.active_modifiers)
        engine.event_bus.emit(EventType.AFTER_ACTION, unit=char, target=enemy,
                               action_type=ActionType.BASIC_ATTACK, damage=100, is_crit=False,
                               engine=engine)
        assert not any(m.source == "LightCone_21017_COND" for m in char.stats.active_modifiers)


# ============================================================
#  TestBirthOfTheSelf — 21006 「我」的诞生 (4★ 智识)
#  永久FUA_DMG + HP≤50%额外
# ============================================================


class TestBirthOfTheSelf:
    """验证永久FUA_DMG + HP≤50%条件额外FUA_DMG。"""

    def _make_char(self):
        c = create_test_character("T", hp=500, speed=100, atk=100)
        c.path = PathType.ERUDITION
        return c

    def _make_setup(self):
        char = self._make_char()
        enemy = Enemy("E", hp=10000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])
        engine = CombatEngine(state)
        return char, enemy, state, engine

    def test_registry(self):
        lc = LightCone("21006")
        assert isinstance(lc, BirthOfTheSelf)

    def test_effect_params_s1(self):
        e = BirthOfTheSelfEffect(superimpose=1)
        assert e._PARAMS[0][0] == pytest.approx(0.24)
        assert e._PARAMS[0][1] == pytest.approx(0.50)
        assert e._PARAMS[0][2] == pytest.approx(0.24)

    def test_on_equip_grants_fua_dmg(self):
        char = self._make_char()
        e = BirthOfTheSelfEffect(superimpose=1)
        e.on_equip(char)
        assert char.stats.get_total_stat(StatType.FUA_DMG) == pytest.approx(0.24)

    def test_hp_below_50_extra_fua(self):
        char, enemy, _, engine = self._make_setup()
        lc = LightCone("21006", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        enemy.hp = 3000
        engine.event_bus.emit(EventType.ACTION_START, unit=char, target=enemy,
                               action_type=ActionType.SKILL, engine=engine)
        fua_extra = [m for m in char.stats.active_modifiers if m.source == "LightCone_21006_COND"]
        assert len(fua_extra) == 1

    def test_hp_above_50_no_extra(self):
        char, enemy, _, engine = self._make_setup()
        lc = LightCone("21006", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        enemy.hp = 9000
        engine.event_bus.emit(EventType.ACTION_START, unit=char, target=enemy,
                               action_type=ActionType.SKILL, engine=engine)
        assert not any(m.source == "LightCone_21006_COND" for m in char.stats.active_modifiers)

    def test_after_clears_cond(self):
        char, enemy, _, engine = self._make_setup()
        lc = LightCone("21006", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        enemy.hp = 3000
        engine.event_bus.emit(EventType.ACTION_START, unit=char, target=enemy,
                               action_type=ActionType.SKILL, engine=engine)
        assert any(m.source == "LightCone_21006_COND" for m in char.stats.active_modifiers)
        engine.event_bus.emit(EventType.AFTER_ACTION, unit=char, target=enemy,
                               action_type=ActionType.SKILL, damage=100, is_crit=False,
                               engine=engine)
        assert not any(m.source == "LightCone_21006_COND" for m in char.stats.active_modifiers)


# ============================================================
#  TestPlanetaryRendezvous — 21011 与行星相会 (4★ 同谐)
#  元素匹配→临时DMG_BONUS
# ============================================================


class TestPlanetaryRendezvous:
    """验证元素匹配时施加临时DMG_BONUS。"""

    def _make_char(self):
        c = create_test_character("T", hp=500, speed=100, atk=100, element=ElementType.FIRE)
        c.path = PathType.HARMONY
        return c

    def _make_setup(self):
        char = self._make_char()
        ally = create_test_character("A", hp=500, speed=100, atk=100, element=ElementType.FIRE)
        ally2 = create_test_character("B", hp=500, speed=100, atk=100, element=ElementType.ICE)
        enemy = Enemy("E", hp=50000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char, ally, ally2], enemies=[enemy])
        engine = CombatEngine(state)
        return char, ally, ally2, enemy, state, engine

    def test_registry(self):
        lc = LightCone("21011")
        assert isinstance(lc, PlanetaryRendezvous)

    def test_matching_element_gets_dmg(self):
        char, ally, _, enemy, _, engine = self._make_setup()
        lc = LightCone("21011", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        engine.event_bus.emit(EventType.BATTLE_START)
        dmg_mods = [m for m in ally.stats.active_modifiers if m.source == "LightCone_21011"]
        assert len(dmg_mods) == 1
        assert dmg_mods[0].value == pytest.approx(0.12)

    def test_mismatched_element_no_dmg(self):
        char, _, ally2, enemy, _, engine = self._make_setup()
        lc = LightCone("21011", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        engine.event_bus.emit(EventType.BATTLE_START)
        assert not any(m.source == "LightCone_21011" for m in ally2.stats.active_modifiers)

    def test_aura_persistent_after_action(self):
        char, ally, _, enemy, _, engine = self._make_setup()
        lc = LightCone("21011", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        engine.event_bus.emit(EventType.BATTLE_START)
        assert any(m.source == "LightCone_21011" for m in ally.stats.active_modifiers)
        # Permanent aura persists after any action
        engine.event_bus.emit(EventType.AFTER_ACTION, unit=ally, target=enemy,
                               action_type=ActionType.SKILL, damage=100, is_crit=False,
                               engine=engine)
        assert any(m.source == "LightCone_21011" for m in ally.stats.active_modifiers)


# ============================================================
#  TestQuidProQuo — 21021 等价交换 (4★ 丰饶)
#  TURN_START→随机低能队友回能
# ============================================================


class TestQuidProQuo:
    """验证回合开始随机选低能量队友回能。"""

    def _make_char(self):
        c = create_test_character("T", hp=500, speed=100, atk=100)
        c.path = PathType.ABUNDANCE
        return c

    def _make_setup(self):
        char = self._make_char()
        ally = create_test_character("A", hp=500, speed=100, atk=100)
        ally.energy = 0
        ally2 = create_test_character("B", hp=500, speed=100, atk=100)
        ally2.energy = ally2.max_energy
        enemy = Enemy("E", hp=50000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char, ally, ally2], enemies=[enemy])
        engine = CombatEngine(state)
        return char, ally, ally2, enemy, state, engine

    def test_registry(self):
        lc = LightCone("21021")
        assert isinstance(lc, QuidProQuo)

    def test_lv80_stats(self):
        lc = LightCone("21021")
        assert lc.base_hp == pytest.approx(505.4, abs=0.1)

    def test_turn_start_grants_energy_to_low_ally(self):
        char, ally, _, _, _, engine = self._make_setup()
        lc = LightCone("21021", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        e_before = ally.energy
        engine.event_bus.emit(EventType.TURN_START, unit=char, engine=engine)
        assert ally.energy > e_before

    def test_high_energy_ally_not_chosen(self):
        char, _, ally2, _, _, engine = self._make_setup()
        lc = LightCone("21021", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        e_before = ally2.energy
        engine.event_bus.emit(EventType.TURN_START, unit=char, engine=engine)
        assert ally2.energy == e_before

    def test_other_unit_turn_no_effect(self):
        char, ally, _, _, _, engine = self._make_setup()
        lc = LightCone("21021", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        e_before = ally.energy
        engine.event_bus.emit(EventType.TURN_START, unit=ally, engine=engine)
        assert ally.energy == e_before


# ============================================================
#  TestTodayIsPeaceful — 21034 今日和平 (4★ 智识)
#  能量上限→DMG_BONUS公式
# ============================================================


class TestTodayIsPeaceful:
    """验证静态能量公式 DMG_BONUS = min(energy,160)×per_energy。"""

    def test_registry(self):
        lc = LightCone("21034")
        assert isinstance(lc, TodayIsPeaceful)

    def test_effect_params_s1(self):
        e = TodayIsPeacefulEffect(superimpose=1)
        assert e._PARAMS[0][0] == pytest.approx(0.002)
        assert e._PARAMS[0][1] == 160

    def test_on_equip_computes_dmg_bonus(self):
        char = create_test_character("T", hp=500, speed=100, atk=100)
        e = TodayIsPeacefulEffect(superimpose=1)
        e.on_equip(char)
        expected = min(char.max_energy, 160) * 0.002
        dmg = char.stats.get_total_stat(StatType.DMG_BONUS)
        assert dmg == pytest.approx(expected, abs=0.001)

    def test_s5_higher_bonus(self):
        char = create_test_character("T", hp=500, speed=100, atk=100)
        e = TodayIsPeacefulEffect(superimpose=5)
        e.on_equip(char)
        expected = min(char.max_energy, 160) * 0.004
        dmg = char.stats.get_total_stat(StatType.DMG_BONUS)
        assert dmg == pytest.approx(expected, abs=0.001)

    def test_unequip_cleans_up(self):
        char = create_test_character("T", hp=500, speed=100, atk=100)
        e = TodayIsPeacefulEffect(superimpose=1)
        e.on_equip(char)
        assert char.stats.get_total_stat(StatType.DMG_BONUS) > 0
        e.on_unequip(char)
        assert char.stats.get_total_stat(StatType.DMG_BONUS) == pytest.approx(0.0)


# ============================================================
#  TestWoofWalkTime — 21026 汪！散步时间！ (4★ 毁灭)
#  +  沃芙·沃克·泰姆  —  Burn/Bleed条件DMG
# ============================================================


class TestWoofWalkTime:
    """验证永久ATK + Burn/Bleed条件DMG。"""

    def _make_char(self):
        c = create_test_character("T", hp=500, speed=100, atk=100)
        c.path = PathType.DESTRUCTION
        return c

    def _make_setup(self):
        char = self._make_char()
        enemy = Enemy("E", hp=50000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])
        engine = CombatEngine(state)
        return char, enemy, state, engine

    def test_registry(self):
        lc = LightCone("21026")
        assert isinstance(lc, WoofWalkTime)

    def test_on_equip_grants_atk(self):
        char = self._make_char()
        e = WoofWalkTimeEffect(superimpose=1)
        e.on_equip(char)
        assert char.stats.get_total_stat(StatType.ATK) >= 0.10

    def test_burn_target_gets_dmg_bonus(self):
        char, enemy, _, engine = self._make_setup()
        from entities.base import DoTStatus
        enemy.dot_statuses.append(
            DoTStatus(source_character=char, element=ElementType.FIRE,
                       dot_multiplier=1.0, duration=2))
        lc = LightCone("21026", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        engine.event_bus.emit(EventType.ACTION_START, unit=char, target=enemy,
                               action_type=ActionType.SKILL, engine=engine)
        cond_mods = [m for m in char.stats.active_modifiers if m.source == "LightCone_21026_COND"]
        assert len(cond_mods) == 1

    def test_no_dot_no_dmg_bonus(self):
        char, enemy, _, engine = self._make_setup()
        lc = LightCone("21026", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        engine.event_bus.emit(EventType.ACTION_START, unit=char, target=enemy,
                               action_type=ActionType.SKILL, engine=engine)
        assert not any(m.source == "LightCone_21026_COND" for m in char.stats.active_modifiers)


# ============================================================
#  TestWeAreWildfire — 21023 我们是地火 (4★ 存护)
#  BATTLE_START 团队减伤+回血
# ============================================================


class TestWeAreWildfire:
    """验证BATTLE_START团队DMG_MITIGATION和回血。"""

    def _make_char(self):
        c = create_test_character("T", hp=500, speed=100, atk=100)
        c.path = PathType.PRESERVATION
        return c

    def _make_setup(self):
        char1 = self._make_char()
        char2 = self._make_char()
        char2.name = "A2"
        char2.hp = int(char2.max_hp * 0.5)
        enemy = Enemy("E", hp=50000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char1, char2], enemies=[enemy])
        engine = CombatEngine(state)
        return char1, char2, enemy, state, engine

    def test_registry(self):
        lc = LightCone("21023")
        assert isinstance(lc, WeAreWildfire)

    def test_lv80_stats(self):
        lc = LightCone("21023")
        assert lc.base_hp == pytest.approx(393.1, abs=0.1)

    def test_effect_params_s1(self):
        e = WeAreWildfireEffect(superimpose=1)
        assert e._PARAMS[0][0] == pytest.approx(0.30)
        assert e._PARAMS[0][1] == pytest.approx(0.08)
        assert e._PARAMS[0][2] == 5

    def test_team_heal_on_start(self):
        char1, char2, _, _, engine = self._make_setup()
        lc = LightCone("21023", superimpose=1)
        char1.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char1)
        hp_before = char2.hp
        engine.event_bus.emit(EventType.BATTLE_START)
        assert char2.hp > hp_before

    def test_team_mitigation_on_start(self):
        char1, char2, _, _, engine = self._make_setup()
        lc = LightCone("21023", superimpose=1)
        char1.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char1)
        engine.event_bus.emit(EventType.BATTLE_START)
        mit_mods = [m for m in char2.stats.active_modifiers if m.source == "LightCone_21023"]
        assert len(mit_mods) == 1
        assert mit_mods[0].duration == 5


# ============================================================
#  剩余 P3 简单光锥: Landaus, Nowhere, MakeClamor, Memories,
#  OnlySilence, SharedFeeling, Breakfast, UnderBlueSky, Warmth
# ============================================================


class TestOnlySilenceRemains:
    """验证永久ATK + ≤2敌CRIT。"""
    def _make_char(self):
        c = create_test_character("T", hp=500, speed=100, atk=100)
        c.path = PathType.HUNT
        return c
    def test_registry(self):
        lc = LightCone("21003")
        assert isinstance(lc, OnlySilenceRemains)
    def test_lv80_stats(self):
        lc = LightCone("21003")
        assert lc.base_hp == pytest.approx(505.4, abs=0.1)
    def test_on_equip_grants_atk(self):
        e = OnlySilenceRemainsEffect(superimpose=1)
        char = self._make_char(); e.on_equip(char)
        assert char.stats.get_total_stat(StatType.ATK) >= 0.16
    def test_two_enemies_grants_crit(self):
        char = self._make_char()
        e1 = Enemy("E1", hp=50000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.PHYSICAL])
        e2 = Enemy("E2", hp=50000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[e1, e2])
        engine = CombatEngine(state)
        lc = LightCone("21003", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(state, char)
        assert char.stats.get_total_stat(StatType.CRIT_RATE) >= 0.12
    def test_crit_activates_on_enemy_death(self):
        """3敌→无crit；杀1→2敌→crit激活。"""
        char = self._make_char()
        e1 = Enemy("E1", hp=1, speed=50, base_damage=0, level=1, weaknesses=[ElementType.PHYSICAL])
        e2 = Enemy("E2", hp=50000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.PHYSICAL])
        e3 = Enemy("E3", hp=50000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[e1, e2, e3])
        engine = CombatEngine(state)
        lc = LightCone("21003", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(state, char)
        assert char.stats.get_total_stat(StatType.CRIT_RATE) == pytest.approx(0.05, abs=0.001)
        e1.hp = 0
        engine.event_bus.emit(EventType.UNIT_DOWNED, unit=e1, source=char)
        assert char.stats.get_total_stat(StatType.CRIT_RATE) >= 0.12


def _make_bare_char():
    return create_test_character("T", hp=500, speed=100, atk=100)


class TestLandausChoice:
    """永久AGGRO + DMG_MITIGATION。"""
    def test_registry(self):
        lc = LightCone("21009"); assert isinstance(lc, LandausChoice)
    def test_lv80_stats(self):
        lc = LightCone("21009"); assert lc.base_hp == pytest.approx(505.4, abs=0.1)
    def test_on_equip_grants_aggro_and_mitigation(self):
        char = _make_bare_char()
        e = LandausChoiceEffect(superimpose=1); e.on_equip(char)
        assert char.stats.get_total_stat(StatType.AGGRO_MODIFIER) >= 2.0
        assert char.stats.get_total_stat(StatType.DMG_MITIGATION) >= 0.16


class TestNowhereToRun:
    """永久ATK + ON_KILL回血。"""
    def test_registry(self):
        lc = LightCone("21033"); assert isinstance(lc, NowhereToRun)
    def test_on_equip_grants_atk(self):
        e = NowhereToRunEffect(superimpose=1); char = _make_bare_char(); e.on_equip(char)
        assert char.stats.get_total_stat(StatType.ATK) >= 0.24
    def test_on_kill_heals(self):
        char = _make_bare_char(); enemy = Enemy("E", hp=1, speed=50, base_damage=0, level=1, weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy]); engine = CombatEngine(state)
        lc = LightCone("21033", superimpose=1); char.equip_light_cone(lc); lc.effect.on_combat_start(state, char)
        char.hp = 100; hp = char.hp
        with patch.object(state, '_notify_death'):
            engine.event_bus.emit(EventType.ON_KILL, source=char, target=enemy, action_type=ActionType.BASIC_ATTACK)
        assert char.hp > hp


class TestMakeWorldClamor:
    """BATTLE_START回能 + 永久ULT_DMG。"""
    def test_registry(self):
        lc = LightCone("21013"); assert isinstance(lc, MakeWorldClamor)
    def test_effect_params_s1(self):
        e = MakeWorldClamorEffect(superimpose=1)
        assert e._PARAMS[0][0] == pytest.approx(0.32)
        assert e._PARAMS[0][1] == 20
    def test_on_equip_grants_ult_dmg(self):
        e = MakeWorldClamorEffect(superimpose=1); char = _make_bare_char(); e.on_equip(char)
        assert char.stats.get_total_stat(StatType.ULT_DMG) >= 0.32
    def test_battle_start_grants_energy(self):
        char = _make_bare_char()
        state = GameState(characters=[char], enemies=[]); engine = CombatEngine(state)
        lc = LightCone("21013", superimpose=1); char.equip_light_cone(lc); lc.effect.on_combat_start(state, char)
        e = char.energy; engine.event_bus.emit(EventType.BATTLE_START)
        assert char.energy > e


class TestMemoriesOfThePast:
    """永久BREAK + 攻击回能1/回合。"""
    def test_registry(self):
        lc = LightCone("21004"); assert isinstance(lc, MemoriesOfThePast)
    def test_on_equip_grants_break(self):
        e = MemoriesOfThePastEffect(superimpose=1); char = _make_bare_char(); e.on_equip(char)
        assert char.stats.get_total_stat(StatType.BREAK_EFFECT) >= 0.28
    def test_attack_grants_energy(self):
        char = _make_bare_char(); enemy = Enemy("E", hp=50000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy]); engine = CombatEngine(state)
        lc = LightCone("21004", superimpose=1); char.equip_light_cone(lc); lc.effect.on_combat_start(state, char)
        e = char.energy; engine.event_bus.emit(EventType.ON_DAMAGE_DEALT, source=char, target=enemy, damage=100, damage_type=DamageType.DIRECT)
        assert char.energy > e
    def test_once_per_turn(self):
        char = _make_bare_char(); enemy = Enemy("E", hp=50000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy]); engine = CombatEngine(state)
        lc = LightCone("21004", superimpose=1); char.equip_light_cone(lc); lc.effect.on_combat_start(state, char)
        engine.event_bus.emit(EventType.ON_DAMAGE_DEALT, source=char, target=enemy, damage=100, damage_type=DamageType.DIRECT)
        e1 = char.energy
        engine.event_bus.emit(EventType.ON_DAMAGE_DEALT, source=char, target=enemy, damage=100, damage_type=DamageType.DIRECT)
        assert char.energy == e1


class TestSharedFeeling:
    """永久HEAL_BOOST + 战技后 team回能。"""
    def test_registry(self):
        lc = LightCone("21007"); assert isinstance(lc, SharedFeeling)
    def test_on_equip_grants_heal_boost(self):
        e = SharedFeelingEffect(superimpose=1); char = _make_bare_char(); e.on_equip(char)
        assert char.stats.get_total_stat(StatType.OUTGOING_HEALING_BOOST) >= 0.10
    def test_skill_grants_team_energy(self):
        char = _make_bare_char(); char2 = _make_bare_char(); char2.name = "A2"
        enemy = Enemy("E", hp=50000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char, char2], enemies=[enemy]); engine = CombatEngine(state)
        lc = LightCone("21007", superimpose=1); char.equip_light_cone(lc); lc.effect.on_combat_start(state, char)
        e1, e2 = char.energy, char2.energy
        engine.event_bus.emit(EventType.AFTER_ACTION, unit=char, target=enemy, action_type=ActionType.SKILL, damage=100, is_crit=False, engine=engine)
        assert char.energy > e1 and char2.energy > e2


class TestSeriousnessOfBreakfast:
    """永久DMG_BONUS + ON_KILL ATK叠层。"""
    def test_registry(self):
        lc = LightCone("21027"); assert isinstance(lc, SeriousnessOfBreakfast)
    def test_on_equip_grants_dmg_bonus(self):
        e = SeriousnessOfBreakfastEffect(superimpose=1); char = _make_bare_char(); e.on_equip(char)
        assert char.stats.get_total_stat(StatType.DMG_BONUS) >= 0.12
    def test_kill_stacks_atk(self):
        char = _make_bare_char(); e = Enemy("E", hp=1, speed=50, base_damage=0, level=1, weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[e]); engine = CombatEngine(state)
        lc = LightCone("21027", superimpose=1); char.equip_light_cone(lc); lc.effect.on_combat_start(state, char)
        with patch.object(state, '_notify_death'):
            engine.event_bus.emit(EventType.ON_KILL, source=char, target=e, action_type=ActionType.BASIC_ATTACK)
        atk_mods = [m for m in char.stats.active_modifiers if m.source == "LightCone_21027_ATK"]
        assert any(m.stat_type == StatType.ATK for m in atk_mods)


class TestUnderTheBlueSky:
    """永久ATK + ON_KILL CRIT_RATE 3T。"""
    def test_registry(self):
        lc = LightCone("21019"); assert isinstance(lc, UnderTheBlueSky)
    def test_on_equip_grants_atk(self):
        e = UnderTheBlueSkyEffect(superimpose=1); char = _make_bare_char(); e.on_equip(char)
        assert char.stats.get_total_stat(StatType.ATK) >= 0.16
    def test_kill_grants_crit_rate(self):
        char = _make_bare_char(); e = Enemy("E", hp=1, speed=50, base_damage=0, level=1, weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[e]); engine = CombatEngine(state)
        lc = LightCone("21019", superimpose=1); char.equip_light_cone(lc); lc.effect.on_combat_start(state, char)
        with patch.object(state, '_notify_death'):
            engine.event_bus.emit(EventType.ON_KILL, source=char, target=e, action_type=ActionType.BASIC_ATTACK)
        assert char.stats.get_total_stat(StatType.CRIT_RATE) >= 0.12


class TestWarmthShortensColdNights:
    """永久HP + BA/SKILL后 team heal。"""
    def test_registry(self):
        lc = LightCone("21028"); assert isinstance(lc, WarmthShortensColdNights)
    def test_on_equip_grants_hp(self):
        e = WarmthShortensColdNightsEffect(superimpose=1); char = _make_bare_char(); e.on_equip(char)
        assert char.stats.get_total_stat(StatType.HP) >= 0.16
    def test_basic_heals_team(self):
        char = _make_bare_char(); char.hp = 300; char2 = _make_bare_char(); char2.name = "A2"; char2.hp = 300
        enemy = Enemy("E", hp=50000, speed=50, base_damage=0, level=1, weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char, char2], enemies=[enemy]); engine = CombatEngine(state)
        lc = LightCone("21028", superimpose=1); char.equip_light_cone(lc); lc.effect.on_combat_start(state, char)
        engine.event_bus.emit(EventType.AFTER_ACTION, unit=char, target=enemy, action_type=ActionType.BASIC_ATTACK, damage=100, is_crit=False, engine=engine)
        assert char.hp > 300 and char2.hp > 300


# ============================================================
#  TestCruising — 24001 星海巡航 (5★ 巡猎)
#  Herta Shop 光锥: PERM CRIT + per-target + ON_KILL ATK
# ============================================================


class TestCruising:
    """验证 5★ 巡猎光锥 星海巡航空的三重特效。"""

    def _make_char(self):
        c = create_test_character("T", hp=500, speed=100, atk=100, crit_rate=0.05)
        c.path = PathType.HUNT
        return c

    def _make_setup(self):
        char = self._make_char()
        enemy = Enemy("E", hp=100000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])
        engine = CombatEngine(state)
        return char, enemy, state, engine

    def test_registry(self):
        lc = LightCone("24001")
        assert isinstance(lc, Cruising)
        assert lc.id == "24001"
        assert lc.name == "星海巡航"

    def test_lv80_stats(self):
        lc = LightCone("24001")
        assert lc.base_hp == pytest.approx(505.44)
        assert lc.base_atk == pytest.approx(280.8)
        assert lc.base_def == pytest.approx(245.7)

    def test_effect_params_s1(self):
        e = CruisingEffect(superimpose=1)
        assert e._PARAMS[0][0] == pytest.approx(0.08)
        assert e._PARAMS[0][1] == pytest.approx(0.50)
        assert e._PARAMS[0][2] == pytest.approx(0.08)
        assert e._PARAMS[0][3] == pytest.approx(0.20)
        assert e._PARAMS[0][4] == 2

    def test_effect_params_s5(self):
        e = CruisingEffect(superimpose=5)
        assert e._PARAMS[4][0] == pytest.approx(0.16)
        assert e._PARAMS[4][3] == pytest.approx(0.40)

    def test_on_equip_grants_permanent_crit(self):
        """Part 1: 永久暴击率。"""
        char = self._make_char()
        e = CruisingEffect(superimpose=1)
        e.on_equip(char)
        assert char.stats.get_total_stat(StatType.CRIT_RATE) == pytest.approx(0.05 + 0.08)

    def test_hp_below_50_extra_crit(self):
        """Part 2: HP≤50% → ACTION_START 时额外暴击率生效。"""
        char, enemy, _, engine = self._make_setup()
        lc = LightCone("24001", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        enemy.hp = 30000
        engine.event_bus.emit(EventType.ACTION_START, unit=char, target=enemy,
                               action_type=ActionType.BASIC_ATTACK, engine=engine)
        cond = [m for m in char.stats.active_modifiers if m.source == "LightCone_24001_COND"]
        assert len(cond) == 1
        assert cond[0].value == pytest.approx(0.08)

    def test_hp_above_50_no_extra_crit(self):
        """HP>50% → 额外暴击率不生效。"""
        char, enemy, _, engine = self._make_setup()
        lc = LightCone("24001", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        enemy.hp = 80000
        engine.event_bus.emit(EventType.ACTION_START, unit=char, target=enemy,
                               action_type=ActionType.BASIC_ATTACK, engine=engine)
        assert not any(m.source == "LightCone_24001_COND" for m in char.stats.active_modifiers)

    def test_hp_equal_50_extra_crit(self):
        """HP=50% → ≤ 条件成立，额外暴击率生效。"""
        char, enemy, _, engine = self._make_setup()
        lc = LightCone("24001", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        enemy.hp = 50000
        engine.event_bus.emit(EventType.ACTION_START, unit=char, target=enemy,
                               action_type=ActionType.BASIC_ATTACK, engine=engine)
        assert any(m.source == "LightCone_24001_COND" for m in char.stats.active_modifiers)

    def test_extra_crit_cleared_after_action(self):
        """AFTER_ACTION 后额外暴击率被 purge。"""
        char, enemy, _, engine = self._make_setup()
        lc = LightCone("24001", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        enemy.hp = 30000
        engine.event_bus.emit(EventType.ACTION_START, unit=char, target=enemy,
                               action_type=ActionType.BASIC_ATTACK, engine=engine)
        assert any(m.source == "LightCone_24001_COND" for m in char.stats.active_modifiers)
        engine.event_bus.emit(EventType.AFTER_ACTION, unit=char, target=enemy,
                               action_type=ActionType.BASIC_ATTACK, damage=100, is_crit=False,
                               engine=engine)
        assert not any(m.source == "LightCone_24001_COND" for m in char.stats.active_modifiers)

    def test_different_targets_rechecked(self):
        """换目标后重新检查HP条件。"""
        char, _, _, engine = self._make_setup()
        e_low = Enemy("EL", hp=100000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        e_high = Enemy("EH", hp=100000, speed=50, base_damage=0, level=1,
                        weaknesses=[ElementType.PHYSICAL])
        engine.state.enemies = [e_low, e_high]
        lc = LightCone("24001", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        e_low.hp = 30000
        engine.event_bus.emit(EventType.ACTION_START, unit=char, target=e_low,
                               action_type=ActionType.BASIC_ATTACK, engine=engine)
        assert any(m.source == "LightCone_24001_COND" for m in char.stats.active_modifiers)
        engine.event_bus.emit(EventType.AFTER_ACTION, unit=char, target=e_low,
                               action_type=ActionType.BASIC_ATTACK, damage=100, is_crit=False,
                               engine=engine)
        engine.event_bus.emit(EventType.ACTION_START, unit=char, target=e_high,
                               action_type=ActionType.BASIC_ATTACK, engine=engine)
        assert not any(m.source == "LightCone_24001_COND" for m in char.stats.active_modifiers)
        engine.event_bus.emit(EventType.AFTER_ACTION, unit=char, target=e_high,
                               action_type=ActionType.BASIC_ATTACK, damage=100, is_crit=False,
                               engine=engine)

    def test_non_enemy_target_ignored(self):
        """队友目标（无 dot_statuses）不会触发条件检查。"""
        char, _, _, engine = self._make_setup()
        lc = LightCone("24001", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        ally = self._make_char()
        ally.name = "Ally"
        engine.state.characters.append(ally)
        hp_before = sum(m.value for m in char.stats.active_modifiers
                        if m.source == "LightCone_24001_COND")
        engine.event_bus.emit(EventType.ACTION_START, unit=char, target=ally,
                               action_type=ActionType.SKILL, engine=engine)
        hp_after = sum(m.value for m in char.stats.active_modifiers
                       if m.source == "LightCone_24001_COND")
        assert hp_after == hp_before

    def test_on_kill_grants_atk(self):
        """Part 3: ON_KILL → ATK buff。"""
        char, enemy, _, engine = self._make_setup()
        lc = LightCone("24001", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        atk_before = char.stats.get_total_stat(StatType.ATK)
        engine.event_bus.emit(EventType.ON_KILL, source=char, target=enemy,
                               action_type=ActionType.BASIC_ATTACK)
        atk_mods = [m for m in char.stats.active_modifiers
                    if m.source == "LightCone_24001_ATK" and m.stat_type == StatType.ATK]
        assert len(atk_mods) == 1
        assert atk_mods[0].value == pytest.approx(0.20)
        assert atk_mods[0].duration == 2

    def test_on_kill_only_for_owner(self):
        """其他人击杀不影响自己。"""
        char, enemy, _, engine = self._make_setup()
        other = self._make_char()
        other.name = "O2"
        engine.state.characters.append(other)
        lc = LightCone("24001", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        engine.event_bus.emit(EventType.ON_KILL, source=other, target=enemy,
                               action_type=ActionType.BASIC_ATTACK)
        assert not any(m.source == "LightCone_24001_ATK" and m.stat_type == StatType.ATK
                       for m in char.stats.active_modifiers)

    def test_kill_atk_expires_after_2_actions(self):
        """ATK buff 持续 2 次普通行动后消失。"""
        char, enemy, _, engine = self._make_setup()
        lc = LightCone("24001", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        engine.event_bus.emit(EventType.ON_KILL, source=char, target=enemy,
                               action_type=ActionType.BASIC_ATTACK)
        mods = lambda: [m for m in char.stats.active_modifiers
                    if m.source == "LightCone_24001_ATK" and m.stat_type == StatType.ATK]
        assert len(mods()) == 1
        engine._decrement_modifiers(unit=char)
        assert mods()[0].duration == 1
        engine._decrement_modifiers(unit=char)
        assert len(mods()) == 0

    def test_unequip_cleans_all(self):
        """卸下光锥后清除所有 modifier。"""
        char, enemy, _, engine = self._make_setup()
        lc = LightCone("24001", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        enemy.hp = 30000
        engine.event_bus.emit(EventType.ACTION_START, unit=char, target=enemy,
                               action_type=ActionType.BASIC_ATTACK, engine=engine)
        engine.event_bus.emit(EventType.ON_KILL, source=char, target=enemy,
                               action_type=ActionType.BASIC_ATTACK)
        assert any(m.source in ("LightCone_24001_CRIT", "LightCone_24001_ATK") for m in char.stats.active_modifiers)
        assert any(m.source == "LightCone_24001_COND" for m in char.stats.active_modifiers)
        char.equip_light_cone(LightCone(id="Bare", base_hp=10, base_atk=10, base_def=10))
        assert not any(m.source.startswith("LightCone_24001")
                       for m in char.stats.active_modifiers)


# ============================================================
#  TestBeforeDawn — 23010 拂晓之前 (5★ 智识)
#  【梦身】: 战技/终结技→FUA 消费
# ============================================================


class TestBeforeDawn:
    """验证 5★ 智识光锥拂晓之前: 永久 CRIT/SKILL/ULT_DMG + 梦身 FUA。"""

    def _make_char(self):
        c = create_test_character("T", hp=500, speed=100, atk=100, crit_rate=0.05)
        c.path = PathType.ERUDITION
        return c

    def _make_setup(self):
        char = self._make_char()
        enemy = Enemy("E", hp=100000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char], enemies=[enemy])
        engine = CombatEngine(state)
        return char, enemy, state, engine

    def test_registry(self):
        lc = LightCone("23010")
        assert isinstance(lc, BeforeDawn)
        assert lc.id == "23010"
        assert lc.name == "拂晓之前"

    def test_lv80_stats(self):
        lc = LightCone("23010")
        assert lc.base_hp == pytest.approx(561.6)
        assert lc.base_atk == pytest.approx(308.88)
        assert lc.base_def == pytest.approx(245.7)

    def test_effect_params_s1(self):
        e = BeforeDawnEffect(superimpose=1)
        assert e._PARAMS[0][0] == pytest.approx(0.36)
        assert e._PARAMS[0][1] == pytest.approx(0.18)
        assert e._PARAMS[0][2] == pytest.approx(0.48)

    def test_on_equip_grants_all(self):
        """Part 1+2: 永久 CRIT_DMG + SKILL_DMG + ULT_DMG。"""
        char = self._make_char()
        e = BeforeDawnEffect(superimpose=1)
        e.on_equip(char)
        assert char.stats.get_total_stat(StatType.CRIT_DMG) >= 0.36
        assert char.stats.get_total_stat(StatType.SKILL_DMG) >= 0.18
        assert char.stats.get_total_stat(StatType.ULT_DMG) >= 0.18

    def test_skill_sets_dream_body(self):
        """战技后设置 _dream_body。"""
        char, enemy, _, engine = self._make_setup()
        lc = LightCone("23010", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        assert not lc.effect._dream_body
        engine.event_bus.emit(EventType.AFTER_ACTION, unit=char, target=enemy,
                               action_type=ActionType.SKILL, damage=100, is_crit=False,
                               tags=set(), engine=engine)
        assert lc.effect._dream_body

    def test_ult_sets_dream_body(self):
        """终结技后设置 dream_body。"""
        char, enemy, _, engine = self._make_setup()
        lc = LightCone("23010", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        engine.event_bus.emit(EventType.AFTER_ACTION, unit=char, target=enemy,
                               action_type=ActionType.ULTIMATE, damage=100, is_crit=False,
                               tags=set(), engine=engine)
        assert lc.effect._dream_body

    def test_fua_consumes_dream_body(self):
        """FUA (tags 含 follow_up) 消费梦身 + FUA_DMG 生效。"""
        char, enemy, _, engine = self._make_setup()
        lc = LightCone("23010", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        engine.event_bus.emit(EventType.AFTER_ACTION, unit=char, target=enemy,
                               action_type=ActionType.SKILL, damage=100, is_crit=False,
                               tags=set(), engine=engine)
        assert lc.effect._dream_body
        engine.event_bus.emit(EventType.ACTION_START, unit=char, target=enemy,
                               action_type=ActionType.SKILL, engine=engine,
                               tags={"follow_up"})
        dream_mods = [m for m in char.stats.active_modifiers if m.source == "LightCone_23010_DREAM"]
        assert len(dream_mods) == 1
        assert dream_mods[0].value == pytest.approx(0.48)
        engine.event_bus.emit(EventType.AFTER_ACTION, unit=char, target=enemy,
                               action_type=ActionType.SKILL, damage=100, is_crit=False,
                               tags={"follow_up"}, engine=engine)
        assert not lc.effect._dream_body
        assert not any(m.source == "LightCone_23010_DREAM" for m in char.stats.active_modifiers)

    def test_non_fua_does_not_consume(self):
        """非 FUA 动作保留梦身。"""
        char, enemy, _, engine = self._make_setup()
        lc = LightCone("23010", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        engine.event_bus.emit(EventType.AFTER_ACTION, unit=char, target=enemy,
                               action_type=ActionType.SKILL, damage=100, is_crit=False,
                               tags=set(), engine=engine)
        assert lc.effect._dream_body
        engine.event_bus.emit(EventType.ACTION_START, unit=char, target=enemy,
                               action_type=ActionType.BASIC_ATTACK, engine=engine,
                               tags=set())
        # non-fua ACTION_START should NOT apply DREAM source
        assert not any(m.source == "LightCone_23010_DREAM" for m in char.stats.active_modifiers)
        # dream body still set, since nonFUA doesn't consume
        assert lc.effect._dream_body

    def test_fua_without_dream_no_bonus(self):
        """没有梦身时 FUA 无额外加成。"""
        char, enemy, _, engine = self._make_setup()
        lc = LightCone("23010", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        engine.event_bus.emit(EventType.ACTION_START, unit=char, target=enemy,
                               action_type=ActionType.SKILL, engine=engine,
                               tags={"follow_up"})
        assert not any(m.source == "LightCone_23010_DREAM" for m in char.stats.active_modifiers)

    def test_unequip_cleans_all(self):
        char, enemy, _, engine = self._make_setup()
        lc = LightCone("23010", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        engine.event_bus.emit(EventType.AFTER_ACTION, unit=char, target=enemy,
                               action_type=ActionType.SKILL, damage=100, is_crit=False,
                               tags=set(), engine=engine)
        engine.event_bus.emit(EventType.ACTION_START, unit=char, target=enemy,
                               action_type=ActionType.SKILL, engine=engine,
                               tags={"follow_up"})
        assert any(m.source == "LightCone_23010_DREAM" for m in char.stats.active_modifiers)
        char.equip_light_cone(LightCone(id="Bare", base_hp=10, base_atk=10, base_def=10))
        assert not any(m.source.startswith("LightCone_23010")
                       for m in char.stats.active_modifiers)
        assert not lc.effect._dream_body


# ============================================================
#  TestButBattleIsntOver — 23003 但战斗还未结束 (5★ 同谐)
#  ERR + SP 计数 + 战技后队友 DMG
# ============================================================


class TestButBattleIsntOver:
    """验证 5★ 同谐光锥: ERR + 每 2 次 Ult SP + 战技后下个队友 DMG。"""

    def _make_char(self):
        c = create_test_character("T", hp=500, speed=100, atk=100)
        c.path = PathType.HARMONY
        return c

    def _make_setup(self):
        char = self._make_char()
        ally = create_test_character("A", hp=500, speed=80, atk=100)
        enemy = Enemy("E", hp=100000, speed=50, base_damage=0, level=1,
                       weaknesses=[ElementType.PHYSICAL])
        state = GameState(characters=[char, ally], enemies=[enemy])
        engine = CombatEngine(state)
        return char, ally, enemy, state, engine

    def test_registry(self):
        lc = LightCone("23003")
        assert isinstance(lc, ButBattleIsntOver)
        assert lc.id == "23003"
        assert lc.name == "但战斗还未结束"

    def test_lv80_stats(self):
        lc = LightCone("23003")
        assert lc.base_hp == pytest.approx(617.76)
        assert lc.base_atk == pytest.approx(280.8)
        assert lc.base_def == pytest.approx(245.7)

    def test_effect_params_s1(self):
        e = ButBattleIsntOverEffect(superimpose=1)
        assert e._PARAMS[0][0] == pytest.approx(0.10)
        assert e._PARAMS[0][1] == pytest.approx(0.30)
        assert e._PARAMS[0][2] == 1

    def test_on_equip_grants_err(self):
        """Part 1: 能量恢复效率。"""
        char = self._make_char()
        e = ButBattleIsntOverEffect(superimpose=1)
        e.on_equip(char)
        assert char.stats.get_total_stat(StatType.ERR) >= 0.10

    def test_ult_every_2_grants_sp(self):
        """Part 2: 每 2 次对友方终结技生成 1 SP。"""
        char, ally, _, _, engine = self._make_setup()
        lc = LightCone("23003", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        sp_before = engine.state.skill_points
        engine.event_bus.emit(EventType.ON_ULTIMATE_INSERTED, character=char, target=ally)
        assert engine.state.skill_points == sp_before
        engine.event_bus.emit(EventType.ON_ULTIMATE_INSERTED, character=char, target=ally)
        assert engine.state.skill_points == sp_before + 1

    def test_ult_on_enemy_no_sp(self):
        """对敌人放的终结技不计入 SP 计数。"""
        char, ally, enemy, _, engine = self._make_setup()
        lc = LightCone("23003", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        sp_before = engine.state.skill_points
        engine.event_bus.emit(EventType.ON_ULTIMATE_INSERTED, character=char, target=enemy)
        assert engine.state.skill_points == sp_before
        engine.event_bus.emit(EventType.ON_ULTIMATE_INSERTED, character=char, target=enemy)
        assert engine.state.skill_points == sp_before

    def test_skill_gives_next_ally_dmg(self):
        """Part 3: 战技后下一个行动队友获得 DMG_BONUS。"""
        char, ally, enemy, _, engine = self._make_setup()
        lc = LightCone("23003", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        engine.event_bus.emit(EventType.AFTER_ACTION, unit=char, target=enemy,
                               action_type=ActionType.SKILL, damage=100, is_crit=False,
                               tags=set(), engine=engine)
        dmg_mods = [m for m in ally.stats.active_modifiers if m.source == "LightCone_23003_DMG"]
        assert len(dmg_mods) == 1
        assert dmg_mods[0].value == pytest.approx(0.30)

    def test_basic_does_not_give_ally_dmg(self):
        """非战技不触发队友 DMG。"""
        char, ally, enemy, _, engine = self._make_setup()
        lc = LightCone("23003", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        engine.event_bus.emit(EventType.AFTER_ACTION, unit=char, target=enemy,
                               action_type=ActionType.BASIC_ATTACK, damage=100, is_crit=False,
                               tags=set(), engine=engine)
        assert not any(m.source == "LightCone_23003_DMG" for m in ally.stats.active_modifiers)

    def test_other_character_skill_no_effect(self):
        """非 owner 的战技不影响。"""
        char, ally, enemy, _, engine = self._make_setup()
        lc = LightCone("23003", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        engine.event_bus.emit(EventType.AFTER_ACTION, unit=ally, target=enemy,
                               action_type=ActionType.SKILL, damage=100, is_crit=False,
                               tags=set(), engine=engine)
        assert not any(m.source == "LightCone_23003_DMG" for m in ally.stats.active_modifiers)

    def test_unequip_cleans_all(self):
        char, ally, enemy, _, engine = self._make_setup()
        lc = LightCone("23003", superimpose=1)
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        engine.event_bus.emit(EventType.AFTER_ACTION, unit=char, target=enemy,
                               action_type=ActionType.SKILL, damage=100, is_crit=False,
                               tags=set(), engine=engine)
        assert any(m.source == "LightCone_23003_DMG" for m in ally.stats.active_modifiers)
        char.equip_light_cone(LightCone(id="Bare", base_hp=10, base_atk=10, base_def=10))
        assert not any(m.source == "LightCone_23003_DMG" for m in ally.stats.active_modifiers)

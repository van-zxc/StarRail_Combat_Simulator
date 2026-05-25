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

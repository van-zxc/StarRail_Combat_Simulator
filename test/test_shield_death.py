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

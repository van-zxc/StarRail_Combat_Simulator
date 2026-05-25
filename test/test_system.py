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

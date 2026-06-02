from __future__ import annotations

"""敌人系统测试 — 构造/属性/AI/伤害管道/CombatEngine 集成。"""

# mypy: ignore-errors
# pyright: reportPrivateUsage=false

from unittest.mock import patch

import pytest

from starrail_combat import (
    ActionType,
    Character,
    CombatEngine,
    DamageType,
    ElementType,
    Enemy,
    GameState,
    StatType,
    create_test_character,
    get_data_loader,
    init_data,
)

init_data()


class TestAntibaryonConstruction:
    def test_level_95_stats(self) -> None:
        a = Enemy.from_template("Antibaryon")
        assert a.atk == 718.0
        assert a.hp == 16429
        assert a.max_hp == 16429
        assert round(a.speed, 1) == 109.6
        assert a.level == 95
        assert a.max_toughness == 30.0
        assert a.element == ElementType.IMAGINARY

    def test_different_levels(self) -> None:
        for lv, expected_atk, expected_hp in [
            (1, 12, 45),
            (50, 234, 1235),
            (80, 552, 8259),
            (100, 773, 20302),
            (120, 1082, 81209),
        ]:
            a = Enemy(name="Antibaryon", level=lv)
            assert a.atk == expected_atk
            assert int(a.hp) == expected_hp

    def test_level_interpolation(self) -> None:
        a = Enemy(name="Antibaryon", level=85)
        assert a.atk > 552 and a.atk < 663

    def test_weaknesses(self) -> None:
        a = Enemy.from_template("Antibaryon")
        assert ElementType.PHYSICAL in a.weaknesses
        assert ElementType.QUANTUM in a.weaknesses
        assert ElementType.FIRE not in a.weaknesses

    def test_crit_defaults(self) -> None:
        a = Enemy.from_template("Antibaryon")
        assert a.crit_rate == 0.0
        assert a.crit_dmg == 0.20

    def test_skill_registered(self) -> None:
        a = Enemy.from_template("Antibaryon")
        skill = a._skills["obliterate"]
        assert skill.multiplier == 2.5
        assert skill.element == ElementType.IMAGINARY
        assert skill.targeting == "single"

    def test_decide_skill_returns_obliterate(self) -> None:
        a = Enemy.from_template("Antibaryon")
        char = create_test_character("Test", hp=200, speed=100, atk=50)
        state = GameState([char], [a])
        skill = a.decide_skill(state)
        assert skill.skill_id == "obliterate"


class TestBaryonConstruction:
    def test_level_95_stats(self) -> None:
        b = Enemy.from_template("Baryon")
        assert b.atk == 718.0
        assert b.element == ElementType.QUANTUM

    def test_weaknesses(self) -> None:
        b = Enemy.from_template("Baryon")
        assert ElementType.ICE in b.weaknesses
        assert ElementType.WIND in b.weaknesses

    def test_skill_element(self) -> None:
        b = Enemy.from_template("Baryon")
        assert b._skills["obliterate"].element == ElementType.QUANTUM


class TestEnemyDamagePipeline:
    def test_base_damage_calculation(self) -> None:
        from core.damage.enemy_pipeline import compute_enemy_damage

        a = Enemy.from_template("Antibaryon")
        target = create_test_character("Victim", hp=5000, speed=100, atk=100)
        target.stats._base_stats[StatType.DEF] = 500.0

        skill = a._skills["obliterate"]
        dmg = compute_enemy_damage(a, skill, target)

        expected_base = 718 * 2.5
        assert dmg > 0
        assert dmg < expected_base

    def test_defense_reduces_damage(self) -> None:
        from core.damage.enemy_pipeline import compute_enemy_damage

        a = Enemy.from_template("Antibaryon")
        high_def = create_test_character("Tank", hp=5000, speed=100, atk=100)
        high_def.stats._base_stats[StatType.DEF] = 2000.0
        low_def = create_test_character("Squish", hp=5000, speed=100, atk=100)
        low_def.stats._base_stats[StatType.DEF] = 200.0

        skill = a._skills["obliterate"]
        dmg_high = compute_enemy_damage(a, skill, high_def)
        dmg_low = compute_enemy_damage(a, skill, low_def)
        assert dmg_low > dmg_high

    @patch("random.random", return_value=0.95)
    def test_no_crit_at_zero_rate(self, _mock) -> None:
        from core.damage.enemy_pipeline import compute_enemy_damage

        a = Enemy.from_template("Antibaryon")
        assert a.crit_rate == 0.0
        target = create_test_character("V", hp=5000, speed=100, atk=100)
        target.stats._base_stats[StatType.DEF] = 500.0

        skill = a._skills["obliterate"]
        dmg = compute_enemy_damage(a, skill, target)
        assert dmg <= a.atk * skill.multiplier


class TestEnemyAI:
    def test_simple_ai_returns_first_skill(self) -> None:
        a = Enemy.from_template("Antibaryon")
        char = create_test_character("Test", hp=200, speed=100, atk=50)
        state = GameState([char], [a])
        skill = a._ai.select_skill(a, state)
        assert skill.skill_id == "obliterate"

    def test_simple_ai_skips_on_cooldown(self) -> None:
        a = Enemy.from_template("Antibaryon")
        a._skills["obliterate"].start_cooldown()
        char = create_test_character("Test", hp=200, speed=100, atk=50)
        state = GameState([char], [a])
        skill = a._ai.select_skill(a, state)
        assert skill == a._default_skill


class TestEnemyInCombatEngine:
    def test_antibaryon_deals_damage_in_battle(self) -> None:
        a = Enemy.from_template("Antibaryon")
        char = create_test_character("Victim", hp=2000, speed=200, atk=500)
        state = GameState([char], [a])
        engine = CombatEngine(state)
        result = engine.run()
        assert a.hp <= a.max_hp
        assert result in ("win", "lose")

    def test_antibaryon_energy_gain(self) -> None:
        a = Enemy.from_template("Antibaryon")
        a.gain_energy(10.0)
        assert a.energy == 0.0

    def test_cooldown_tick(self) -> None:
        a = Enemy.from_template("Antibaryon")
        skill = a._skills["obliterate"]
        skill._current_cooldown = 2
        assert not skill.available
        skill.tick_cooldown()
        assert not skill.available
        skill.tick_cooldown()
        assert skill.available


class TestBackwardCompat:
    def test_voidranger_unchanged(self) -> None:
        v = Enemy.from_template("Voidranger")
        assert v.hp == 300
        # SPD 受等级缩放: 90 * 1.32 ≈ 118 at lv95
        assert v.speed > 100
        assert v.base_damage == 25
        assert ElementType.FIRE in v.weaknesses
        assert ElementType.ICE in v.weaknesses

    def test_voidranger_attack_still_works(self) -> None:
        v = Enemy.from_template("Voidranger")
        char = create_test_character("Test", hp=200, speed=100, atk=50)
        state = GameState([char], [v])
        engine = CombatEngine(state)
        result = engine.run()
        assert result in ("win", "lose")

    def test_old_style_construction(self) -> None:
        e = Enemy(name="Custom", hp=500, speed=80, base_damage=30,
                  weaknesses=[ElementType.FIRE], level=80)
        assert e.hp == 500
        assert e.level == 80
        assert e.base_damage == 30

    def test_old_style_has_no_ai(self) -> None:
        e = Enemy(name="Custom", hp=500, speed=80, base_damage=30)
        assert e._ai is None

    def test_old_style_combat(self) -> None:
        e = Enemy(name="Legacy", hp=1000, speed=50, base_damage=40)
        v = create_test_character("Victim", hp=200, speed=100, atk=50)
        state = GameState([v], [e])
        engine = CombatEngine(state)
        result = engine.run()
        assert result in ("win", "lose")

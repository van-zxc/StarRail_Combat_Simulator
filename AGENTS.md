# Honkai: Star Rail — Turn-Based Combat Simulation Engine

## 项目结构

```
starrail_combat.py           # 入口模块 (re-export)
core/
  enums.py                   # ActionType/DamageType/StatType/ElementType/PathType 枚举
  events.py                  # EventBus: 30 事件类型 + subscribe/emit
  entity_stats.py            # EntityStats: 白值/绿值分离 + 修饰器池 + apply_modifier 叠层策略
  game_state.py              # SP/Energy/execute_action/DoT/heal/debuff/wave/technique
  combat_engine.py           # 主循环: AV推进/FUA队列/ExtraTurn/Ultimate插队/回合调度
  targeting.py               # TargetManager: Aggro/Bounce/Blast/AoE/Random/LockOn/Taunt
  toughness.py               # BreakEffectHandler + CCProcessor + Break LM表
  test_factory.py            # create_test_character()
  data_loader.py             # DataLoader: JSON 可选加载
  damage/
    __init__.py              # MULTIPLIER_CHAIN: 6种DamageType乘区链调度表
    multipliers.py           # 15个独立乘区函数 (dmg_bonus/def/res/crit/break/elation...)
    base.py                  # compute_base_damage() + Elation LM表
config/
  game_config.py             # 引擎配置: SP/Energy/Aggro/Cycle/Ambush/FollowUpEnergy
entities/
  base.py                    # Fighter/StatModifier/ShieldStatus/DoTStatus/CCStatus/CertifiedBanger/ToughnessDamagePacket/HitPacket/Memosprite
  aha.py                     # Aha 倒计时对象
  characters/
    base.py                  # BaseCharacter + _character_registry
    dan_heng/                # DanHeng (HUNT/WIND) + Elation测试技能
    march_7th/               # March7th (PRESERVATION/ICE) + 护盾/反击
    template_character/      # 标准角色模板
  enemies/
    base.py                  # BaseEnemy + hit_energy_bucket
    voidranger.py
  light_cones/
    base.py / cruising.py    # EquipmentEffect 抽象基类
  relics/
    base.py                  # BaseRelic + RelicSetManager
docs/
  todo.md                    # 开发路线图 (已完成/缺失/待实测)
original_data/               # 原始文档与数据源
test_starrail_combat.py      # pytest: 217 tests
```

## 开发约定

- Python 3.12+ / pytest
- `from __future__ import annotations` 所有文件
- dataclass 优先于手写 __init__
- 乘区为纯函数 (`core/damage/multipliers.py`)，公式与损伤截断分离
- `core/toughness.py` 处理击破效果/CC/韧性恢复
- `config/game_config.py` 保存所有可配置数值
- 事件驱动: 30 事件类型, 26 emit 点, 技能通过 `on_combat_start` 注册监听
- 叠层策略: `EntityStats.apply_modifier(mod, policy)` — refresh/independent/add_stacks/replace_weaker/replace_stronger/no_stack
- 多段攻击: `HitPacket` 列表 + `execute_multi_hit()` / `skip_action_resources`
- 波次系统: `GameState.waves` / `start_next_wave()` / `WAVE_START` emit / `av_keep_on_wave`
- 测试工厂: `create_test_character(name, hp, speed, atk, crit_rate, element, path, level, max_energy)`
- 实体注册: `Character("DanHeng")` 自动分发到 `DanHeng` 子类; `Enemy.from_template("Voidranger")`

## Agent 使用指南

1. 阅读 `docs/todo.md` 了解当前开发状态
2. 阅读 `core/` 下各模块了解引擎机制
3. 运行 `pytest test_starrail_combat.py` 验证改动
4. 运行 `python starrail_combat.py` 验证 demo
5. 变更后更新 `docs/todo.md` 和 `.agent_memory`

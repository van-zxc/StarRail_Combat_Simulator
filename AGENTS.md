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
  anti_regression.md         # 防错清单 (详细规则 + 历史案例)
original_data/                   # 原始文档与数据源
  enemy/                         # DimbreathBot 完整数据 (4.2.0, 2026-05)
    excel_output/                # MonsterConfig.json + MonsterSkillConfig.json (2027文件)
    config_character/            # 怪物技能配置 (541文件)
    config_ability/              # 怪物能力实现 (688文件)
    config_ai/                   # 怪物 AI 行为树 (688文件)
enemy_data/                      # 构建后的单文件数据源
  _data.json                     # ★ 引擎加载的唯一文件: {<tid>: {弱点/技能/AI}, _ai: {...}, _meta: {...}}
  override/                      # ★ 用户覆盖目录 — 同名文件按字段覆盖
scripts/
  download_enemy_data.ps1        # 下载脚本 (git clone 方式)
  build_enemy_data.py            # 从原始数据构建 _data.json
  split_enemy_data.py            # 废弃 (已被build替代)
test_starrail_combat.py      # pytest: 312 tests
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

## 核心约束

违反以下任意一条将导致静默 bug。详情见 `docs/anti_regression.md`。

- **禁止重复定义 Enum 类** — 重复定义会使引用旧类的 dict/map 静默失效。
- **BATTLE_END 后必须调用 `event_bus.clear_all()`** — 防止跨战斗订阅泄漏。
- **事件 emit 的 kwargs key 必须与 handler 读的 key 一致** — 用错 key 会导致条件永远不满足。
- **禁止在技能 execute() 中设置可变属性传递上下文** — 应通过事件 `**kwargs` 传递；用错会导致静默错误。
- **`from __future__ import annotations` 必须是每个 `.py` 文件的第一行非空行** — 新文件创建时就要写。
- **重复 ≥3 处的代码块必须提取为辅助函数或模块常量** — 单点修改遗漏会导致行为不一致。

## 工作准则

### 先想后写
写代码前先阅读相关模块。不清楚时问，不要猜。遇到多种方案时，列出选项而非静默选择。如果一个方案明显更简单，主动指出。

### 最小实现
只写解决问题必需的最小代码。不为未来"可能需要"的东西加抽象层。不要为单次使用的代码创建辅助类。写完问自己：这段代码能不能砍掉一半？

### 精准修改
只改与任务直接相关的代码。不要顺手重构、不改相邻代码的风格/注释/格式。你的改动产生的 orphan（不再使用的 import/变量/函数）必须清理，但不要删除改动之前就已存在的 dead code。

### 以验证为终点
每个任务都要有明确的验证标准——通常是让一个测试从红变绿。在声称"完成"之前，必须运行 `pytest test_starrail_combat.py` 确认全部通过。写法：
```
1. [步骤] → 验证: [具体检查]
2. [步骤] → 验证: [具体检查]
```

## Agent 使用指南

1. 阅读 `docs/todo.md` 了解当前开发状态
2. 阅读 `core/` 下各模块了解引擎机制
3. 阅读 `docs/anti_regression.md` 了解禁止操作
4. 运行 `pytest test_starrail_combat.py` 验证改动
5. 运行 `python starrail_combat.py` 验证 demo
6. 变更后更新 `docs/todo.md` 和 `.agent_memory`

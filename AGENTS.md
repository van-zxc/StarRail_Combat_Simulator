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

## 防错清单 (Anti-Regression Checklist)

修改代码时必须遵循以下规则，防止历史债务重现：

### 枚举
- **禁止重复定义 Enum 类** — `class ElementType(Enum):` 不得出现第二次。
  重复定义会导致第一个类变为新类的不同 shadow，模块级引用该类的 dict/map 会静默失效。
  *已修复: 2026-05-22 (removed duplicate ElementType in core/enums.py)*

### 事件系统
- **事件 emit 必须在战斗结束时清理** — BATTLE_END 后调用 `event_bus.clear_all()`。
  缺少清理会导致角色实例复用时事件监听器累积，每次事件触发多次回调。
  *已修复: 2026-05-22 (added EventBus.clear_all() + CombatEngine cleanup)*
- **事件 kwargs key 必须与 emit 端一致** — emit 用 `source=xxx`，handler 就必须读 `kwargs.get("source")`。
  用错 key (如 `breaker` 对应 `source`) 会导致条件永远不满足。
  *已修复: 2026-05-22 (HimekoE4 breaker→source)*

### 角色技能
- **禁止在技能 execute() 中设置可变属性 (`_killing_action`) 来传递上下文** —
  应通过事件的 `**kwargs` 传递 `action_type`，否则新增技能遗漏赋值会导致静默错误。
  *已修复: 2026-05-22 (removed all _killing_action, replaced with action_type in ON_KILL kwargs)*

### 代码质量
- **重复代码块必须提取** — 发现同一个逻辑在 3+ 处重复时，立即提取为辅助函数/模块常量。
  典型：SPD 重算逻辑（5 处 → 提取为 `_recalc_spd_if_changed`）、action_name 解析（3 处 → 提取为 `_ACTION_NAMES` dict）。
- **`from __future__ import annotations` 必须是每个 `.py` 文件的第一行非空行**。
  添加新文件时包含它，不要事后批量补。

### 版本兼容
- **禁止用 PowerShell `Set-Content` 修改 `.py` 文件** — 它会破坏 UTF-8 编码。
  始终用 Python 脚本或直接 Edit 工具。
- **所有工具脚本操作 `.py` 文件时必须指定 `encoding='utf-8'`**。

## Agent 使用指南

1. 阅读 `docs/todo.md` 了解当前开发状态
2. 阅读 `core/` 下各模块了解引擎机制
3. 运行 `pytest test_starrail_combat.py` 验证改动
4. 运行 `python starrail_combat.py` 验证 demo
5. 变更后更新 `docs/todo.md` 和 `.agent_memory`

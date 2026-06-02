# 敌人实现管线 (Enemy Pipeline)

> 本文档记录从原始数据到引擎完整实现的敌人构筑流程。
> Agent 必须按此方法论添加每个敌人的完整机制。
> 基于 Antibaryon / Baryon / Voidranger 的实战经验修订。

---

## 一、架构概览

敌人系统采用 **JSON 数值 + Python 逻辑** 双层分离架构：

```
EnemyConfig (数据层，JSON 驱动)
  ├── level_stats     → 等级成长表
  ├── weaknesses      → 弱点属性列表
  ├── skills          → 技能列表 (EnemySkill × N)
  │     └── effects   → 可组合效果 (DamageEffect | DebuffEffect | DoTEffect | ...)
  └── ai              → AI 决策策略

BaseEnemy (逻辑层，Python 类)
  ├── _init_from_config()   → 从 EnemyConfig 初始化
  ├── decide_skill(state)   → AI 选择技能
  ├── atk / crit_rate / ... → 属性代理
  └── energy / cooldown     → 资源管理
```

伤害管线独立于上述两层，由 `CombatEngine` 调用 `core/damage/enemy_pipeline.py`。

---

## 二、文件结构

```
entities/enemies/
├── __init__.py                 # 聚合注册 + 子包导入
├── base.py                     # BaseEnemy — 敌人基类
├── enemy_skill.py              # EnemySkill + SkillEffect 类型族
├── enemy_ai.py                 # SimpleAI / PriorityAI / 行为树骨架
├── enemy_config.py             # EnemyConfig + load_config_from_json()
│
├── antibaryon/
│   ├── __init__.py             # class Antibaryon (8行)
│   └── data.json               # 纯数值
│
├── baryon/
│   ├── __init__.py
│   └── data.json
│
├── voidranger/
│   ├── __init__.py             # class Voidranger (旧式兼容)
│   └── data.json
│
└── template/
    ├── __init__.py             # 新敌人起手式 (复制即用)
    └── data.json               # 字段说明模板
```

### 相关模块

| 模块 | 用途 |
|------|------|
| `core/damage/enemy_pipeline.py` | 敌人→角色六乘区伤害计算 |
| `core/combat_engine.py` | `_execute_enemy_turn()` 路由 (AI活动→新管道, 无AI→旧攻击) |
| `core/targeting.py` | 目标选择 (复用于单目标索敌) |
| `core/toughness.py` | 击破效果 / CC 处理 (敌人作为受击方) |
| `test/test_enemies.py` | 敌人测试 (构造/属性/AI/伤害/集成/兼容) |

---

## 三、JSON 格式 (`data.json`)

### 完整字段

```json
{
  "name": "Antibaryon",
  "element": "Imaginary",
  "weaknesses": ["Physical", "Quantum"],
  "max_toughness": 30.0,
  "base_res": 0.20,
  "crit_rate": 0.0,
  "crit_dmg": 0.20,
  "hit_energy_bucket": 10.0,
  "max_energy": null,
  "level_stats": {
    "1":  {"hp": 45,  "atk": 12,  "def": 210, "spd": 83,   "ehr": 0.00, "eres": 0.00},
    "95": {"hp": 16429,"atk": 718, "def": 1150,"spd": 109.6,"ehr": 0.36, "eres": 0.10}
  },
  "skills": [
    {
      "skill_id": "obliterate",
      "name": "Obliterate",
      "multiplier": 2.5,
      "element": "Imaginary",
      "targeting": "single",
      "cooldown": 0,
      "energy_gain": 10.0,
      "energy_cost": 0.0,
      "effects": []
    }
  ],
  "ai": {"type": "simple"}
}
```

### 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|:---:|------|
| `name` | string | 是 | 怪物显示名，与目录名一致 |
| `element` | string | 是 | 伤害元素：`"Physical"` `"Fire"` `"Ice"` `"Lightning"` `"Wind"` `"Quantum"` `"Imaginary"` |
| `weaknesses` | [string] | 是 | 弱点元素列表 |
| `max_toughness` | float | 是 | 韧性条上限，0=无韧性 |
| `base_res` | float | 否 | 非弱点元素的基础抗性，默认 0.20 |
| `crit_rate` | float | 否 | 基础暴击率，默认 0.0 |
| `crit_dmg` | float | 否 | 基础暴击伤害加成，默认 0.20 |
| `hit_energy_bucket` | float | 否 | 受击回能基准值，默认 10.0 |
| `max_energy` | float\|null | 否 | 能量上限，null=无能量系统 |
| `level_stats` | {string: object} | 是 | 等级→属性表，key为字符串表示等级 |
| `level_stats.LV.hp` | float | 是 | 该等级的基础HP |
| `level_stats.LV.atk` | float | 是 | 该等级的基础ATK |
| `level_stats.LV.def` | float | 是 | 该等级的基础DEF |
| `level_stats.LV.spd` | float | 是 | 该等级的基础SPD |
| `level_stats.LV.ehr` | float | 是 | 该等级的效果命中 |
| `level_stats.LV.eres` | float | 是 | 该等级的效果抵抗 |
| `skills` | [object] | 否 | 技能列表 |
| `skills[].skill_id` | string | 是 | 技能唯一ID (如 `"obliterate"`) |
| `skills[].name` | string | 否 | 显示名 |
| `skills[].multiplier` | float | 是 | ATK倍率 |
| `skills[].element` | string | 是 | 技能伤害元素 |
| `skills[].targeting` | string | 是 | 目标类型：`"single"` `"aoe"` |
| `skills[].cooldown` | int | 否 | 冷却回合数，默认0 |
| `skills[].energy_gain` | float | 否 | 使用时回复能量，默认10.0 |
| `skills[].energy_cost` | float | 否 | 使用消耗能量，默认0 |
| `skills[].effects` | [object] | 否 | 附加效果列表 |
| `ai.type` | string | 是 | AI类型：`"simple"` `"priority"` |

### 枚举值对照

游戏中原始数据使用整数，JSON 中统一用**字符串**（大小写不敏感，加载时 `.upper()` 转换）：

| 枚举 | Python Enum | JSON 字符串 |
|------|-------------|-------------|
| ElementType | `ElementType.IMAGINARY` | `"Imaginary"` / `"IMAGINARY"` |
| ElementType | `ElementType.PHYSICAL` | `"Physical"` / `"PHYSICAL"` |
| ElementType | `ElementType.QUANTUM` | `"Quantum"` / `"QUANTUM"` |

---

## 四、加载管线

```
Enemy.from_template("Antibaryon")
  │
  ├── 1. __new__ → _enemy_registry["Antibaryon"] → Antibaryon 子类
  │
  ├── 2. Antibaryon.__init__(level=95)
  │       └── load_config_from_json(Path(__file__).parent)
  │             ├── 读取 data.json
  │             ├── 枚举字符串 → ElementType[name.upper()]
  │             ├── level_stats 键 → int()
  │             ├── skills → [EnemySkill(...), ...]
  │             ├── ai → SimpleAI() | PriorityAI()
  │             └── 返回 EnemyConfig(...)
  │
  ├── 3. BaseEnemy.__init__(level=95, config=EnemyConfig)
  │       └── _init_from_config()
  │             ├── _resolve_level_stats(config, level)  # 查表/插值
  │             ├── EntityStats(HP, ATK, DEF, SPD, EHR, ERES, CRIT_RATE, CRIT_DMG)
  │             └── _skills, _ai, _default_skill, _energy
  │
  └── 4. BaseEnemy 注册表自发现 (__init_subclass__)
```

### 等级查表/插值规则

1. `level` 在表中精确命中 → 直接取那一行
2. `level` < 最小键 → 取最小键的行
3. `level` > 最大键 → 取最大键的行
4. 中间值 → 相邻两行线性插值

---

## 五、技能系统

### EnemySkill

```python
@dataclass
class EnemySkill:
    skill_id: str           # 唯一标识
    name: str               # 显示名
    multiplier: float       # ATK 倍率
    element: ElementType    # 伤害元素
    targeting: str          # "single" | "aoe"
    cooldown: int = 0       # 冷却回合
    energy_gain: float      # 使用时回能
    energy_cost: float      # 消耗能量
    effects: list[SkillEffect]  # 附加效果
```

### SkillEffect 类型族（7种）

| 类型 | 用途 | 关键字段 |
|------|------|---------|
| `DamageEffect` | 额外伤害 | `extra_multiplier`, `element` |
| `DebuffEffect` | 施加负面状态 | `stat_type`, `value`, `base_chance`, `duration` |
| `DoTEffect` | 施加持续伤害 | `element`, `dot_multiplier`, `duration`, `base_chance` |
| `BuffEffect` | 自身/友军增益 | `stat_type`, `value`, `duration` |
| `HealEffect` | 恢复生命 | `multiplier` (基于maxHP), `flat_amount` |
| `ShieldEffect` | 施加护盾 | `multiplier` (基于ATK), `flat_amount`, `duration` |
| `SummonEffect` | 召唤敌人 | `enemy_template`, `count` |

### 效果执行

所有效果在 `CombatEngine._apply_skill_effects()` 中按类型分发结算，无需技能 `execute()` 方法体。

---

## 六、AI 系统

### 三层 AI 体系

| AI 类型 | 适用 | 决策方式 |
|---------|------|---------|
| `SimpleAI` | Minion (1个技能) | 返回 `_skills` 中第一个可用技能 |
| `PriorityAI` | Elite (2~4个技能) | 按 `_rules` 优先级匹配条件→技能 |
| `BehaviorTree` | Boss (4+技能/多阶段) | 行为树节点组合 (Selector/Sequence/Condition/Action) |

### SimpleAI

```json
{"ai": {"type": "simple"}}
```

无配置参数，永远返回第一个 `cooldown=0` 且 `energy_cost ≤ current_energy` 的技能。

### PriorityAI

```json
{
  "ai": {
    "type": "priority",
    "rules": [
      {"condition": "hp_below:0.5", "skill_id": "heal_self"},
      {"condition": "cd_ready:summon", "skill_id": "summon_baryon"},
      {"condition": "always", "skill_id": "basic_attack"}
    ]
  }
}
```

支持的 condition 字符串：
- `"always"` — 永远命中
- `"hp_below:<pct>"` — 自身HP低于百分比
- `"cd_ready:<skill_id>"` — 指定技能冷却完毕
- `"energy_ready:<threshold>"` — 能量超阈值

### 行为树骨架 (用于 Boss)

```
BTSelector  → 第一个成功的子节点
BTSequence  → 全部子节点成功才成功
BTCondition → 检查条件 (hp_below / phase_is / skill_ready)
BTAction    → 选中技能写入 blackboard
```

当前节点实现已就绪，JSON 驱动的行为树加载器待 Boss 实战时补齐。

---

## 七、伤害管线

### 敌人→角色 六乘区公式

```
BaseDamage = enemy.ATK × skill.multiplier

FinalDamage = BaseDamage
  × Resistance(1.0 - min(max(target.RES, -1.0), 0.9))
  × Defense(enemy_level_base / (effective_target_DEF + enemy_level_base))
  × Vulnerability(1.0 + target.VULNERABILITY + element_VULN)
  × WEAKEN(1.0 - target.WEAKEN)
  × DMG_Bonus(1.0 + enemy.DMG_BONUS)
  × Crit(1.0 + enemy.CRIT_DMG, if crit; else 1.0)
```

**与角色→敌人的差异**：
- 无 Resistance 弱点匹配 (角色无天然弱点)
- 无 Toughness 乘区 (角色无击破状态)
- 无 RES_PEN (敌人一般无抗性穿透)

### 调用链路

```
CombatEngine._execute_enemy_turn(enemy)
  └── enemy._ai is not None?
        ├── YES: _execute_enemy_skill_turn(enemy)
        │     ├── skill = enemy.decide_skill(state)          # AI 决策
        │     ├── targets = _get_enemy_targets(enemy, skill) # 目标选择
        │     ├── for target in targets:
        │     │     damage = compute_enemy_damage(enemy, skill, target)
        │     │     actual = target.take_damage(damage, mitigated=True)
        │     │     emit(ON_HIT)
        │     │     emit(ON_KILL) if dead
        │     └── _apply_skill_effects(enemy, skill, targets)
        │
        └── NO:  _execute_enemy_legacy_turn(enemy)          # 旧式攻击 (base_damage)
              └── enemy.attack() → target.take_damage(enemy.base_damage)
```

### 目标选择 (`_get_enemy_targets`)

| `skill.targeting` | 行为 |
|-------------------|------|
| `"single"` | `TargetManager.select_target()` (Aggro 规则) |
| `"aoe"` | 所有存活角色 |
| 其他 | 首个存活角色 (fallback) |

---

## 八、如何添加新敌人

### 3 步起手式

**步骤 1**：复制 `template/` 目录并重命名

```
cp -r entities/enemies/template entities/enemies/<新怪物名>
```

**步骤 2**：编辑 `data.json`

填入该怪物的实际数值（参考第五节 JSON 格式）。

**步骤 3**：编辑 `__init__.py`

修改两处：类名 + `_default_name`。其余代码不变。

```python
from __future__ import annotations
"""<怪物名> — <阵营·类别>"""

from pathlib import Path
from entities.enemies.base import BaseEnemy
from entities.enemies.enemy_config import load_config_from_json

_HERE = Path(__file__).parent

class <新类名>(BaseEnemy):
    _default_name = "<新类名>"

    def __init__(self, level: int = 95, **kwargs: object) -> None:
        kwargs.setdefault("name", "<新类名>")
        super().__init__(level=level, config=load_config_from_json(_HERE), **kwargs)
```

**注册**：在 `entities/enemies/__init__.py` 添加一行导入：

```python
from entities.enemies.<文件夹名> import <新类名>
```

### 自动发现

`BaseEnemy.__init_subclass__` 自动将子类的 `_default_name` 注册到 `_enemy_registry`，因此 `Enemy.from_template("新类名")` 零配置生效。

---

## 九、测试

### 测试文件

`test/test_enemies.py` 覆盖：

| 测试类 | 验证内容 |
|--------|---------|
| `TestAntibaryonConstruction` | 等级属性、弱点、暴击默认值、技能注册、AI决策 |
| `TestBaryonConstruction` | Baryon 特定属性 |
| `TestEnemyDamagePipeline` | 基础伤害计算、防御减伤、暴击判定 |
| `TestEnemyAI` | SimpleAI 选择、冷却跳过 |
| `TestEnemyInCombatEngine` | 实战集成、能量系统、冷却计数 |
| `TestBackwardCompat` | 旧式Voidranger、旧式构造、旧式战斗 |

### 添加新敌人测试

在 `test/test_enemies.py` 中新增一个测试类，按 `TestAntibaryonConstruction` 模式复制即可。

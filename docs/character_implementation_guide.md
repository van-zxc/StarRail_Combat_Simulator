# 角色实现方法论

> 本文档记录从原始 JSON 数据到引擎完整实现的标准流程。
> Agent 必须按此方法论依次添加每个角色的完整机制。
> 基于 DanHeng / March7th / PlayerGirl / Himeko / Welt / Kafka 六个角色的实战经验修订。

---

## 一、数据准备

### 1.1 数据源

角色数据已通过 `extract_character_data.py` 提取到 `character_data/` 目录。

文件名格式: `<id>_<tag>.json`（如 `1001_mar7th.json`），可通过 `character_data/_index.json` 快速查找。

### 1.2 JSON 五大模块

读取目标 `<id>_<tag>.json`，重点关注：

| 模块 | 含义 | 示例 |
|------|------|------|
| `promotions` | 各突破阶基础属性 (7阶, HP/ATK/DEF/SPD/crit/taunt) | lv80 = values[6].base + step*10 |
| `skills` | 技能名称/类型/效果/参数表/描述 | `type`: Normal/BPSkill/Ultra/Talent/Maze |
| `traces` | 行迹: `skill_upgrades` / `ability_bonuses` / `stat_bonuses` | stat_bonuses 有 `properties[].{type, value}` |
| `eidolons` | 星魂 1-6: 名称/描述/`rank`/`level_up_skills` | 逻辑型星魂 desc 不含具体数值 |
| `metadata` | 命途/元素/稀有度/能量上限/taunt | `max_sp` 可能为 null (无能量体系) |

### 1.3 参数表解读

技能 `params` 是一个二维数组: `params[skill_level - 1]` 为一维参数列表。

- 普攻: 10 级 (params[0] ~ params[9])
- 战技/终结技/天赋: 15 级 (params[0] ~ params[14])
- 秘技: 1 级

描述中的 `#N[i]` 表示使用 params[i-1][N-1] 填充。

**例外**: 行迹能力节点的 `desc` 也含 `#1[i]`，但 `params` 为空。这些值是硬编码的，需向用户确认（参 §2.4）。

### 1.4 增强版技能识别 (Base vs Enhanced)

部分角色 JSON 包含**两套**完整技能数据，用不同 ID 前缀区分：

| 版本 | ID 前缀 | 含义 |
|------|---------|------|
| Base | `1004xx` | 基础技能 |
| Enhanced | `11004xx` | 行迹/星魂解锁后的强化版（更多效果、更高倍率） |

识别方法：
1. 检查 skills 数组中是否有 `11` 前缀的 ID（如 `1100502` vs `100502`）
2. 比较两套 skills 的 params 维度：Enhanced 通常参数更多
3. 比较 description：Enhanced 通常描述更多机制
4. **遇到两套时，向用户确认使用 Enhanced 版本**

已确认使用 Enhanced 的角色: Welt (11004xx), Kafka (11005xx)。

---

## 二、语义歧义排查

### 2.1 常见模糊描述映射

| 原文表述 | 实际含义 | 来源 |
|---------|---------|------|
| "被敌方攻击的概率大幅提高" | 外部嘲讽因子 = 600% (独立乘区) | 战技 |
| "提高#1[i]%" (空 params) | +15% 冻结基础概率 | 冰咒行迹 |
| "增加#1[i]回合" (空 params) | 护盾持续 +1 回合 | 加护行迹 |
| "立即向攻击者发起反击" | FUA 队列立即插入 (不等待 AV) | 天赋 |
| "随机敌方单体" | TargetingType.RANDOM | 秘技 |
| "少量/中量/大量" | 需对照实际倍率推算 | 通用 |

### 2.2 附加伤害类型归属

描述中含 "附加伤害" 的技能 → `DamageType.ADDITIONAL_DMG`。

特性（社区实测）:
- 可独立暴击，与主体伤害无关
- 享受 ATK 增加 / 通用增伤 / 减防 / 易伤 / RES PEN
- **不享受**元素专属增伤 / 动作标签增伤 / FUA 增伤
- 不可削韧 / 不触发特效
- 享受主体破韧后的 toughness_multiplier (0.9→1.0)

### 2.3 技能作用范围

| effect | 范围 | engine target |
|--------|------|---------------|
| `SingleAttack` | 单攻 | `target` 参数直接使用 |
| `AoEAttack` | 群攻 | 遍历 `state.alive_enemies` |
| `Blast` | 扩散 | `TargetManager.select_blast(enemies, target)` |
| `Bounce` | 弹射 | `TargetManager.select_target(enemies, is_bounce=True)` |
| `Defence` / `Restore` / `Support` | 辅助 | 己方 own/ally |
| `Enhance` | 强化 | 通常为自身 buff/状态变化 |

### 2.4 常见游戏机制→引擎实现速查表

| 游戏描述 | 引擎实现 | 示例角色 |
|---------|---------|---------|
| "行动延后 X%" | `target.delay_action(X/100)` | Welt |
| "行动提前 X%" | `character.advance_action(X/100)` | DanHeng E4 |
| "立即行动" | `grant_extra_turn()` 或 `advance_action(1.0)` | — |
| "陷入冰冻/禁锢/纠缠" | `CCStatus("Freeze"/"Imprison"/"Entanglement")` + `enemy.cc_statuses.append()` | Welt |
| "陷入灼烧/触电/风化" | `DoTStatus(source, element, multiplier, duration)` + `enemy.apply_dot()` | Kafka |
| "持续伤害立即产生 X% 伤害" | `_detonate_dots(state, target, pct)` | Kafka |
| "追加攻击/反击" | `state.grant_follow_up_action(owner, skill)` | Himeko / Kafka |
| "弱点击破时" | `subscribe(ON_WEAKNESS_BREAK)` | Himeko / PlayerGirl |
| "处于减速状态" | 检查 `target.stats` 中是否有 value < 0 的 SPD 修饰器 | DanHeng / Welt |
| "敌方目标被消灭时" | `subscribe(ON_KILL)` + 检查 `source` | DanHeng E4 |
| "施放攻击后" | `subscribe(AFTER_ACTION)` + 检查 `unit == owner` | Himeko A2 |
| "回合开始时" | `subscribe(TURN_START)` + 检查 `unit == owner` | DanHeng 天赋 |
| "持续伤害提高 X%" | 用 `DMG_BONUS +X%` 近似 (无专用 DOT_DMG StatType) | Kafka E2 |
| "受到的 X 伤害提高" | `StatModifier(VULNERABILITY, FLAT, X%)` 应用到 enemy.stats | Himeko 秘技 |
| "施放攻击不消耗战技点" | `execute_action(..., skip_action_resources=True)` + 手动 `gain_energy()` | Arlan |
| "消耗自身生命值" | `owner.take_damage(hp_cost, bypass_shield=True)` 在技能 execute 开头 | Arlan |
| "多段伤害 (N次)" | `HitPacket` 列表 + `state.execute_multi_hit()` | Arlan |
| "受到致命攻击时不倒下" | `subscribe(BEFORE_DEATH)` + 恢复 HP | Arlan E4 |
| "免疫除持续伤害外的伤害" | `Fighter._nullify_direct_dmg = True` (在 `take_damage` 中拦截) | Arlan A3 |
| "消耗生命值获得伤害加成" | 每次攻击前动态计算 `DMG_BONUS` 并 apply modifier | Arlan |

### 2.5 空 params 能力行迹 — 必须向用户确认

JSON 中 ability_bonuses 的 desc 含 `#1[i]%` 但 params 为空时，**必须暂停并向用户确认数值**。常见确认项:

```
"施放攻击后有#1[i]%的基础概率使目标陷入灼烧, 持续#2[i]回合, DoT #3[i]%攻击力"
→ 问: base_chance=?, duration=?, multiplier=?
"若生命值≥#1[i]%则暴击率提高#2[i]%"
→ 问: hp_threshold=?, crit_rate=?
"效果命中大于#1[i]%时每超过#2[i]%攻击力提高#3[i]%, 最多#4[i]%"
→ 问: 阈值和步进值
```

---

## 三、引擎依赖判断

Agent 在读完全部技能和行迹描述后，必须先完成此检查清单：

```
[ ] 是否需要新的 StatType (如元素增伤/新伤害类型)
[ ] 是否需要新的状态类 (DoTStatus/FreezeDotStatus/新 CC)
[ ] 是否需要新的 DamageType 或乘区链调整
[ ] 是否需要新事件或新 emit 点
[ ] 是否需要新的目标选择模式
[ ] 是否需要 Fighter 基类新增字段
[ ] 是否需要 Enemy 基类新增字段 (如 weightless 状态字段)
[ ] 是否需要 combat_engine 新增调度逻辑
[ ] 是否需要 targeting 仇恨计算调整
[ ] 是否需要新全局辅助函数 (如 DoT 引爆、失重应用)
```

**原则: 先实现引擎扩展，再实现角色。依赖不全就动手会导致返工。**

### 3.1 引擎扩展类型参考

已有扩展记录:
- **Enemy 新字段**: `weightless_remaining_turns` / `weightless_hit_count` (Welt)
- **新全局函数**: `_detonate_dots()` / `_apply_shock()` / `_target_is_slowed()` (Kafka / DanHeng)
- **CC 类型**: Imprison 已存在於 `CCProcessor`, Freeze 通过 `CCStatus("Freeze")` 使用
- **BEFORE_DEATH 事件**: 在 `Fighter.take_damage()` 中，当 HP 降至 0 时自动 emit（防止重复通过 `_before_death_emitted` 标记；`_notify_death()` 也检查该标记避免二次 emit）。`enemy.attack()` 的直接伤害也可触发此事件。
- **伤害免疫**: `Fighter._nullify_direct_dmg` 标志，设为 True 后在 `take_damage` 中拦截首次非 DoT 伤害并翻转为 False

---

## 四、文件创建模板

### 4.1 目录结构

```
entities/characters/<name>/
    __init__.py          # from .<name> import <ClassName>
    <name>.py            # 角色类
    skills.py            # 技能类 + 全局辅助函数
    traces.py            # 行迹注册表
    eidolons.py          # 星魂注册表
```

### 4.2 角色类模板 (`<name>.py`)

```python
"""<Name> — <命途>·<元素> (lv80 数据)."""

from __future__ import annotations

from core.enums import ElementType, PathType, StatType
from core.entity_stats import stats_defaults
from entities.characters.template_character.template_character import TemplateCharacter
from entities.characters.<name>.skills import (...)
from entities.characters.<name>.traces import TRACE_REGISTRY
from entities.characters.<name>.eidolons import EIDOLON_REGISTRY

class <Name>(TemplateCharacter):
    _default_id = "<Name>"
    _default_level = 80
    _default_element = ElementType.XXX
    _default_path = PathType.XXX

    # promotions.values[6].base + step*10 (lv80)
    _base_stats = {
        **stats_defaults(),
        StatType.HP: ...,
        StatType.ATK: ...,
        StatType.DEF: ...,
        StatType.SPD: ...,
        StatType.CRIT_RATE: 0.05,
        StatType.CRIT_DMG: 0.50,
        StatType.ERR: 1.0,
        StatType.MAX_ENERGY: ...,   # JSON max_sp
        StatType.AGGRO_MODIFIER: ...,  # (base_taunt / 100) - 1.0
    }

    def __init__(self, character_id="", level=None, unlocked_traces=None, eidolon_level=0):
        # ⚠️ 状态标记必须在 super().__init__() 之前初始化
        # 否则 _init_traces / _init_eidolons 设置的值会被覆写为 False
        self._has_xxx: bool = False
        self._has_e1: bool = False
        self._has_e2: bool = False
        self._counter_field: int = 0

        super().__init__(character_id, level, unlocked_traces, eidolon_level)

    def _init_skills(self) -> None:
        self._skills["basic"] = <Name>BasicAttack(self)
        self._skills["skill"] = <Name>Skill(self)
        self._skills["ultimate"] = <Name>Ultimate(self)
        self._skills["talent"] = <Name>Talent(self)
        self._skills["technique"] = <Name>Technique(self)

    def _init_traces(self, unlocked: list[str]) -> None:
        self._has_xxx = "XxxAbility" in unlocked
        for key in unlocked:
            fn = TRACE_REGISTRY.get(key)
            if fn:
                for mod in fn(self):
                    self.stats.add_modifier(mod)

    def _init_eidolons(self, level: int) -> None:
        for lv in range(1, level + 1):
            fn = EIDOLON_REGISTRY.get(lv)
            if fn:
                for mod in fn(self):
                    self.stats.add_modifier(mod)
```

**lv80 属性计算**: `promotions.values[6].base + promotions.values[6].step * 10`。

**AGGRO_MODIFIER**:
- 巡猎/智识/同谐/虚无: taunt=75 → `(75/100)-1 = -0.25`
- 毁灭: taunt=125 → `0.25`
- 存护: taunt=150 → `0.5`
- 丰饶: taunt=100 → `0.0`

### 4.2.1 角色级削韧/回能覆盖

角色的削韧值和能量回复可能与全局默认值不同。通过定义类属性 `_toughness_map` 和 `_energy_map` 实现覆盖（空 dict 使用全局 `config/game_config.py` 的默认值）：

```python
from core.enums import ActionType

_toughness_map = {
    ActionType.BASIC_ATTACK: 10.0,   # 覆盖全局默认 10
    ActionType.SKILL: 20.0,          # 覆盖全局默认 20
    ActionType.ULTIMATE: 20.0,       # 覆盖全局默认 30
}
_energy_map = {
    ActionType.BASIC_ATTACK: 20.0,   # 覆盖全局默认 20
    ActionType.SKILL: 30.0,          # 覆盖全局默认 30
    ActionType.ULTIMATE: 5.0,        # 覆盖全局默认 5
}
```

全局默认值（`config/game_config.py`）：
| ActionType | 削韧 | 回能 |
|------------|------|------|
| BASIC_ATTACK | 10.0 | 20.0 |
| SKILL | 20.0 | 30.0 |
| ULTIMATE | 30.0 | 5.0 |
| ENHANCED_BASIC | — | 30.0 |

只有需要覆盖的角色才定义这些 map。不需要的角色留空 dict，引擎会自动 fallback 到全局默认。

### 4.3 技能类模板 (`skills.py`)

#### 简单技能 (纯伤害)

```python
class <Name>BasicAttack(TemplateBasicAttack):
    skill_multiplier = 1.40   # params[9][0] (lv10)
```

#### 复杂技能 (有额外效果)

覆写 `execute(target, state)`:

```python
class <Name>Ultimate(TemplateUltimate):
    skill_multiplier = 1.80

    def execute(self, target, state) -> tuple[int, bool, float, bool]:
        dmg, crit, tough, brk = state.execute_action(
            self.owner, self.action_type, target, self.skill_multiplier,
            damage_type=self.damage_type,
        )
        # 额外效果 (debuff / DoT 引爆 / CC 等)
        return (dmg, crit, tough, brk)
```

**出参**: `(int damage, bool is_crit, float toughness, bool is_break)`

#### 群攻技能

```python
def execute(self, target, state):
    total_dmg = 0
    for enemy in state.alive_enemies:
        dmg, crit, tough, brk = state.execute_action(
            self.owner, self.action_type, enemy, self.skill_multiplier,
            damage_type=self.damage_type,
        )
        total_dmg += dmg
    return (total_dmg, total_crit, total_tough, total_brk)
```

#### 扩散技能

```python
def execute(self, target, state):
    blast_targets = TargetManager.select_blast(state.alive_enemies, target)
    total_dmg = 0
    for t in blast_targets:
        is_primary = t is target
        mult = self.primary_mult if is_primary else self.adjacent_mult
        dmg, crit, tough, brk = state.execute_action(
            self.owner, self.action_type, t, mult, damage_type=self.damage_type,
        )
        total_dmg += dmg
    return (total_dmg, total_crit, total_tough, total_brk)
```

#### 弹射技能 (Bounce)

```python
def execute(self, target, state):
    total_dmg = 0
    for i in range(num_bounces):
        t = TargetManager.select_target(self.owner, state.alive_enemies, is_bounce=True)
        if t is None:
            continue
        dmg, crit, tough, brk = state.execute_action(
            self.owner, self.action_type, t, self.skill_multiplier,
            damage_type=self.damage_type,
        )
        # 每段命中后效果 (debuff / DoT / 附加伤害)
        total_dmg += dmg
    return (total_dmg, total_crit, total_tough, total_brk)
```

#### 事件驱动技能 (天赋)

```python
class <Name>Talent:
    action_type = ActionType.TALENT
    skill_multiplier = 0.0  # 或 1.75 等 (若 FUA 有伤害)

    def __init__(self, owner) -> None:
        self.owner = owner

    def on_combat_start(self, state) -> None:
        if state.event_bus is None:
            return
        self._state_ref = state
        from core.events import EventType
        state.event_bus.subscribe(EventType.AFTER_ACTION, self._on_after_action)
        state.event_bus.subscribe(EventType.ON_WEAKNESS_BREAK, self._on_weakness_break)
        state.event_bus.subscribe(EventType.TURN_START, self._on_turn_start)
        # 根据需求订阅其他事件

    def _on_after_action(self, **kwargs) -> None:
        unit = kwargs.get("unit")
        target = kwargs.get("target")
        # 检查条件 → state.grant_follow_up_action(self.owner, self)

    def execute(self, target, state) -> tuple[int, bool, float, bool]:
        # FUA 执行时的伤害逻辑
        return (0, False, 0.0, False)
```

**可订阅事件** (`core/events.py`):
`BATTLE_START`, `WAVE_START`, `TURN_START`, `TURN_END`, `ACTION_START`, `ON_BEFORE_HIT`, `ON_HIT`, `ON_DAMAGE_DEALT`, `AFTER_ACTION`, `ON_KILL`, `ON_WEAKNESS_BREAK`, `UNIT_DOWNED`, `ON_SHIELD_APPLIED`, `HEAL_DONE` 等。

#### 秘技

```python
class <Name>Technique:
    action_type = ActionType.TALENT
    skill_multiplier = 0.0

    def __init__(self, owner) -> None:
        self.owner = owner

    def on_combat_start(self, state) -> None:
        if state.event_bus is None:
            return
        from core.events import EventType
        state.event_bus.subscribe(EventType.BATTLE_START, self._on_battle_start)

    def _on_battle_start(self, **kwargs) -> None:
        engine = kwargs.get("engine")
        if engine is None:
            return
        # 秘技效果: 全体攻击 / 施加 debuff / 治疗等

    def execute(self, target, state):
        return (0, False, 0.0, False)
```

### 4.4 DoT 引爆通用函数

```python
def _detonate_dots(state, target, detonate_pct) -> int:
    """遍历目标所有 dot_statuses, 每个 DoT 立即结算 pct 比例伤害。"""
    total = 0
    for dot in target.dot_statuses:
        source = dot.source_character
        if not source.is_alive:
            continue
        base_dmg = int(source.atk * dot.dot_multiplier * dot.stacks * detonate_pct)
        if base_dmg <= 0:
            continue
        dmg, _, _, _ = state.execute_action(
            character=source,
            action_type=ActionType.BASIC_ATTACK,
            target=target,
            skill_multiplier=0.0,
            damage_type=DamageType.DOT,
            base_damage_override=base_dmg,
            element_override=dot.element,
        )
        total += dmg
    return total
```

**关键**: `base_damage_override` 绕过 skill_multiplier 计算，直接使用 ATK × multiplier，与引擎 DoT tick 逻辑一致。

### 4.5 行迹模板 (`traces.py`)

```python
from entities.base import StatModifier
from core.enums import StatModifierType, StatType

def trace_stat_node(owner) -> list[StatModifier]:
    return [StatModifier(stat_type, modifier_type, value, source="Trace_Xxx")]

def trace_ability_node(owner) -> list[StatModifier]:
    return []  # 逻辑在技能类中通过 owner._has_xxx 判断

TRACE_REGISTRY: dict[str, callable] = {
    "Key1": trace_func1,
    "Key2": trace_func2,
}
```

**属性映射规则**:

| JSON `properties[].type` | `StatType` | `modifier_type` |
|--------------------------|------------|-----------------|
| `IceAddedRatio` / `FireAddedRatio` / etc | `ICE_DMG_BONUS` / `FIRE_DMG_BONUS` / etc | FLAT |
| `AttackAddedRatio` | `ATK` | PERCENT |
| `DefenceAddedRatio` | `DEF` | PERCENT |
| `HPAddedRatio` | `HP` | PERCENT |
| `SpeedDelta` | `SPD` | FLAT |
| `CriticalChanceBase` | `CRIT_RATE` | FLAT |
| `CriticalDamageBase` | `CRIT_DMG` | FLAT |
| `StatusResistanceBase` | `EFFECT_RES` | FLAT |
| `StatusProbabilityBase` | `EFFECT_HIT_RATE` | FLAT |
| `BreakDamageAddedRatio` | `BREAK_EFFECT` | FLAT |
| `SPRatioBase` | `ERR` | FLAT |

> 元素伤害必须用 `ICE_DMG_BONUS` 等专属类型，**不可**用通用 `DMG_BONUS`。

### 4.6 星魂模板 (`eidolons.py`)

```python
# 逻辑型星魂 — 设置标记，技能中判断
def eidolon_N(owner) -> list:
    owner._has_eN = True
    return []

# 技能升级型 — 直接改 skill_multiplier
def eidolon_N(owner) -> list:
    skill = owner._skills.get("ultimate")
    if skill:
        skill.skill_multiplier += diff_value  # params[lv13→lv15]
    return []

EIDOLON_REGISTRY: dict[int, callable] = {
    1: eidolon_1, ..., 6: eidolon_6,
}
```

**技能升级型星魂**: 对照 JSON 中 `level_up_skills[].num` (升几级)，从 params 表中取对应级差 (lv13→lv15 或 lv8→lv10)。

---

## 五、引擎扩展步骤

当检查清单 (§三) 触发引擎扩展需求时，按以下文件顺序修改：

| 步骤 | 文件 | 用途 |
|------|------|------|
| 1 | `core/enums.py` | 新增 `StatType` / `DamageType` / `EventType` |
| 2 | `entities/base.py` | 新增 `Fighter` 字段 / 新 dataclass |
| 3 | `entities/enemies/base.py` | 新增敌人类字段 (如 weightless) |
| 4 | `core/entity_stats.py` | 新增属性查询方法 |
| 5 | `core/damage/multipliers.py` | 新增/修改乘区函数 |
| 6 | `core/damage/__init__.py` | 新增 DamageType 乘区链 |
| 7 | `core/game_state.py` | 新增结算方法 |
| 8 | `core/combat_engine.py` | 新增调度点 |
| 9 | `core/targeting.py` | 新增/修改目标选择 |
| 10 | `entities/characters/<name>/skills.py` | 新增全局辅助函数 (如 `_detonate_dots`) |

**每次引擎扩展后必须立即运行 `pytest`。**

---

## 六、集成与验证

### 6.1 角色注册

完成后必须将角色导入注册表:

```python
# entities/characters/__init__.py
from entities.characters.<name> import <ClassName>
```

### 6.2 技能注册

确保 `_init_skills` 注册了所有 5 种类型:
```python
self._skills["basic"] = ...     # 必须
self._skills["skill"] = ...     # 必须
self._skills["ultimate"] = ...  # 必须
self._skills["talent"] = ...    # 必须
self._skills["technique"] = ... # 如有秘技
```

### 6.3 事件注册时机

```
顺序:
  技能.on_combat_start(state)  →  注册事件监听器
  BATTLE_START emit              →  所有监听器触发
  state.apply_techniques()       →  注册式秘技回调
```

### 6.4 验证步骤

```
1. pytest test_starrail_combat.py    # 全量测试必须全绿
2. python starrail_combat.py         # demo 无崩溃
3. 编写角色专属测试类 (≥8 tests, 见 §8)
```

### 6.5 文档更新

1. 在 `docs/todo.md` 已完成的清单中添加 `[x] <角色名>`
2. 如有引擎扩展，在架构改进记录中追加
3. 如有新机制，在本文档 §2.4 添加映射项

---

## 七、自检清单

每完成一个角色，逐项确认：

### 数据准备
```
[ ] JSON 参数映射正确 (params 数组索引 = skill_level - 1)
[ ] lv80 属性 = promotions.values[6].base + step*10
[ ] 检查是否有 Enhanced 版技能 (id 前缀 11xxxx)
[ ] 能力行迹 params 为空 → 已向用户确认数值
```

### 角色类
```
[ ] 状态标记在 super().__init__() 之前初始化 (防止被覆写)
[ ] _init_traces 中能力行迹设置了 _has_xxx 标记
[ ] _init_eidolons 中逻辑星魂设置了 _has_eN 标记
[ ] _default_id 正确 (Character("<Name>") 可自动分发)
[ ] entities/characters/__init__.py 已添加 import
```

### 技能
```
[ ] 行迹属性使用正确 StatType (元素增伤 ≠ 通用 DMG_BONUS)
[ ] 能力行迹副作用在技能 execute/on_combat_start 中正确判断
[ ] 逻辑星魂标记在技能中正确检查
[ ] 技能 element 与角色默认 element 一致 (除非 element_override)
[ ] 群攻技能遍历 alive_enemies 自己循环
[ ] 辅助技能 skill_multiplier=0 且 execute 返回 (0, False, 0.0, False)
[ ] 所有 5 种技能类型分配: basic/skill/ultimate/talent/technique
[ ] 秘技通过 BATTLE_START 事件触发
[ ] 全局辅助函数放在 skills.py 模块顶层 (_detonate_dots / _target_is_slowed 等)
[ ] 施加 debuff 前检查 target.is_alive (防止敌人已死)
```

### 测试
```
[ ] 每角色 ≥8 tests (倍率 / debuff / 行迹 / E1~E6 关键星魂)
[ ] 测试中 debuff 必中: EFFECT_RES = -1.0
[ ] 测试中暴击必中: CRIT_RATE = 1.0
[ ] 测试中 enemy HP 够高 (≥50000) 防止截断
[ ] 全量 tests 通过 + demo 无异常
```

---

## 八、测试编写指南

### 8.1 角色构造

```python
# 基础构造
char = Character("DanHeng")

# 带行迹
char = Character("Himeko", unlocked_traces=["Fire1", "StarFire", "Scorch"])

# 带星魂
char = Character("Kafka", eidolon_level=6)

# 带行迹+星魂 (全配)
char = Character("Welt", unlocked_traces=ALL_WELT_TRACES, eidolon_level=6)
```

### 8.2 常见测试模板

#### 倍率验证
```python
def test_basic_multiplier(self):
    char = Character("DanHeng")
    assert char._skills["basic"].skill_multiplier == 1.40
```

#### Debuff 施加验证 (强制命中)
```python
def test_skill_applies_debuff(self):
    char = Character("DanHeng")
    enemy = Enemy(name="E", hp=50000, speed=50, base_damage=0, level=1, weaknesses=[...])
    enemy.stats.add_modifier(StatModifier(StatType.EFFECT_RES, StatModifierType.FLAT, -1.0))
    state = GameState(characters=[char], enemies=[enemy])
    char._skills["skill"].execute(enemy, state)
    assert any(m.source == "My_Source" for m in enemy.stats.active_modifiers)
```

#### 伤害比较验证 (倍率差异)
```python
def test_damage_comparison(self):
    char = Character("Himeko", unlocked_traces=["Scorch"])
    enemy_burned = Enemy(name="E1", hp=50000, speed=50, ...)
    enemy_burned.dot_statuses.append(DoTStatus(source=char, element=ElementType.FIRE, ...))
    enemy_normal = Enemy(name="E2", hp=50000, speed=50, ...)
    state1 = GameState(characters=[char], enemies=[enemy_burned])
    dmg_burned, _, _, _ = char._skills["skill"].execute(enemy_burned, state1)
    state2 = GameState(characters=[char], enemies=[enemy_normal])
    dmg_normal, _, _, _ = char._skills["skill"].execute(enemy_normal, state2)
    assert dmg_burned > dmg_normal
```

#### 事件流测试 (手动注册+手动 emit)
```python
def test_fua_trigger(self):
    from core.events import EventType
    char = Character("Kafka")
    char._talent_count = 2
    ally = create_test_character("Ally", hp=500, speed=100)
    enemy = Enemy(name="E", hp=50000, speed=50, ...)
    state = GameState(characters=[char, ally], enemies=[enemy])
    engine = CombatEngine(state)
    char._skills["talent"].on_combat_start(state)
    state.event_bus.emit(EventType.AFTER_ACTION, unit=ally, target=enemy)
    assert state.has_follow_up_action()
    assert char._talent_count == 1
```

#### 修饰器清理验证
```python
def test_modifier_removed_on_expiry(self):
    enemy.weightless_remaining_turns = 1
    # ... apply modifiers
    state.event_bus.emit(EventType.TURN_START, unit=enemy)
    assert enemy.weightless_remaining_turns == 0
    assert not any(m.source == "My_Source" for m in enemy.stats.active_modifiers)
```

### 8.3 集成测试 (多角色队)

```python
def test_four_character_full_battle(self):
    d = Character("DanHeng", unlocked_traces=ALL_DH_TRACES, eidolon_level=6)
    pg = Character("PlayerGirl", unlocked_traces=ALL_PG_TRACES, eidolon_level=6)
    h = Character("Himeko", unlocked_traces=ALL_H_TRACES, eidolon_level=6)
    w = Character("Welt", unlocked_traces=ALL_W_TRACES, eidolon_level=6)
    enemies = [Enemy(name=f"E{i}", hp=800, speed=30, ...) for i in range(3)]
    state = GameState(characters=[d, pg, h, w], enemies=enemies)
    engine = CombatEngine(state)
    engine.run()  # 不应崩溃
    assert all(c.is_alive for c in state.characters)
    assert not any(e.is_alive for e in state.enemies)
```

### 8.4 常见测试类命名

```
Test<RoleName>        # 角色专属测试 (≥8 tests)
TestTeamIntegration   # 多角色交互测试
TestEdgeCases         # 边缘/异常终止测试
```

### 8.5 测试常见陷阱

1. **HP 截断**: `take_damage` 返回 `min(hp, damage)`，HP 不够会截断伤害比较
   - 解决: 使用 `hp=50000` 的大血包
2. **debuff 不命中**: 敌人 EFFECT_RES 默认值可能不为 0
   - 解决: 加 `EFFECT_RES = -1.0` 修改器
3. **暴击不触发**: `random.random()` 理论上可能返回 ≥1.0
   - 解决: 加 `CRIT_RATE = 1.0` 修改器 (total 1.05 确保必暴)
4. **敌人死亡后无法 debuff**: 伤害可能高于剩余 HP
   - 解决: 用 `hp=50000` 或检查 `target.is_alive`
5. **多角色测试事件冲突**: 检查 handler 注册数量
   - 解决: 使用集成测试验证 `event_bus._listeners` 长度

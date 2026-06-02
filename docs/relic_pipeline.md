# 遗器套装实现指南

> 如何从 `data/relic_data/` 的 JSON 数据出发，将一个遗器套装完整接入战斗引擎。
> 参考实现：`entities/relics/set_102_musketeer.py`（快枪手套装）。

---

## 一、核心文件一览

| 文件 | 作用 |
|------|------|
| `data/relic_data/{id}.json` | 套装原始数据（套装效果、部件列表、主副词缀选项） |
| `entities/relics/base.py` | `BaseRelic` 部件基类 + `RelicSetEffect` 抽象基类 + `check_and_apply_set_effects` / `start_relic_set_effects` 两个模块函数 |
| `entities/relics/set_{id}_{name}.py` | 一个套装的实现文件 |
| `entities/relics/__init__.py` | 导入新套装以触发自动注册 |
| `entities/base.py` | `StatModifier` 数据类 |
| `core/combat_engine.py:63-65` | 战斗开始时调用 `start_relic_set_effects` |
| `entities/characters/base.py:181-196` | `equip_relic()` 末尾调用 `check_and_apply_set_effects` |

---

## 二、运行机制

### 2.1 生命周期

```
用户调用 equip_relic(部件)
  └→ 移除/添加部件级的 StatModifier（source = "Relic_HEAD" 等）
  └→ check_and_apply_set_effects(character)
       ├→ 清理旧的套装效果：调用旧 effect 的 on_unequip()
       ├→ 统计 character.relics 里每个 set_id 有几件
       └→ 对 ≥2 件的套装，创建 effect 实例并调用 on_equip(character, piece_count)

CombatEngine.run()
  └→ start_relic_set_effects(state, character)
       └→ 遍历角色当前激活的套装 effect，调用 on_combat_start()
```

### 2.2 件数判定规则

| 件数 | 洞隧套（cavern） | 位面套（planar） |
|------|-----------------|-------------------|
| 1 件 | 不激活 | 不激活 |
| 2 件 | 激活 2 件套效果 | 激活（位面套只有 2 件档） |
| 3 件 | 仍只激活 2 件套 | — |
| ≥4 件 | 同时激活 2 件套 + 4 件套 | — |

- 可以混穿：2 件套 A + 2 件套 B → 两个 2 件套效果同时生效
- 卸下 / 替换部件时 → 自动重算，效果实时变更

---

## 三、抽象基类

`RelicSetEffect` 定义在 `entities/relics/base.py`，子类必须覆写 `on_equip`：

```python
class RelicSetEffect(ABC):
    set_id: str = ""          # "102", "301" 等
    set_type: str = "cavern"  # "cavern" 或 "planar"

    _registry: dict[str, type[RelicSetEffect]] = {}

    def __init_subclass__(cls):
        # 子类定义 set_id 后自动注册到 _registry
        super().__init_subclass__()
        if cls.set_id:
            cls._registry[cls.set_id] = cls

    @abstractmethod
    def on_equip(self, character, piece_count):
        """装备/更换时调用。piece_count 表示当前已装备件数。"""
        ...

    def on_combat_start(self, state, character):
        """战斗开始。只有脚本效果需要覆写。"""
        pass

    def on_unequip(self, character):
        """清理。必须清除本套装产生的所有 modifier 和事件订阅。"""
        pass
```

---

## 四、数据文件怎么看

打开 `data/relic_data/102.json`，关注以下字段：

```jsonc
{
  "id": "102",
  "name": "野穗伴行的快枪手",
  "set_type": "cavern",
  "desc": [
    "攻击力提高12%。",                                    // 2 件套描述
    "使装备者的速度提高6%，普攻造成的伤害提高10%。"       // 4 件套描述
  ],
  "set_effects": {
    "2": [{ "type": "AttackAddedRatio", "value": 0.12 }],  // 2 件套的固定属性加成
    "4": [{ "type": "SpeedAddedRatio", "value": 0.06 }]    // 4 件套的固定属性加成
  },
  "pieces": [ ... ],           // 5 星部件列表（HEAD/HANDS/BODY/FEET/NECK/OBJECT）
  "main_affixes": { ... },     // 主词缀选项（供用户选属性用，做效果时不需关注）
  "sub_affixes": [ ... ]       // 副词缀选项（同上）
}
```

### 关键信号

- `set_effects` 的某个档位是 `[]` 空数组 → **纯脚本效果**，必须手动实现逻辑
- `set_effects` 有内容 → 直接翻译成 `StatModifier`
- `desc` 里有"施放终结技后""敌目标被消灭时"等时间状语 → 需要 `on_combat_start` 注册事件

### 属性类型映射

JSON 里的 `type` → `StatType` + `StatModifierType`：

| JSON type | StatType | ModifierType |
|-----------|----------|--------------|
| HPAddedRatio | HP | PERCENT |
| AttackAddedRatio | ATK | PERCENT |
| DefenceAddedRatio | DEF | PERCENT |
| SpeedAddedRatio / SpeedDelta | SPD | PERCENT / FLAT |
| CriticalChanceBase | CRIT_RATE | PERCENT |
| CriticalDamageBase | CRIT_DMG | PERCENT |
| HealRatioBase | OUTGOING_HEALING_BOOST | PERCENT |
| BreakDamageAddedRatioBase | BREAK_EFFECT | PERCENT |
| SPRatioBase | ERR | PERCENT |
| StatusProbabilityBase | EFFECT_HIT_RATE | PERCENT |
| StatusResistanceBase | EFFECT_RES | PERCENT |
| PhysicalAddedRatio | PHYSICAL_DMG_BONUS | PERCENT |
| FireAddedRatio | FIRE_DMG_BONUS | PERCENT |
| IceAddedRatio | ICE_DMG_BONUS | PERCENT |
| ThunderAddedRatio | THUNDER_DMG_BONUS | PERCENT |
| WindAddedRatio | WIND_DMG_BONUS | PERCENT |
| QuantumAddedRatio | QUANTUM_DMG_BONUS | PERCENT |
| ImaginaryAddedRatio | IMAGINARY_DMG_BONUS | PERCENT |

---

## 五、实现步骤

### 步骤 1：读 JSON，判断类型

打开 `data/relic_data/{id}.json`：

1. 看 `set_type` → 决定是 cavern（4 件洞隧）还是 planar（2 件位面）
2. 看 `desc` → 理解效果含义
3. 看 `set_effects`：
   - 非空 → 有固定属性加成，直接翻译
   - 空数组 `[]` → 纯脚本效果，需要读 `desc` 来实现

### 步骤 2：创建套装文件

新建 `entities/relics/set_{id}_{name}.py`。最简形式如下：

```python
from __future__ import annotations

"""<套装中文名> — <洞隧/位面>套装 (<效果简述>)。"""

from core.enums import StatType, StatModifierType
from entities.base import StatModifier
from entities.relics.base import RelicSetEffect


class <ClassName>(RelicSetEffect):
    set_id = "<id>"
    set_type = "<cavern|planar>"

    def on_equip(self, character, piece_count):
        if piece_count >= 2:
            character.stats.add_modifier(StatModifier(
                StatType.ATK, StatModifierType.PERCENT, 0.12,
                source="RelicSet_<id>_2pc", dispellable=False,
            ))
        if piece_count >= 4:
            character.stats.add_modifier(StatModifier(
                StatType.SPD, StatModifierType.PERCENT, 0.06,
                source="RelicSet_<id>_4pc", dispellable=False,
            ))

    def on_unequip(self, character):
        character.stats.purge_source("RelicSet_<id>_2pc")
        character.stats.purge_source("RelicSet_<id>_4pc")
```

**要点**：
- `source` 命名规则：`"RelicSet_{set_id}_2pc"` / `"RelicSet_{set_id}_4pc"`
- 所有装备类 modifier 必须 `dispellable=False`
- `on_unequip` 必须 `purge_source` 清理全部 source
- 位面套只有 2 件档，不需要 4 件档的判断

### 步骤 3：添加脚本效果（如需）

如果 `set_effects` 是空数组 `[]`，说明效果完全靠脚本触发。在类中添加 `on_combat_start` 并覆写 `on_unequip` 以清理回调：

```python
from core.events import EventType

def on_combat_start(self, state, character):
    self._character = character
    self._cb = lambda **kw: self._on_event()
    state.event_bus.subscribe(EventType.XXX, self._cb)

def _on_event(self):
    # 套装的脚本逻辑
    pass

def on_unequip(self, character):
    character.stats.purge_source("RelicSet_<id>_2pc")
    if hasattr(self, "_cb") and self._cb and character.event_bus:
        character.event_bus.unsubscribe(EventType.XXX, self._cb)
```

### 步骤 4：注册

在 `entities/relics/__init__.py` 中加一行 import：

```python
from entities.relics.set_{id}_{name} import <ClassName>
```

无需其他操作——`RelicSetEffect.__init_subclass__` 会通过 `set_id` 自动注册。

引擎侧的 `equip_relic` 和 `CombatEngine.run` 不需要改。

---

## 六、常见效果模式

以下每种模式给出了 JSON 中对应的信号特征和代码模板。

### 模式 A：纯固定属性加成

**信号**：`set_effects` 的某个档位非空。

```python
def on_equip(self, character, piece_count):
    if piece_count >= 2:
        character.stats.add_modifier(StatModifier(
            StatType.ATK, StatModifierType.PERCENT, 0.12,
            source="RelicSet_102_2pc", dispellable=False,
        ))
```

### 模式 B：战斗开始时触发

**信号**：desc 含"战斗开始时""进入战斗后"。

```python
def on_combat_start(self, state, character):
    self._cb = lambda **kw: self._on_battle_start(state)
    state.event_bus.subscribe(EventType.BATTLE_START, self._cb)

def _on_battle_start(self, state):
    state.skill_points = min(state.skill_points + 1, state.max_sp)  # 例：过客 4 件 +1SP
```

### 模式 C：施放终结技后触发

**信号**：desc 含"施放终结技后""施放终结技时"。

```python
def on_combat_start(self, state, character):
    self._character = character
    self._cb = lambda **kw: self._on_ult(kw.get("character"))
    state.event_bus.subscribe(EventType.ON_ULTIMATE_INSERTED, self._cb)

def _on_ult(self, caster):
    if caster is not self._character:
        return
    mod = StatModifier(StatType.CRIT_DMG, StatModifierType.PERCENT, 0.25,
                       source="RelicSet_104_trigger", duration=2, dispellable=False)
    self._character.stats.apply_modifier(mod, "refresh")
```

> `duration=2` 表示持续 2 个正常回合（FUA / 额外回合 / 终结技插队不计入）。

### 模式 D：叠层效果

**信号**：desc 含"叠加""每层""最多 N 层"。

```python
def on_combat_start(self, state, character):
    self._character = character
    self._stack = 0
    self._cb = lambda **kw: self._on_trigger()
    state.event_bus.subscribe(EventType.XXX, self._cb)

def _on_trigger(self):
    self._stack = min(self._stack + 1, MAX_STACKS)
    mod = StatModifier(StatType.ATK, StatModifierType.PERCENT,
                       self._stack * 0.05,
                       source="RelicSet_105_stack", dispellable=False)
    self._character.stats.apply_modifier(mod, "refresh")
```

> 用 `"refresh"` 策略：每次叠层刷新 modifier 的值，不会重复创建。

### 模式 E：生命值条件触发

**信号**：desc 含"HP≤X%""生命值小于等于"。

```python
def on_combat_start(self, state, character):
    self._character = character
    self._cb = lambda **kw: self._on_turn_start(kw.get("unit"))
    state.event_bus.subscribe(EventType.TURN_START, self._cb)

def _on_turn_start(self, unit):
    if unit is not self._character:
        return
    if self._character.hp / self._character.max_hp <= 0.5:
        heal = int(self._character.max_hp * 0.08)
        self._character.hp = min(self._character.hp + heal, self._character.max_hp)
        self._character.gain_energy(5)
```

### 模式 F：弱点击破时触发

**信号**：desc 含"弱点击破""击破敌方目标弱点"。

```python
def on_combat_start(self, state, character):
    self._character = character
    self._cb = lambda **kw: self._on_break(kw.get("source"))
    state.event_bus.subscribe(EventType.ON_WEAKNESS_BREAK, self._cb)

def _on_break(self, source):
    if source is self._character:
        self._character.gain_energy(3)
```

### 模式 G：速度阈值条件

**信号**：desc 含"速度≥X""当速度大于等于"。

```python
def on_equip(self, character, piece_count):
    if piece_count >= 2:
        character.stats.add_modifier(StatModifier(
            StatType.ATK, StatModifierType.PERCENT, 0.12,
            source="RelicSet_301_2pc", dispellable=False,
        ))

def on_combat_start(self, state, character):
    if character.stats.get_total_stat(StatType.SPD) >= 120:
        character.stats.add_modifier(StatModifier(
            StatType.ATK, StatModifierType.PERCENT, 0.12,
            source="RelicSet_301_spd", dispellable=False,
        ))
```

> 速度阈值效果在进入战斗后一次性判断即可，不需要持续监听。

---

## 七、编码规范

### source 命名

| 效果类型 | source 格式 | 示例 |
|---------|------------|------|
| 2 件套固定加成 | `RelicSet_{id}_2pc` | `RelicSet_102_2pc` |
| 4 件套固定加成 | `RelicSet_{id}_4pc` | `RelicSet_102_4pc` |
| 事件触发的临时 buff | `RelicSet_{id}_trigger` | `RelicSet_104_trigger` |
| 叠层效果 | `RelicSet_{id}_stack` | `RelicSet_105_stack` |
| 速度阈值触发 | `RelicSet_{id}_spd` | `RelicSet_301_spd` |

### on_unequip 清理

```python
def on_unequip(self, character):
    # 1. 清除所有可能的 source
    character.stats.purge_source("RelicSet_<id>_2pc")
    character.stats.purge_source("RelicSet_<id>_4pc")
    character.stats.purge_source("RelicSet_<id>_trigger")
    character.stats.purge_source("RelicSet_<id>_stack")
    # 2. 取消所有事件订阅
    if hasattr(self, "_cb") and self._cb and character.event_bus:
        character.event_bus.unsubscribe(EventType.XXX, self._cb)
```

### 事件回调存储

所有 `lambda` 回调必须存为 `self._cb` 实例属性，**不能匿名传入 `subscribe`**——否则 `unsubscribe` 时找不到引用。

```python
# ✅ 正确
self._cb = lambda **kw: self._handler()
state.event_bus.subscribe(EventType.XXX, self._cb)

# ❌ 错误
state.event_bus.subscribe(EventType.XXX, lambda **kw: self._handler())
```

### 事件回调中检查角色归属

如果事件会被多个角色触发（如 `ON_ULTIMATE_INSERTED`），必须在回调中判断 `caster is self._character`：

```python
def _on_ult(self, caster):
    if caster is not self._character:
        return
    # 只有穿戴者自己放终结技才触发
```

---

## 八、测试模板

```python
class Test<SetName>:
    def _make_char(self):
        from core.test_factory import create_test_character
        return create_test_character("Tester", hp=500, speed=100, atk=100.0)

    # 注册验证
    def test_registry(self):
        eff = RelicSetEffect("<id>")
        assert isinstance(eff, <ClassName>)

    # 2 件套生效
    def test_2pc_applies(self):
        char = self._make_char()
        head = Relic(part=RelicPart.HEAD, set_id="<id>",
                     main_stat=StatModifier(StatType.HP, StatModifierType.FLAT, 100))
        hands = Relic(part=RelicPart.HANDS, set_id="<id>",
                      main_stat=StatModifier(StatType.ATK, StatModifierType.FLAT, 10))
        char.equip_relic(head)
        char.equip_relic(hands)
        assert any("RelicSet_<id>_2pc" in m.source for m in char.stats.active_modifiers)

    # 4 件套生效（cavern only）
    def test_4pc_applies(self):
        char = self._make_char()
        for part in (RelicPart.HEAD, RelicPart.HANDS, RelicPart.BODY, RelicPart.FEET):
            r = Relic(part=part, set_id="<id>",
                      main_stat=StatModifier(StatType.HP, StatModifierType.FLAT, 100))
            char.equip_relic(r)
        assert any("RelicSet_<id>_4pc" in m.source for m in char.stats.active_modifiers)

    # 1 件不生效
    def test_one_piece_no_effect(self):
        char = self._make_char()
        head = Relic(part=RelicPart.HEAD, set_id="<id>",
                     main_stat=StatModifier(StatType.HP, StatModifierType.FLAT, 100))
        char.equip_relic(head)
        assert not any("RelicSet_<id>" in m.source for m in char.stats.active_modifiers)

    # 混搭 2+2
    def test_mixed_2_plus_2(self):
        char = self._make_char()
        for part in (RelicPart.HEAD, RelicPart.HANDS):
            r = Relic(part=part, set_id="<id>",
                      main_stat=StatModifier(StatType.HP, StatModifierType.FLAT, 100))
            char.equip_relic(r)
        for part in (RelicPart.BODY, RelicPart.FEET):
            r = Relic(part=part, set_id="<other_id>",
                      main_stat=StatModifier(StatType.HP, StatModifierType.FLAT, 100))
            char.equip_relic(r)
        assert any("RelicSet_<id>_2pc" in m.source for m in char.stats.active_modifiers)
        assert any("RelicSet_<other_id>_2pc" in m.source for m in char.stats.active_modifiers)

    # 卸下部件后套装效果消失
    def test_unequip_cleans_effect(self):
        char = self._make_char()
        for part in (RelicPart.HEAD, RelicPart.HANDS):
            r = Relic(part=part, set_id="<id>",
                      main_stat=StatModifier(StatType.HP, StatModifierType.FLAT, 100))
            char.equip_relic(r)
        # 替换掉一件 → 只剩 1 件
        empty = Relic(part=RelicPart.HEAD, set_id="",
                      main_stat=StatModifier(StatType.HP, StatModifierType.FLAT, 100))
        char.equip_relic(empty)
        assert not any("RelicSet_<id>" in m.source for m in char.stats.active_modifiers)

    # 脚本效果触发（仅需时有）
    def test_scripted_effect(self):
        char = self._make_char()
        # equip relics...
        enemy = Enemy(name="E", hp=50000, speed=50, base_damage=0, level=1)
        state = GameState(characters=[char], enemies=[enemy])
        engine = CombatEngine(state)  # 这会调用 start_relic_set_effects
        engine.event_bus.emit(EventType.XXX, ...)
        # 检查脚本效果是否触发

    # 位面套验证（仅位面套需要）
    def test_planar_2pc(self):
        char = self._make_char()
        sphere = Relic(part=RelicPart.PLANAR_SPHERE, set_id="<id>",
                       main_stat=StatModifier(StatType.HP, StatModifierType.PERCENT, 0.10))
        rope = Relic(part=RelicPart.LINK_ROPE, set_id="<id>",
                     main_stat=StatModifier(StatType.ATK, StatModifierType.PERCENT, 0.10))
        char.equip_relic(sphere)
        char.equip_relic(rope)
        assert any("RelicSet_<id>" in m.source for m in char.stats.active_modifiers)
```

---

## 九、相关文档

- `docs/todo.md` — 开发路线图，含遗器完成状态
- `docs/anti_regression.md` — 防错清单
- `data/relic_data/_index.json` — 56 套遗器索引
- `data/relic_data/{id}.json` — 单套遗器原始数据
- `entities/relics/set_102_musketeer.py` — 参考实现

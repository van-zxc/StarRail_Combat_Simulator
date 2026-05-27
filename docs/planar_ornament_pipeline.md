# 位面饰品实现指南

> 如何将一位面饰品套装完整接入战斗引擎。
> 参考实现：`entities/planar_ornaments/set_301_space_sealing.py`（太空封印站）。
> 位面饰品与隧洞遗器共享基础框架，本文档聚焦位面饰品独有的模式与陷阱。
> 共享部分（`BaseRelic` / `RelicSetEffect` / 注册机制）见 `docs/relic_pipeline.md`。

---

## 一、核心文件一览

| 文件 | 作用 |
|------|------|
| `data/relic_data/{id}.json` | 套装原始数据（`set_type: "planar"`，仅 2 件效果） |
| `entities/relics/base.py` | `BaseRelic` / `RelicSetEffect` 共享基类，位面饰品从中 import |
| `entities/planar_ornaments/set_{id}_{name}.py` | 一个位面饰品的实现文件 |
| `entities/planar_ornaments/__init__.py` | 导入新套装以触发自动注册 |
| `entities/base.py` | `StatModifier` 数据类 |
| `core/combat_engine.py:63-65` | 战斗开始时调用 `start_relic_set_effects` |
| `entities/characters/base.py:181-196` | `equip_relic()` 末尾调用 `check_and_apply_set_effects` |

位面饰品与隧洞遗器使用同一入口 `equip_relic()`。`RelicPart.PLANAR_SPHERE` / `LINK_ROPE` 已在 `core/enums.py` 中定义，无需任何引擎改动。

---

## 二、运行机制

与隧洞遗器完全一致（详见 `docs/relic_pipeline.md` 第二节），仅件数判定不同：

| 件数 | 位面套（planar） |
|------|-----------------|
| 1 件 | 不激活 |
| 2 件 | 激活（位面套只有 2 件档） |

可以混穿：隧洞 4 件 + 位面 2 件 → 两套效果同时生效。

---

## 三、JSON 数据怎么看

打开 `data/relic_data/301.json`，关注以下字段（以 301 太空封印站为例）：

```jsonc
{
  "id": "301",
  "name": "太空封印站",
  "set_type": "planar",          // ← 位面饰品
  "desc": [
    "使装备者的攻击力提高12%。当装备者的速度大于等于120时，攻击力额外提高12%。"
  ],
  "set_effects": {
    "2": [{ "type": "AttackAddedRatio", "value": 0.12 }]  // 仅"2"档，没有"4"
  },
  "pieces": [
    { "id": "63015", "type": "PLANAR_SPHERE", ... },        // 球
    { "id": "63016", "type": "LINK_ROPE", ... }             // 绳
  ],
  "main_affixes": {
    "55": [ ... ],   // PLANAR_SPHERE 主词缀（HP%/ATK%/DEF%/元素增伤）
    "56": [ ... ]    // LINK_ROPE 主词缀（击破%/充能%/HP%/ATK%/DEF%）
  },
  "sub_affixes": [ ... ]  // 标准 5 星副词缀（与隧洞共用）
}
```

### 与隧洞 JSON 的区别

| 字段 | 隧洞 (cavern) | 位面 (planar) |
|------|---------------|---------------|
| `set_type` | `"cavern"` | `"planar"` |
| `set_effects` | 有 `"2"` 和 `"4"` 两档 | 只有 `"2"` 一档 |
| `pieces[].type` | `HEAD` / `HANDS` / `BODY` / `FEET` | `PLANAR_SPHERE` / `LINK_ROPE` |
| `main_affixes` | 4 个组 (51~54) | 2 个组 (55~56) |

### 关键信号

- `set_effects["2"]` 非空 → 有固定属性加成，直接翻译成 `StatModifier`
- `desc` 含"额外""额外提高" → 条件触发型，需要 `_check_condition` 动态 toggle
- `desc` 含"我方全体""队伍中" → 全队 buff 模式，需要保存 `state` 引用
- `desc` 含"当前XX的XX%" → 动态换算模式，用 `refresh` 策略
- `desc` 含"进入战斗时立刻" → BATTLE_START 一次性触发
- `desc` 含"持续到施放首次攻击后" → BATTLE_START 发牌 + 首次攻击收回

---

## 四、实现步骤

### 步骤 1：读 JSON，判断模式

打开 `data/relic_data/{id}.json`：

1. 确认 `set_type: "planar"`
2. 读 `desc` → 对照第五节判断属于哪种实现模式
3. 读 `set_effects["2"]` → 非空则直接翻译成 `on_equip` 里的 `StatModifier`

### 步骤 2：创建套装文件

新建 `entities/planar_ornaments/set_{id}_{name}.py`。包含两个部位类 + 一个套装效果类：

```python
from __future__ import annotations

"""<套装中文名> — 2件套 (<效果简述>)。"""

from typing import Optional

from core.enums import StatType, StatModifierType
from entities.base import StatModifier
from entities.relics.base import BaseRelic, RelicSetEffect
from starrail_combat import RelicPart


class XxxSphere(BaseRelic):
    _default_part = RelicPart.PLANAR_SPHERE
    _default_set_id = "{id}"


class XxxRope(BaseRelic):
    _default_part = RelicPart.LINK_ROPE
    _default_set_id = "{id}"


class XxxSet(RelicSetEffect):
    set_id = "{id}"
    set_type = "planar"

    def on_equip(self, character, piece_count):
        if piece_count >= 2:
            character.stats.add_modifier(StatModifier(
                StatType.XXX, StatModifierType.PERCENT, 0.XX,
                source="RelicSet_{id}_2pc", dispellable=False,
            ))

    def on_unequip(self, character):
        character.stats.purge_source("RelicSet_{id}_2pc")
```

### 步骤 3：添加条件效果

根据 desc 判断是否需要 `on_combat_start` 订阅事件。参考第五节选择对应的代码模板。

### 步骤 4：注册

在 `entities/planar_ornaments/__init__.py` 中加一行 import：

```python
from entities.planar_ornaments.set_{id}_{name} import XxxSet, XxxSphere, XxxRope
```

`RelicSetEffect.__init_subclass__` 会通过 `set_id` 自动注册。

---

## 五、位面饰品专属实现模式

以下 5 种模式是位面饰品独有的，隧洞遗器只需模式 A~G（见 `docs/relic_pipeline.md` 第六节）。

### 模式 H：自我条件阈值（AFTER_ACTION）

**信号**：desc 含"当XX大于等于Y%时""额外提高"。

**说明**：永久给一个属性，条件满足时再给一个额外属性。条件可能因战斗中 buff/debuff 改变（如 SPD 被队友加速），**必须用 `AFTER_ACTION` 实时刷新**。

**为什么不用 TURN_START**：`combat_engine.py:114-115` 中 `TURN_START` emit 在 `_decrement_modifiers_timing` 之前。如果 SPD buff 在回合开始时过期，TURN_START handler 读到的是过期前的旧 SPD 值，导致条件 buff 多残留一整回合。

```python
from core.events import EventType

class XxxSet(RelicSetEffect):
    _SOURCE_2PC = "RelicSet_{id}_2pc"
    _SOURCE_EXTRA = "RelicSet_{id}_2pc_extra"

    def __init__(self) -> None:
        self._character = None
        self._cb_after_action = None

    def on_equip(self, character, piece_count):
        if piece_count >= 2:
            character.stats.add_modifier(StatModifier(
                StatType.XXX, StatModifierType.PERCENT, 0.XX,
                source=self._SOURCE_2PC, dispellable=False,
            ))

    def on_combat_start(self, state, character):
        self._character = character
        self._check_condition()                         # 初始状态检查
        self._cb_after_action = lambda **kw: self._check_condition()
        state.event_bus.subscribe(EventType.AFTER_ACTION, self._cb_after_action)

    def _check_condition(self) -> None:
        val = self._character.stats.get_total_stat(StatType.XXX)
        has_extra = any(
            m.source == self._SOURCE_EXTRA
            for m in self._character.stats.active_modifiers
        )
        if val >= THRESHOLD and not has_extra:
            self._character.stats.add_modifier(StatModifier(
                StatType.YYY, StatModifierType.PERCENT, 0.XX,
                source=self._SOURCE_EXTRA, dispellable=False,
            ))
        elif val < THRESHOLD and has_extra:
            self._character.stats.purge_source(self._SOURCE_EXTRA)

    def on_unequip(self, character):
        character.stats.purge_source(self._SOURCE_2PC)
        character.stats.purge_source(self._SOURCE_EXTRA)
        if self._cb_after_action and character.event_bus:
            character.event_bus.unsubscribe(EventType.AFTER_ACTION, self._cb_after_action)
```

**应用**：301（SPD≥120 → 额外 ATK）、304（EHR≥50% → 额外 DEF）、306（CRIT_RATE≥50% → ULT_DMG + FUA_DMG）

---

### 模式 I：全队 buff + 独立 source

**信号**：desc 含"我方全体""队伍中"。

**说明**：装备者达到条件后给**全队成员**（含自己）加属性。多名角色同时装备此套装时效果**叠加**。

**独立 source 技巧**：每人用自己的 `id(character)` 生成唯一的 team source，施加用 `no_stack`（同装备者对同角色不重复），不同装备者自然叠加。

```python
class XxxSet(RelicSetEffect):
    def on_combat_start(self, state, character):
        self._character = character
        self._state = state
        self._team_source = f"RelicSet_{self.set_id}_2pc_team_{id(character)}"
        self._check_condition()
        self._cb_after_action = lambda **kw: self._check_condition()
        state.event_bus.subscribe(EventType.AFTER_ACTION, self._cb_after_action)

    def _check_condition(self) -> None:
        if not self._character.is_alive:
            self._purge_team_buff()
            return
        spd = self._character.speed
        if spd >= 120.0:
            for char in self._state.alive_characters:
                mod = StatModifier(StatType.ATK, StatModifierType.PERCENT, 0.XX,
                                   source=self._team_source, dispellable=False)
                char.stats.apply_modifier(mod, "no_stack")
        else:
            self._purge_team_buff()

    def _purge_team_buff(self) -> None:
        for char in self._state.characters:
            char.stats.purge_source(self._team_source)

    def on_unequip(self, character):
        character.stats.purge_source(...)                  # 个人永久属性
        if self._state:
            for char in self._state.characters:
                char.stats.purge_source(self._team_source)  # 只清自己的团队 buff
        if self._cb_after_action and character.event_bus:
            character.event_bus.unsubscribe(EventType.AFTER_ACTION, self._cb_after_action)
```

**关键**：清理时只 purge 自己的 `_team_source`，不碰别人的。死亡后 `_check_condition` 检查 `is_alive`，不存活则全队清理；复活后自动重建。

**应用**：302（SPD≥120 → 全队 ATK+8%）

---

### 模式 J：动态属性换算（refresh）

**信号**：desc 含"等同于当前XX的YY%""最多提高。"

**说明**：一个属性值按比例转换成另一个属性值，比例固定但数值随源属性变化。使用 `apply_modifier` 的 `"refresh"` 策略：同 source 的 modifier 值被替换，不会重复创建。

```python
class XxxSet(RelicSetEffect):
    _SOURCE_CONV = "RelicSet_{id}_2pc_conversion"

    def _check_condition(self) -> None:
        src_val = self._character.stats.get_total_stat(StatType.XXX)
        target_val = min(src_val * RATIO, CAP)
        mod = StatModifier(StatType.ATK, StatModifierType.PERCENT, target_val,
                           source=self._SOURCE_CONV, dispellable=False)
        self._character.stats.apply_modifier(mod, "refresh")

    def on_unequip(self, character):
        character.stats.purge_source(self._SOURCE_2PC)
        character.stats.purge_source(self._SOURCE_CONV)
        ...
```

**应用**：303（EHR×0.25 → ATK%，上限 25%）

---

### 模式 K：BATTLE_START 一次性触发

**信号**：desc 含"进入战斗时立刻"。

**说明**：在 BATTLE_START 时判定一次，满足条件则触发效果（如拉条），之后不再判定。用 `_fired` flag 防止多波次重复触发。

```python
class XxxSet(RelicSetEffect):
    def __init__(self) -> None:
        self._character = None
        self._cb_battle = None
        self._fired = False

    def on_combat_start(self, state, character):
        self._character = character
        self._cb_battle = lambda **kw: self._on_battle_start(**kw)
        state.event_bus.subscribe(EventType.BATTLE_START, self._cb_battle)

    def _on_battle_start(self, **kwargs):
        if self._fired:
            return
        self._fired = True
        if self._character.speed >= 120.0:
            self._character.advance_action(0.40)

    def on_unequip(self, character):
        character.stats.purge_source(self._SOURCE_2PC)
        if self._cb_battle and character.event_bus:
            character.event_bus.unsubscribe(EventType.BATTLE_START, self._cb_battle)
```

**应用**：308（SPD≥120 → 行动提前 40%）

---

### 模式 L：BATTLE_START 发牌 + 首次攻击收回

**信号**：desc 含"持续到施放首次攻击后结束"。

**说明**：BATTLE_START 一次性判定条件，满足则发放临时 buff，buff 在角色**首次攻击**后移除。若角色在 buff 持续期间死亡，需在 `UNIT_DOWNED` 中清理 buff。

**攻击类型判定**：仅 `BASIC_ATTACK / ENHANCED_BASIC / SKILL / ULTIMATE / FOLLOW_UP / COUNTER` 算"攻击"。`TALENT / EXTRA_TURN / SUMMON` 不算——被冻结跳过回合不消耗 buff。

```python
_ATTACK_TYPES = {
    ActionType.BASIC_ATTACK,
    ActionType.ENHANCED_BASIC,
    ActionType.SKILL,
    ActionType.ULTIMATE,
    ActionType.FOLLOW_UP,
    ActionType.COUNTER,
}


class XxxSet(RelicSetEffect):
    _SOURCE_BATTLE = "RelicSet_{id}_2pc_battle"

    def __init__(self) -> None:
        self._character = None
        self._cb_battle = None
        self._cb_after = None
        self._cb_death = None

    def on_combat_start(self, state, character):
        self._character = character
        self._cb_battle = lambda **kw: self._on_battle_start(**kw)
        state.event_bus.subscribe(EventType.BATTLE_START, self._cb_battle)

    def _on_battle_start(self, **kwargs):
        from core.events import EventType

        if self._character.stats.get_total_stat(StatType.CRIT_DMG) < 1.20:
            return                            # 条件不达标，永不触发
        self._character.stats.add_modifier(StatModifier(
            StatType.CRIT_RATE, StatModifierType.PERCENT, 0.60,
            source=self._SOURCE_BATTLE, dispellable=False,
        ))
        self._cb_after = lambda **kw: self._on_after_action(**kw)
        self._cb_death = lambda **kw: self._on_unit_downed(**kw)
        bus = self._character.event_bus
        if bus is not None:
            bus.subscribe(EventType.AFTER_ACTION, self._cb_after)
            bus.subscribe(EventType.UNIT_DOWNED, self._cb_death)

    def _on_after_action(self, **kwargs):
        if kwargs.get("unit") is not self._character:
            return
        if kwargs.get("action_type") not in _ATTACK_TYPES:
            return                            # 非攻击不消耗
        self._cleanup_battle_buff()

    def _on_unit_downed(self, **kwargs):
        if kwargs.get("target") is not self._character:
            return
        self._cleanup_battle_buff()

    def _cleanup_battle_buff(self):
        from core.events import EventType

        self._character.stats.purge_source(self._SOURCE_BATTLE)
        bus = self._character.event_bus
        if bus is not None:
            if self._cb_after is not None:
                bus.unsubscribe(EventType.AFTER_ACTION, self._cb_after)
                self._cb_after = None
            if self._cb_death is not None:
                bus.unsubscribe(EventType.UNIT_DOWNED, self._cb_death)
                self._cb_death = None

    def on_unequip(self, character):
        character.stats.purge_source(self._SOURCE_2PC)
        character.stats.purge_source(self._SOURCE_BATTLE)
        bus = character.event_bus
        if bus is not None:
            if self._cb_battle is not None:
                bus.unsubscribe(EventType.BATTLE_START, self._cb_battle)
            if self._cb_after is not None:
                bus.unsubscribe(EventType.AFTER_ACTION, self._cb_after)
            if self._cb_death is not None:
                bus.unsubscribe(EventType.UNIT_DOWNED, self._cb_death)
```

**注意**：BATTLE_START 是**一次性判定**。如果 BATTLE_START 时条件不达标，后续即使 CRIT_DMG 被 buff 抬上去也不触发。

**应用**：305（CRIT_DMG≥120% → CRIT_RATE+60%，首次攻击后移除）

---

## 六、编码规范

### source 命名

| 效果类型 | source 格式 | 示例 |
|---------|------------|------|
| 2 件套固定加成 | `RelicSet_{id}_2pc` | `RelicSet_301_2pc` |
| 条件阈值触发 | `RelicSet_{id}_2pc_extra` | `RelicSet_301_2pc_extra` |
| 全队 buff（必须含 id(character)） | `RelicSet_{id}_2pc_team_{id(character)}` | `RelicSet_302_2pc_team_1402345` |
| 动态换算 | `RelicSet_{id}_2pc_conversion` | `RelicSet_303_2pc_conversion` |
| BATTLE_START 临时 buff | `RelicSet_{id}_2pc_battle` | `RelicSet_305_2pc_battle` |

其余规范（回调存储、角色归属检查、`on_unequip` 清理）— 与隧洞遗器相同，见 `docs/relic_pipeline.md` 第七节。

---

## 七、测试模板

```python
class Test<SetName>:
    def _make_char(self):
        from core.test_factory import create_test_character
        return create_test_character("Tester", hp=500, speed=100, atk=100.0)

    def _make_state(self, char):
        from starrail_combat import GameState, CombatEngine
        from entities.enemies.base import BaseEnemy
        enemy = Enemy(name="E", hp=50000, speed=50, base_damage=0, level=1)
        state = GameState(characters=[char], enemies=[enemy])
        engine = CombatEngine(state)
        return state, engine

    def _equip_2pc(self, char):
        char.equip_relic(Relic(part=RelicPart.PLANAR_SPHERE, set_id="<id>",
                                main_stat=StatModifier(StatType.HP, ...)))
        char.equip_relic(Relic(part=RelicPart.LINK_ROPE, set_id="<id>",
                                main_stat=StatModifier(StatType.ATK, ...)))

    # 注册验证
    def test_registry(self):
        assert "<id>" in RelicSetEffect._registry

    # 2 件套生效
    def test_2pc_applies(self):
        char = self._make_char()
        self._equip_2pc(char)
        assert any("RelicSet_<id>_2pc" in m.source
                   for m in char.stats.active_modifiers)

    # 1 件不生效
    def test_one_piece_no_effect(self):
        char = self._make_char()
        char.equip_relic(Relic(part=RelicPart.PLANAR_SPHERE, set_id="<id>", ...))
        assert not any("RelicSet_<id>" in m.source
                       for m in char.stats.active_modifiers)

    # 隧洞 + 位面混装
    def test_cavern_planar_coexist(self):
        char = self._make_char()
        for part in (RelicPart.HEAD, RelicPart.HANDS, RelicPart.BODY, RelicPart.FEET):
            char.equip_relic(Relic(part=part, set_id="109", ...))
        self._equip_2pc(char)
        assert any(m.source.startswith("RelicSet_109_") for m in char.stats.active_modifiers)
        assert any(m.source.startswith("RelicSet_<id>_") for m in char.stats.active_modifiers)

    # 卸下部件后套装效果消失
    def test_unequip_cleans(self):
        char = self._make_char()
        self._equip_2pc(char)
        char.equip_relic(Relic(part=RelicPart.PLANAR_SPHERE, set_id="OtherSet", ...))
        char.equip_relic(Relic(part=RelicPart.LINK_ROPE, set_id="OtherSet", ...))
        assert not any(m.source.startswith("RelicSet_<id>_") for m in char.stats.active_modifiers)

    # 条件阈值动态 toggle（模式 H）
    def test_threshold_dynamic_toggle(self):
        char = self._make_char()
        self._equip_2pc(char)
        state, engine = self._make_state(char)
        from entities.relics.base import start_relic_set_effects
        start_relic_set_effects(state, char)
        # 提升 stat 到条件以上
        char.stats.add_modifier(StatModifier(StatType.XXX, ..., source="Boost"))
        engine.event_bus.emit(EventType.AFTER_ACTION, unit=char, target=state.enemies[0])
        assert any("RelicSet_<id>_extra" in m.source for m in char.stats.active_modifiers)
        # 移除 boost，stat 恢复
        char.stats.remove_modifier_by_source("Boost")
        engine.event_bus.emit(EventType.AFTER_ACTION, unit=char, target=state.enemies[0])
        assert not any("RelicSet_<id>_extra" in m.source for m in char.stats.active_modifiers)

    # 全队 buff 叠加（模式 I）
    def test_two_wearers_stack(self):
        a = self._make_char()
        b = self._make_char()
        self._equip_2pc(a)
        self._equip_2pc(b)
        state, engine = self._make_state(a, b)
        start_relic_set_effects(state, a)
        start_relic_set_effects(state, b)
        assert a.stats.get_total_stat(StatType.ATK) == pytest.approx(100.0 * 1.16)

    # 动态换算（模式 J）
    def test_conversion_dynamic(self):
        char = self._make_char()
        self._equip_2pc(char)
        state, engine = self._make_state(char)
        start_relic_set_effects(state, char)
        char.stats.add_modifier(StatModifier(StatType.EFFECT_HIT_RATE, ...))
        engine.event_bus.emit(EventType.AFTER_ACTION, ...)
        # 验证 ATK 相应变化

    # BATTLE_START 一次性（模式 K）
    def test_battle_start_one_shot(self):
        char = self._make_char(speed=120)
        self._equip_2pc(char)
        state, engine = self._make_state(char)
        start_relic_set_effects(state, char)
        av_before = char.current_av
        engine.event_bus.emit(EventType.BATTLE_START, engine=engine)
        assert char.current_av < av_before
        av_after_first = char.current_av
        char.reset_av()
        engine.event_bus.emit(EventType.BATTLE_START, engine=engine)
        assert char.current_av == pytest.approx(char.base_av)

    # BATTLE_START 发牌 + 攻击收回（模式 L）
    def test_battle_buff_removed_on_attack(self):
        char = self._make_char()
        self._ensure_high_cd(char)
        self._equip_2pc(char)
        state, engine = self._make_state(char)
        start_relic_set_effects(state, char)
        engine.event_bus.emit(EventType.BATTLE_START, engine=engine)
        assert any(m.source == "RelicSet_<id>_battle" for m in char.stats.active_modifiers)
        engine.event_bus.emit(EventType.AFTER_ACTION, unit=char,
                              target=state.enemies[0], action_type=ActionType.BASIC_ATTACK)
        assert not any(m.source == "RelicSet_<id>_battle" for m in char.stats.active_modifiers)
```

---

## 八、已知陷阱

### 1. TURN_START 时序陷阱

`combat_engine.py:114-115` 中 `TURN_START` emit 在 `_decrement_modifiers_timing` 之前。

**错误做法**：在 TURN_START handler 中读取 stat 做条件判断。
**后果**：若 buff 在回合开始时过期，handler 读到的是过期前的旧 stat 值。
**正确做法**：条件阈值类（模式 H / I / J）全部用 `AFTER_ACTION` + `on_combat_start` 初始检查。`AFTER_ACTION` 总是在 modifier 更新后发出。

### 2. BATTLE_START 一次性判定

模式 L（305）的 BATTLE_START 判定是**一次性的**。BATTLE_START 时不达标则永远不触发，即使后续 CRIT_DMG 被 buff 抬上阈值。desc 中"进入战斗后"暗示入场时判定。

### 3. 攻击类型显式枚举

"施放首次攻击后结束"中的"攻击"需要显式限定。`TALENT` 是天赋被动触发，`EXTRA_TURN` 是额外回合类型，二者都不消耗 buff。

### 4. 全队 buff 的独立 source

模式 I 的 team source 必须包含 `id(character)` 确保唯一性。两个角色穿同一套装时，清理自己的团队 buff 不能误删别人的。

### 5. EventBus.unsubscribe 安全

`unsubscribe` 用 list comprehension 创建新列表，不修改 `emit` 正在迭代的旧列表。可在事件回调中安全取消对该事件的订阅（如模式 L 在攻击后取消 AFTER_ACTION）。

---

## 九、相关文档

- `docs/todo.md` — 开发路线图，含位面饰品完成状态
- `docs/relic_pipeline.md` — 隧洞遗器实现指南（共享基类 / 生命周期 / 注册机制）
- `docs/known_issues.md` — 已知设计约束
- `docs/anti_regression.md` — 防错清单
- `data/relic_data/_index.json` — 56 套遗器索引（30 隧洞 + 26 位面）
- `entities/planar_ornaments/set_301_space_sealing.py` — 参考实现

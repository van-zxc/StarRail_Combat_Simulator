# Known Issues & Untested Behaviors

Bugs and behaviors that need empirical verification. Each entry links to the relevant source code.

---

## Light Cone: 银河铁道之夜 (23000)

### KI-001: 敌人计数 — 分裂造物是否计入？

**代码**: `entities/light_cones/night_milky_way.py` → `NightMilkyWayEffect._recalc_stacks()`

**描述**: 光锥特效 "场上每有1个敌方目标，ATK提高#2%" 使用 `len(state.alive_enemies)` 计数。
某些 Boss 会分裂出小型造物（如末日兽的爪子）。这些造物算不算 "敌方目标" 有待实机测试确认。

**当前行为**: 计入所有 `alive_enemies` 中的实体。

**待验证**: 如果分裂造物不应计入，需要在 `_recalc_stacks()` 中添加过滤逻辑（如检查 entity 的 `is_boss`、`is_spawn` 等标记）。

---

## Light Cone: 一场术后对话 (21000)

### KI-002: 治疗 buff 持续时间 — 终结技后残留

**代码**: `entities/light_cones/post_op.py` → `PostOpEffect._on_ult()`

**描述**: "施放终结技时治疗量提高" 通过 `ON_ULTIMATE_INSERTED` 事件施加 `OUTGOING_HEALING_BOOST` (duration=1, tick=owner_turn_end)。
此 buff 会在终结技执行期间生效（覆盖治疗计算），但在终结技之后的正常回合结束前仍会残留。

**当前行为**: buff 持续到 owner 的下一个正常回合结束才移除。意味着如果在终结技后立即触发 FUA / 附加治疗，buff 仍然有效。

**待验证**: 实机测试是否允许 FUA 或额外治疗也吃到这个加成。如果实机不允许，需要改为在 `AFTER_ACTION` 中主动移除。

---

## Combat Engine

### KI-003: `_decrement_modifiers` 的 `owner_turn_end` 作用域

**代码**: `core/combat_engine.py:126-127` → `_decrement_modifiers(unit=actor)`

**描述**: Phase 2 修复前，`_decrement_modifiers()` 无 `unit` 参数，导致任意单位行动时全体 buff 均 tick。
修复后改为 `unit=actor`，仅当前行动者的 `owner_turn_end` 修饰器递减。

**待验证**: 多角色环境下，该修复是否完全对齐实机行为。当前设计：仅主人回合结束时 buff tick；其他角色的行动不影响。

---

## Data

### KI-004: 光锥 JSON 中的 `promotions.levels` 的 `step` 值含义

**代码**: `entities/light_cones/base.py` → `_calc_stat()`

**描述**: JSON 中每个 promotion bracket 有 `base` 和 `step` 两个值。当前使用分段线性插值：
bracket_i 从 `base[i]` 开始，到 `base[i+1]`（或 Lv80 的 `base[6]+step[6]*10`）。
此公式在整数 breakpoint（1,20,30,40,50,60,70,80）处精确匹配 JSON 数据，
但 `step` 的数据值仅对最后一阶 (70→80) 有效，未用于中间 bracket 的插值。

**待验证**: 实机光锥面板在中间等级的数值是否与当前线性插值一致。

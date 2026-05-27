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

---

## Light Cone: ACTION_START / AFTER_ACTION 条件增伤模式

### KI-005: 条件增伤不实时反映

**影响范围**: 以下 light cone 使用 **ACTION_START 检查条件→贴 buff → AFTER_ACTION 清除 buff** 的成对模式：

| 光锥 | 文件 | ID |
|------|------|----|
| 秘密誓心 (A Secret Vow) | `a_secret_vow.py` | 21012 |
| 延长记号 (Fermata) | `fermata.py` | 21022 |
| 汪！散步时间！ (Woof! Walk Time!) | `woof_walk_time.py` | 21026 |
| 乐圮 (Collapsing Sky) | `collapsing_sky.py` | 20009 |
| 晚安与睡颜 (Good Night Sleep Well) | `good_night_sleep_well.py` | 21001 |
| 点个关注吧！ (Subscribe for More!) | `subscribe_for_more.py` | 21017 |
| 星海巡航 (Cruising) — 条件暴击部分 | `cruising.py` | 24001 |
| 渊环 (Loop) | `loop.py` | 20011 |

**已知局限**:
1. **状态变化不实时反映**：条件检查在 `ACTION_START` 时做一次，多段攻击中目标 HP/叠层数变化后 buff 不会更新，直到 `AFTER_ACTION` 清除/下个 `ACTION_START`。
2. **DoT 不经过 `ACTION_START`**：DoT 跳伤害不经由此模式，条件增伤对持续伤害不生效——但部分光锥（如 Fermata）描述注明"对持续伤害也会生效"，此模式无法覆盖。
3. **多段 HitPacket 中的目标变化**：第一段命中 target A 后 target A 死亡，后续段切换 target B，但条件检查已过期（未重新检查 B）。
4. **追加攻击/反击等非主行动**：`ACTION_START` 的 `unit`/`target`/`action_type` 语义可能与技能不符。

**待验证**:
- 原游戏中条件增伤是否在每段命中的 damage calculation 前独立重新判定
- 是否可以通过 `ON_DAMAGE_CALCULATED` 或 `ON_BEFORE_HIT` 事件代替 `ACTION_START`/`AFTER_ACTION` 模式

---

## `count_debuffs()` 语义覆盖广度

### KI-006: 负面效果计数

**现有实现**: `entities/base.py:221-236` — 统计目标身上的负面效果数量：
- `active_modifiers` 中 `value < 0` 的 modifier
- `cc_statuses` 条目数
- `dot_statuses` 条目数

**未验证项**:
| 问题 | 风险 |
|------|------|
| 同名 DoT 叠层是否重复计入（如同元素 Shock 叠加两层 → 计为 1 还是 2） | 可能高估 debuff 计数 |
| 易伤（VULNERABILITY > 0）是否为负面？当前 value>0 不计入 | 可能低估，原游戏是否计入待验证 |
| 护盾削弱、抗性降低等非属性 modifier 是否应计入 | 当前不计入（modifier 无 value 字段或 value≥0） |
| CC 状态是否全部算作 debuff（冻结/禁锢/纠缠） | 全部计入，但原游戏中可能有所区分 |

---

## 伤害乘区加算关系

### KI-007: DMG_BONUS 与条件增伤的加算验证

**已验证**: `multipliers.py:74-77`：`DMG_BONUS` 与 `SKILL_DMG`/`ULT_DMG`/`BASIC_ATK_DMG` 为**加算**关系：
- 战技：总增伤 = 通用 `DMG_BONUS` + `SKILL_DMG`
- 终结技：总增伤 = 通用 `DMG_BONUS` + `ULT_DMG`
- 普攻：总增伤 = 通用 `DMG_BONUS` + `BASIC_ATK_DMG`
- 追加攻击：总增伤 = 通用 `DMG_BONUS` + `FUA_DMG`

**未验证**:
- `DOT_DMG` 与上述的关系（当前实现在 `apply_dmg_bonus` 中对 DoT 额外加算 `DOT_DMG`）
- 元素专属 DMG_BONUS（如 `FIRE_DMG_BONUS`）与通用的叠加关系（当前实现在 `get_element_dmg_bonus` 中返回 `DMG_BONUS + 元素专属`，即加算）

---

## This Is Me! (这就是我啦！) — 多目标终结技验证

### KI-008: `_extra_base_dmg` 多目标覆盖

**结论**: 经代码审查确认**每个敌方目标都能正确获得 DEF 附加伤害**，无需修改。

原因：
- `_extra_base_dmg` 在 `ON_ULTIMATE_INSERTED` 时设置
- `compute_base_damage()` 对每个 target 独立读取该值（只读不写）
- `AFTER_ACTION` 在所有 target 处理完毕后触发清除
- 引擎中没有中间清除逻辑

**现有测试覆盖**: 仅 6 个单元测试（手动 emit event），缺完整 combat run 的集成测试。

---

## 宇宙市场趋势 (Trend of Universal Market) — DEF→ATK 转换

### KI-009: ATK 归零除零风险

**已知风险**: `burn_mult = def_total * def_coeff / self._character.atk`
- 当装备者 ATK 因减益降为 0 时触发 `ZeroDivisionError`
- 浮点精度损失（极小，可忽略）
- 当前不做修改

---

## 跨战斗事件订阅泄漏

### KI-010: BATTLE_END 后订阅残留

**约定**: `docs/anti_regression.md` 规则 #2：`BATTLE_END` 后必须 `event_bus.clear_all()`。

所有 light cone effect 在 `on_unequip` 中 unsubscribe 了自身订阅的事件。但若装备从未被卸载（如整场战斗未更换装备），且引擎未在战斗结束后执行 `clear_all()`，则订阅会泄漏到下一场战斗。

建议在 `GameState` 的 `BATTLE_END` 处理中统一调用 `event_bus.clear_all()`。

---

## Light Cone: 论剑 (Swordplay) (21010)

### KI-011: 目标追踪使用 name 字符串而非实例 identity

**代码**: `entities/light_cones/swordplay.py:80` → `SwordplayEffect._on_hit()`

**描述**: 判断"是否同一目标"时使用 `target.name`（字符串比较）。同种怪物共享相同 name，切换至同类型另一只怪物时不会触发"目标变化→清除层数"的逻辑。

**当前行为**: `_current_target_name = target.name`，若 A 怪物与 B 怪物 name 相同则视为同一目标。

**待验证**: 实机中论剑按怪物实例 identity 判定。等怪物系统支持 UUID/实例标识后修复。

---


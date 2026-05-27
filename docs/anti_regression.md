# 防错清单 (Anti-Regression Checklist)

历史案例 + 禁止操作，防止已修复的 bug 重现。

---

## 1. 禁止重复定义 Enum 类

**规则**: 同一个 `class Xxx(Enum):` 在一个 `.py` 文件中只能出现一次。

**案例**: `core/enums.py` 中 `class ElementType(Enum):` 在第 108 行和第 133 行各定义了一次。
夹在中间的 `_ELEMENT_DMG_STAT` 字典以**第一个** `ElementType` 为键构造，但运行时所有代码使用的都是**第二个** `ElementType`。
结果：`_ELEMENT_DMG_STAT.get(element)` 永远返回 `None`，所有角色的元素专属增伤（火伤/冰伤/雷伤等）静默失效。

**修复**: 2026-05-22，删除第一个重复类定义，将 `_ELEMENT_DMG_STAT` 移至唯一类定义之后。

**检测方法**: 如果新增元素增伤（如 `EleEntityStats.get_element_dmg_bonus()`）测试始终返回 0，检查 Enum 是否被重复定义。

---

## 2. BATTLE_END 后必须调用 `event_bus.clear_all()`

**规则**: 战斗结束时清除所有事件监听器。

**案例**: 角色天赋（Talent）在 `on_combat_start` 中注册监听，但没有任何地方调用取消订阅。
如果同一个角色实例被复用于第二次战斗，旧监听器不会清除，导致每个事件触发多次回调。

**修复**: 2026-05-22，新增 `EventBus.clear_all()` 方法，在 `CombatEngine.run()` 的 `BATTLE_END` emit 后调用。

---

## 3. 事件 kwargs key 必须与 emit 端一致

**规则**: emit 时传 `source=xxx`，handler 中就必须读 `kwargs.get("source")`。反之亦然。

**案例**: `GameState.execute_action()` emit `ON_WEAKNESS_BREAK` 时传 `source=character`，但 Himeko 的 `_on_weakness_break` 读的是 `kwargs.get("breaker")`。由于 `breaker` key 不存在，Himeko E4 附加充能条件永远不满足。

**修复**: 2026-05-22，将 Himeko handler 中的 `breaker` 改为 `source`。

---

## 4. 禁止在技能 execute() 中设置可变属性来传递上下文

**规则**: 不要用 `self.owner._killing_action = "ultimate"` 这种模式在技能和事件处理器之间传递信息。应通过事件的 `**kwargs` 传递明确的 `action_type` 参数。

**案例**: 5 个角色（DanHeng/PlayerGirl/Himeko/Kafka/Welt）在每个技能的 `execute()` 中设置 `self.owner._killing_action = "basic"/"skill"/"ultimate"/"talent_fua"`，然后在 `_on_kill` 或 `_on_weakness_break` 处理器中检查该值。
- 新增技能如果忘记设置 `_killing_action`，事件处理器中的条件判断会静默走错分支。
- 该属性在角色 `__init__` 中声明为 `self._killing_action: str = ""`，是散布在 5 个文件中的重复代码。

**修复**: 2026-05-22，
1. 在 `execute_action()` 的 `ON_KILL` emit 传入 `action_type=action_type`，在 `ON_WEAKNESS_BREAK` emit 同样传入。
2. 事件处理器改为 `kwargs.get("action_type") == ActionType.XXX`。
3. 删除所有 `_killing_action` 赋值（11 处）和声明（5 处）。

---

## 5. 重复代码块必须提取（≥3 处）

**规则**: 发现同一逻辑在 3 个或以上位置完全重复时，立即提取为辅助函数或模块常量。

**案例 1 — SPD 重算**:
`core/entity_stats.py` 中 `apply_modifier` / `remove_modifier` / `remove_modifier_by_source` / `purge_source` / `remove_modifier_by_tag` 共 5 个方法中都有相同的 SPD 检查+重算逻辑。

**修复**: 2026-05-22，提取为 `_recalc_spd_if_changed(old_spd)` 私有方法。

**案例 2 — action_name 解析**:
`core/combat_engine.py` 的 `_execute_character_turn()` 中，同样的 `"战技" if action_type == SKILL else "终结技" if action_type == ULTIMATE else "普攻"` 三目表达式出现了 3 次。

**修复**: 2026-05-22，提取为模块级 `_ACTION_NAMES: dict[ActionType, str]` 字典。

**案例 3 — Bremake / SuperBreak 乘区链完全一致**:
`core/damage/__init__.py` 中 `DamageType.BREAK` 和 `DamageType.SUPER_BREAK` 的乘区链列表完全相同（9 行 × 2）。

**状态**: 当前未修改（两个 DamageType 可能在未来分化，但当前重复值得注意）。

---

## 6. `from __future__ import annotations` 规则

**规则**: 每个 `.py` 文件的第一行非空行（docstring 可放在其后）必须是 `from __future__ import annotations`。创建新文件时必须写入，不要事后批量补。

**案例**: 项目早期大量文件缺失该导入，导致类型注解使用类名字符串时报 `NameError`。

**修复**: 2026-05-22，通过 Python 脚本补全至全部 84 个源文件。

---

## 7. 禁止用 PowerShell `Set-Content` 修改 Python 文件

**规则**: `Set-Content` 默认使用 UTF-16 LE 编码, 会破坏 Python 源文件中非 ASCII 字符（中文注释、docstring）。

**案例**: 2026-05-22，批量添加 `from __future__` 时使用了 `Set-Content`，导致 56 个文件的中文注释被破坏为乱码 `\ufffd`，所有文件不得不用 `git checkout` 恢复。

**正确做法**: 使用 Python 脚本（`open(path, 'w', encoding='utf-8')`）或编辑工具直接修改文件。

---

## 其他潜在风险点

### 懒导入
28 处 `from core.events import EventType` 写在方法体内部（每个角色的 `on_combat_start` 都有一行）。虽然不导致 bug，但违反了 PEP 8 风格。

### 多段攻击模式不统一
Arlan/Herta 用 `HitPacket` + `execute_multi_hit()`；其余角色手写 `for` 循环多次 `execute_action()`。后续开发应选择统一模式。

### 测试文件过大
`test/` 目录下 11 个文件（402 tests），后续新增测试应放入对应模块文件。

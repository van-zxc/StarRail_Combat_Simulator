# Light Cone Pipeline Guide

How to implement a new light cone from source data to combat engine.
References: Arrows (20000), PostOpConversation (21000), NightOnTheMilkyWay (23000).

---

## 1. Key Files

| File | Purpose |
|------|---------|
| `data/light_cone_data/{id}.json` | Raw data (stats, skill, params, promotions) |
| `entities/light_cones/base.py` | `BaseLightCone` + registry + level system + path mapping |
| `entities/light_cones/<name>.py` | Concrete light cone class + effect |
| `entities/light_cones/__init__.py` | Export new LC |
| `entities/base.py` | `EquipmentEffect` ABC (`on_equip` / `on_combat_start` / `on_unequip`) |
| `core/combat_engine.py` | `on_combat_start` wiring + `_decrement_modifiers(unit)` |
| `entities/characters/base.py` | `equip_light_cone()` with path check |
| `test/test_light_cones.py` | Tests |
| `docs/known_issues.md` | Untested behaviors tracked with code references |

---

## 2. Data Reference

Open `data/light_cone_data/{id}.json`. Key fields:

```json
{
  "id": "20000",
  "name": "锋镝",
  "rarity": 5,
  "path": "巡猎",
  "path_key": "Rogue",
  "path_en": "The Hunt",
  "skill_name": "危机",
  "skill_desc": "战斗开始时，暴击率提高#1[i]%，持续#2[i]回合。",
  "params": [[0.12, 3], [0.15, 3], ...],
  "properties": [[], [], ...],
  "promotions": { "levels": [
    { "hp_base": 38.4, "hp_step": 5.76, "atk_base": 14.4, "atk_step": 2.16, "def_base": 12.0, "def_step": 1.8 },
    ...
  ]}
}
```

- `params[5]`: one per superimpose rank (S1-S5). May have 1 to 6+ numbers per rank.
- `properties[5]`: permanent stat bonuses per rank. Empty `[]` means conditional-only effects.
- `promotions.levels[7]`: HP/ATK/DEF growth per promotion bracket (copy directly into `_PROMOTIONS`).
- `path_key`: StarRailRes path key (`Rogue`→HUNT, `Mage`→ERUDITION, etc.). Maps via `BaseLightCone._PATH_KEY_TO_ENUM`.

### Lv80 Stat Verification

```python
# Last promotion (index 6, levels 70→80):
lv80_hp  = levels[6]["hp_base"]  + levels[6]["hp_step"]  * 10  # 38.4 + 5.76*10 = 96.0 ... wait 391.68 + 5.76*10 = 449.28
lv80_atk = levels[6]["atk_base"] + levels[6]["atk_step"] * 10
lv80_def = levels[6]["def_base"] + levels[6]["def_step"] * 10
```

---

## 3. Step-by-Step Checklist

### Step 1: Create the light cone class

Create `entities/light_cones/<slug>.py`:

```python
class <Name>(BaseLightCone):
    _default_id = "<numeric_id>"
    _default_name = "<zh_name>"
    _default_path_key = "<path_key>"    # "Rogue"/"Mage"/"Priest"/etc.

    _PROMOTIONS = [                     # from data/light_cone_data/{id}.json
        {"hp_base": ..., "hp_step": ..., "atk_base": ..., "atk_step": ..., "def_base": ..., "def_step": ...},
        ... # 7 entries total
    ]

    def __init__(self, id: str = "", **kwargs):
        super().__init__(id=id, **kwargs)
        if self.effect is None:
            self.effect = <Name>Effect(self.superimpose)
```

**Rules**:
- `_default_path_key` maps to `PathType` via `_PATH_KEY_TO_ENUM`. Set it; do NOT leave it empty
- `_PROMOTIONS` is the 7-tier growth data. `_default_base_*` is NOT needed — the base class computes from `_PROMOTIONS` + `level`
- `id: str = ""` is required as first positional param for registry compatibility

### Step 2: Implement EquipmentEffect

```python
class <Name>Effect(EquipmentEffect):
    _PARAMS = [ ... ]    # from params[5] array — one sub-array per superimpose rank
    _SOURCE = "LightCone_<id>"

    def __init__(self, superimpose=1):
        self.superimpose = max(1, min(superimpose, 5))
        self._character = None
        self._state = None          # if you need state.alive_enemies
        self._cb_one: callable = None
        self._cb_two: callable = None
        # Store ALL callback references for on_unequip cleanup

    def on_equip(self, character):
        # Permanent stat bonuses from JSON properties[rank][*].type + value
        # Or NO-OP if properties array is empty
        pass

    def on_combat_start(self, state, character):
        # Store state ref if needed
        # Subscribe to ALL events this effect depends on
        # Store lambda callback references as instance attributes
        # Call any initial setup logic (e.g., _recalc_stacks())
        pass

    # -- event handlers (named _on_<event>) --

    def on_unequip(self, character):
        # 1. purge_source for ALL source strings used
        # 2. unsubscribe ALL events with their stored callbacks
        pass
```

**Critical**:
- Store all lambda callbacks as `self._cb_*` so `unsubscribe` can find them
- If using multiple source strings (e.g. for ATK vs DMG), `purge_source` each one
- Check `caster is self._character` in event handlers where the event fires for any character

### Step 3: Register in __init__.py

```python
from entities.light_cones.<slug> import <Name>
```

Registration is automatic via `__init_subclass__` + `_default_id`.

### Step 4: Add imports to test file

```python
from entities.light_cones.<slug> import <Name>, <Name>Effect
```

No other wiring needed — `starrail_combat.py` is not required.

### Step 5: Write tests

Test class template:

```python
class Test<Name>LightCone:
    """<rarity>* <path> light cone: <short description>."""

    def _make_char(self):
        """Character with matching path."""
        c = create_test_character(...)
        c.path = PathType.<MATCHING_PATH>  # must match _default_path_key!
        return c

    def _make_setup(self, ...):
        char = self._make_char()
        enemy = Enemy(...)
        state = GameState(characters=[char], enemies=[enemy])
        engine = CombatEngine(state)
        return char, enemy, state, engine

    # Registry
    def test_registry(self):
        lc = LightCone("<id>")
        assert isinstance(lc, <Name>)

    # Level system
    def test_lv80_stats(self):
        lc = LightCone("<id>")
        assert lc.base_hp == pytest.approx(<lv80_hp>)

    # Permanent effect on equip
    def test_permanent_stat(self):
        char = self._make_char()
        lc = LightCone("<id>")
        char.equip_light_cone(lc)
        ...

    # Event-triggered effect
    def test_effect_on_event(self):
        char, _, _, engine = self._make_setup()
        lc = LightCone("<id>")
        char.equip_light_cone(lc)
        lc.effect.on_combat_start(engine.state, char)
        engine.event_bus.emit(EventType.<EVENT>, ...)
        ...

    # Owner check: other character's event should not trigger
    def test_effect_only_for_owner(self):
        ...

    # Duration / expiry
    def test_buff_expiry(self):
        engine._decrement_modifiers(unit=char)  # tick 1 turn

    # Unequip cleanup
    def test_unequip_cleans_up(self):
        bare = LightCone(id="Bare", base_hp=10, base_atk=10, base_def=10)
        char.equip_light_cone(bare)
        assert not any(m.source == "LightCone_<id>" for m in char.stats.active_modifiers)

    # Mismatched path prevents effect
    def test_mismatched_path_skips_effect(self):
        ...
```

**Rules**:
- Never `engine.run()` — consumes durations, runs full battle
- Use `engine.event_bus.emit(EventType.X, ...)` for event triggers
- Use `engine._decrement_modifiers(unit=char)` for turn simulation
- **Always create a character with matching path** via `char.path = PathType.X` or `create_test_character(..., path=...)`

---

## 4. Important Rules

### Path Restriction

- Each light cone has `_default_path_key` mapped to `PathType`
- `equip_light_cone()` checks: `if lc.path != char.path` → skips `on_equip`
- `combat_engine` also checks before calling `on_combat_start`
- **Base HP/ATK/DEF always apply**, regardless of path match
- `path_key=""` means no restriction (backward compat for test light cones)
- Path key → PathType mapping in `BaseLightCone._PATH_KEY_TO_ENUM`

### Level System

- `_PROMOTIONS` with 7 bracket entries drives stat calculation
- `BaseLightCone._calc_stat(key, level)` uses piecewise linear interpolation
- Breakpoints (1, 20, 30, 40, 50, 60, 70, 80) are exact; mid-level values are interpolated
- Default level is 80; use `LightCone("<id>", level=50)` for lower levels
- No `_PROMOTIONS` → falls back to `_default_base_*` (backward compat)

### Duration Behavior

- "持续X回合" means X of the OWNER's normal-turn actions
- `tick_timing="owner_turn_end"` (default) ticks AFTER owner's normal turn
- FUA / Extra Turn / Ultimate插队 do NOT call `_decrement_modifiers`
- `_decrement_modifiers(unit=actor)` only ticks the ACTOR's modifiers
- Set `dispellable=False` for all equipment modifiers

### Modifier Source Convention

**强制规则: 同一个光锥的不同 buff/debuff 必须使用不同的 source tag。**

- 每个 StatModifier 的 `source` 字段必须是独一无二的字符串
- 格式: `"LightCone_<id>_<EFFECT>"`，其中 `<EFFECT>` 是能区分效果的短标识
- 示例: `"LightCone_21002_DEF"` 和 `"LightCone_21002_RES"`（余生的第一天）
- **严禁**多个不同 stat_type 的 modifier 共用同一个 source 字符串
- 原因: `purge_source()` 会移除所有匹配该 source 的 modifier，共用 source 会导致 A 效果被误清或 B 效果被误判为"已存在"

**命名建议**:
- 常驻属性 buff: `_SOURCE_<STAT>` (如 `_SOURCE_DEF`, `_SOURCE_ATK`, `_SOURCE_EHR`)
- 条件触发 buff: `_SOURCE_<COND>` 或 `_SOURCE_COND` (如 `_SOURCE_COND`, `_SOURCE_CDMG`)
- 多个相同类型但不同来源的: 加数字或场景后缀区分
- 动态 source（如 NightMilkyWay 的 break DMG）: `f"{self._SOURCE}_DMG"`

**on_unequip 规则**:
- 必须 `purge_source()` 每一个 source 字符串
- 必须对目标为队友的 modifier 也要清除（遍历所有队友 purge）

### Event Subscription Lifecycle

```python
def on_combat_start(self, state, character):
    self._cb_x = lambda **kw: self._on_event_x()
    state.event_bus.subscribe(EventType.X, self._cb_x)

def on_unequip(self, character):
    if self._cb_x and character.event_bus:
        character.event_bus.unsubscribe(EventType.X, self._cb_x)
```

- Always store lambda as `self._cb_*` — never inline `subscribe(type, lambda: ...)` without storing
- Unsubscribe ALL events in `on_unequip`
- Guard with `is not None` / `hasattr` checks

---

## 5. Effect Pattern Catalog

### Pattern A: On Battle Start (one-time buff)

**Example**: Arrows (20000), future Cruising (24001)

Subscribe to `BATTLE_START`, apply `StatModifier` with `duration`.

### Pattern B: Permanent Stat Bonus (from properties)

**Example**: PostOpConversation ERR (21000)

When JSON `properties[n]` has entries: in `on_equip`, apply `StatModifier` with NO duration.

```python
def on_equip(self, character):
    val = self._PROPERTIES[self.superimpose - 1]
    mod = StatModifier(STAT, PERCENT, val, source=self._SOURCE, dispellable=False)
    character.stats.apply_modifier(mod, "refresh")
```

Property type → StatType mapping:
| JSON property type | StatType |
|-------------------|----------|
| `CriticalChanceBase` | `CRIT_RATE` |
| `CriticalDamageBase` | `CRIT_DMG` |
| `AttackAddedRatio` | `ATK` |
| `DefenceAddedRatio` | `DEF` |
| `HPAddedRatio` | `HP` |
| `SpeedAddedRatio` | `SPD` |
| `SPRatioBase` | `ERR` |
| `BreakDamageAddedRatioBase` | `BREAK_EFFECT` |
| `StatusProbabilityBase` | `EFFECT_HIT_RATE` |
| `StatusResistanceBase` | `EFFECT_RES` |

### Pattern C: On Ultimate Cast (conditional buff)

**Example**: PostOpConversation heal boost (21000)

Subscribe to `ON_ULTIMATE_INSERTED`, check `caster is self._character`, apply buff.

```python
def on_combat_start(self, state, character):
    self._cb_ult = lambda **kw: self._on_ult(kw.get("character"))
    state.event_bus.subscribe(EventType.ON_ULTIMATE_INSERTED, self._cb_ult)

def _on_ult(self, caster):
    if caster is not self._character:
        return
    mod = StatModifier(STAT, PERCENT, val, source=self._SOURCE, duration=1, dispellable=False)
    self._character.stats.apply_modifier(mod, "refresh")
```

### Pattern D: Dynamic Enemy-Stacking

**Example**: NightOnTheMilkyWay ATK stacks (23000)

Track number of alive enemies, recalculate stacks on relevant events. Use `"refresh"` policy to update value.

```python
def _recalc_stacks(self):
    n = len(self._state.alive_enemies)
    stacks = min(n, MAX_STACKS)
    mod_value = stacks * per_stack_value
    if mod_value > 0:
        mod = StatModifier(ATK, PERCENT, mod_value, source=self._SOURCE, dispellable=False)
        self._character.stats.apply_modifier(mod, "refresh")
    else:
        self._character.stats.purge_source(self._SOURCE)
```

Subscribe to:
- `WAVE_START` → new wave, recount
- `UNIT_DOWNED` → enemy killed, recount
- Manual initial call at end of `on_combat_start`

### Pattern E: On Weakness Break (triggered buff)

**Example**: NightOnTheMilkyWay DMG bonus (23000)

Subscribe to `ON_WEAKNESS_BREAK`, apply buff with `duration=1`.

```python
self._cb_break = lambda **kw: self._on_break()
state.event_bus.subscribe(EventType.ON_WEAKNESS_BREAK, self._cb_break)

def _on_break(self):
    mod = StatModifier(DMG_BONUS, PERCENT, val,
                       source=f"{self._SOURCE}_DMG", duration=1, dispellable=False)
    self._character.stats.apply_modifier(mod, "refresh")
```

### Pattern F: On Kill (triggered buff)

**Example**: future Cruising (24001)

Subscribe to `ON_KILL`, apply conditional ATK% for N turns.

### Pattern G: Multi-Event Cleanup

When the effect subscribes to 2+ events, `on_unequip` must unsubscribe each and purge each source:

```python
def on_unequip(self, character):
    character.stats.purge_source(self._SOURCE)
    character.stats.purge_source(f"{self._SOURCE}_DMG")
    if character.event_bus:
        bus = character.event_bus
        if self._cb_a: bus.unsubscribe(EventType.A, self._cb_a)
        if self._cb_b: bus.unsubscribe(EventType.B, self._cb_b)
        if self._cb_w: bus.unsubscribe(EventType.WAVE_START, self._cb_w)
```

---

## 6. Quick Reference: Event Payloads

| Event | Emit Signature | Relevant Fields |
|-------|---------------|-----------------|
| `BATTLE_START` | `engine=self` | — |
| `ON_ULTIMATE_INSERTED` | `character=char, target=target` | `character` (caster) |
| `ON_WEAKNESS_BREAK` | `source=character, target=target` | `source` (breaker) |
| `UNIT_DOWNED` | `unit=target, source=source` | `unit` (dead entity) |
| `WAVE_START` | — | — |
| `ON_KILL` | — | — |
| `TURN_START` / `TURN_END` | `unit=actor, engine=self` | `unit` |

---

## 7. Quick Reference: Mapping JSON to Code

| JSON Field | Code Usage |
|-----------|-----------|
| `id` | `_default_id`, registry key |
| `path_key` | `_default_path_key`, maps to `PathType` enum |
| `params[S-1][0]` | Main effect value (crit rate, ATK%, DMG%, etc.) |
| `params[S-1][1]` | Secondary effect or duration |
| `properties[S-1]` | Array of `{type, value}` permanent bonuses |
| `properties[S-1][0].type` | Property type string → see §5 Pattern B mapping |
| `properties[S-1][0].value` | Property value |
| `promotions.levels[0..6]` | Copy all 7 entries into `_PROMOTIONS` |
| `rarity` | Informational (3, 4, 5) |
| `skill_desc` | Informational — read to understand effect logic |

---

## 8. Related Docs

- `docs/todo.md` — development roadmap with light cone completion status
- `docs/known_issues.md` — untested behaviors with code references (e.g., enemy counting for spawned units)

# Light Cone Pipeline Guide

How to implement a new light cone from source data to combat engine. Example: Arrows (20000).

---

## 1. Key Files

| File | Purpose |
|------|---------|
| `light_cone_data/{id}.json` | Raw data (stats, skill, params) |
| `entities/light_cones/base.py` | `BaseLightCone` + registry |
| `entities/light_cones/<name>.py` | Concrete light cone + effect |
| `entities/light_cones/__init__.py` | Export new LC |
| `entities/base.py` | `EquipmentEffect` ABC |
| `core/combat_engine.py` | `on_combat_start` wiring |
| `starrail_combat.py` | Top-level re-export |
| `test_starrail_combat.py` | Tests |

---

## 2. Data Reference

Open `light_cone_data/{id}.json`. Key fields:

```json
{
  "id": "20000",
  "name": "锋镝",
  "rarity": 5,
  "path": "巡猎",
  "path_key": "Rogue",
  "skill_name": "危机",
  "skill_desc": "战斗开始时，暴击率提高#1[i]%，持续#2[i]回合。",
  "params": [[0.12, 3], [0.15, 3], ...],
  "properties": [[], [], ...],
  "promotions": { "levels": [{ "hp_base": 38.4, "hp_step": 5.76, ... }] }
}
```

- `params[5]`: one per superimpose rank (S1-S5)
- `properties[5]`: permanent stat bonuses per rank (type + value). Empty means conditional only.
- `promotions.levels[7]`: HP/ATK/DEF growth (base + step per level bracket)

### Lv80 Stats Formula

Take the last promotion level (index 6, levels 70-80):
```
stat_lv80 = base + step * 10
```
Example for 20000: HP = 391.68 + 5.76 * 10 = 449.28

---

## 3. Step-by-Step Checklist

### Step 1: Create the light cone class

Create `entities/light_cones/<slug>.py`:

```python
class <Name>(BaseLightCone):
    _default_id = "<numeric_id>"
    _default_name = "<zh_name>"
    _default_base_hp = <lv80_hp>
    _default_base_atk = <lv80_atk>
    _default_base_def = <lv80_def>

    def __init__(self, id: str = "", **kwargs):
        superimpose = kwargs.pop("superimpose", 1)
        if not isinstance(superimpose, int):
            superimpose = 1
        super().__init__(id=id, superimpose=superimpose, **kwargs)
        if self.effect is None:
            self.effect = <Name>Effect(self.superimpose)
```

### Step 2: Implement EquipmentEffect

In the same file, create the effect class:

```python
class <Name>Effect(EquipmentEffect):
    _PARAMS = [ ... ]  # from light_cone_data/{id}.json params[5]
    _SOURCE = "LightCone_<id>"

    def __init__(self, superimpose=1):
        self.superimpose = max(1, min(superimpose, 5))
        self._character = None
        self._callback = None

    def on_equip(self, character):
        # Add permanent StatModifier if properties[rank] has entries
        # Use self._PARAMS[self.superimpose - 1] for rank-specific values
        pass

    def on_combat_start(self, state, character):
        # Subscribe to events (BATTLE_START, ON_KILL, etc.)
        # Store callback references for cleanup
        pass

    def _on_event(self):
        # Apply StatModifier with:
        #   source=self._SOURCE
        #   dispellable=False
        #   duration=int(params[...])
        pass

    def on_unequip(self, character):
        # Purge modifiers and unsubscribe events
        pass
```

### Step 3: Register in __init__.py

Add to `entities/light_cones/__init__.py`:
```python
from entities.light_cones.<slug> import <Name>
```

Registration is automatic via `__init_subclass__` + `_default_id`.

### Step 4: Wire imports

Add to `starrail_combat.py`:
```python
from entities.light_cones.<slug> import <Name>
```

### Step 5: Write tests

Add a test class in `test_starrail_combat.py`:

```python
class Test<Name>LightCone:
    def test_registry(self):
        lc = LightCone("<id>")
        assert isinstance(lc, <Name>)

    def test_effect_params_s1_s5(self):
        ...

    def test_on_equip(self):
        ...

    def test_on_combat_start(self):
        # Manual setup pattern (do NOT use engine.run()):
        # 1. Create chars, enemies, state
        # 2. Create engine (for event_bus injection)
        # 3. lc.effect.on_combat_start(state, char)
        # 4. engine.event_bus.emit(EventType.BATTLE_START)
        # 5. Check modifiers

    def test_buff_expiry(self):
        # Use engine._decrement_modifiers(unit=char) to simulate turns

    def test_buff_not_ticked_by_other(self):
        # engine._decrement_modifiers(unit=enemy) should not affect char

    def test_unequip_cleanup(self):
        ...
```

---

## 4. Important Rules

### Duration Behavior

- "持续X回合" means X of the OWNER's actions
- Set `tick_timing="owner_turn_end"` (default)
- Buff ticks only via `engine._decrement_modifiers(unit=owner)` after each normal turn
- FUA / Extra Turn / Ultimate do NOT decrement (matching engine behavior)
- Set `dispellable=False` for equipment buffs

### Superimpose

- `BaseLightCone.superimpose` defaults to 1, range 1-5
- `_PARAMS[self.superimpose - 1]` accesses rank params
- `properties[self.superimpose - 1]` accesses rank stat bonuses

### Event Subscription Lifecycle

- Subscribe in `on_combat_start`, store callback reference
- Unsubscribe in `on_unequip` via `event_bus.unsubscribe(type, callback)`
- Never use lambda without storing the reference

### Modifier Source Convention

- Use `"LightCone_<id>"` as source string
- `purge_source()` removes ALL modifiers with this source on unequip

### Test Pattern

- Never call `engine.run()` in unit tests (runs full battle, consumes durations)
- Use manual setup: `on_combat_start()` + `emit(BATTLE_START)` + `_decrement_modifiers(unit=...)`

---

## 5. Common Patterns

### Pattern A: On Battle Start (one-time buff)
See: Arrows (20000), Cruising (24001)

Subscribe to `BATTLE_START`, apply StatModifier with duration.

### Pattern B: On Kill (triggered buff)
See: Cruising (24001)

Subscribe to `ON_KILL`, apply conditional buff for N turns.

### Pattern C: Permanent Stat Bonus
See: light cones with non-empty `properties` arrays

In `on_equip`, apply permanent StatModifier (no duration).

### Pattern D: Stacking Buff
See: Seele LC (23001)

Subscribe to `AFTER_ACTION` or similar, increment stack counter, apply scaled modifier.

---

## 6. Quick Reference: Mapping JSON to Code

| JSON Field | Code Usage |
|-----------|-----------|
| `params[n][0]` | Main effect value (crit rate, ATK%, etc.) |
| `params[n][1]` | Secondary effect value or duration |
| `properties[n]` | Permanent stat bonuses at rank n |
| `properties[n][0].type` | Property type (CriticalChanceBase, AttackAddedRatio, etc.) |
| `properties[n][0].value` | Property value |
| `promotions.levels[6]` | Lv80 stats (hp_base, atk_base, def_base) |

from __future__ import annotations
"""无处可逃 (Nowhere to Run) — 4★ 毁灭光锥。

特效: 攻击力提高#1[i]%，消灭敌方目标时回复#2[i]%攻击力的生命值。
"""

from typing import Optional

from entities.light_cones.base import BaseLightCone
from entities.base import EquipmentEffect, StatModifier


class NowhereToRun(BaseLightCone):
    _default_id = "21033"
    _default_name = "无处可逃"
    _default_path_key = "Warrior"

    _PROMOTIONS = [
        {"hp_base": 43.2, "hp_step": 6.48, "atk_base": 24, "atk_step": 3.6, "def_base": 12, "def_step": 1.8},
        {"hp_base": 95.04, "hp_step": 6.48, "atk_base": 52.8, "atk_step": 3.6, "def_base": 26.4, "def_step": 1.8},
        {"hp_base": 164.16, "hp_step": 6.48, "atk_base": 91.2, "atk_step": 3.6, "def_base": 45.6, "def_step": 1.8},
        {"hp_base": 233.28, "hp_step": 6.48, "atk_base": 129.6, "atk_step": 3.6, "def_base": 64.8, "def_step": 1.8},
        {"hp_base": 302.4, "hp_step": 6.48, "atk_base": 168, "atk_step": 3.6, "def_base": 84, "def_step": 1.8},
        {"hp_base": 371.52, "hp_step": 6.48, "atk_base": 206.4, "atk_step": 3.6, "def_base": 103.2, "def_step": 1.8},
        {"hp_base": 440.64, "hp_step": 6.48, "atk_base": 244.8, "atk_step": 3.6, "def_base": 122.4, "def_step": 1.8},
    ]

    def __init__(self, id: str = "", **kwargs):
        super().__init__(id=id, **kwargs)
        if self.effect is None:
            self.effect = NowhereToRunEffect(self.superimpose)


class NowhereToRunEffect(EquipmentEffect):
    _PARAMS = [[0.24, 0.12], [0.30, 0.15], [0.36, 0.18], [0.42, 0.21], [0.48, 0.24]]
    _SOURCE = "LightCone_21033"

    def __init__(self, superimpose: int = 1) -> None:
        self.superimpose = max(1, min(superimpose, 5))
        self._character: Optional["Character"] = None
        self._cb_kill: Optional[callable] = None

    def on_equip(self, character: "Character") -> None:
        from core.enums import StatType, StatModifierType

        atk_pct = self._PARAMS[self.superimpose - 1][0]
        mod = StatModifier(
            stat_type=StatType.ATK,
            modifier_type=StatModifierType.PERCENT,
            value=atk_pct,
            source=self._SOURCE,
            dispellable=False,
        )
        character.stats.apply_modifier(mod, "refresh")

    def on_combat_start(self, state: "GameState", character: "Character") -> None:
        from core.events import EventType

        self._character = character
        self._cb_kill = lambda **kw: self._on_kill(kw.get("source"))
        state.event_bus.subscribe(EventType.ON_KILL, self._cb_kill)

    def _on_kill(self, source: "Character") -> None:
        if source is not self._character:
            return
        from core.enums import StatType

        heal_pct = self._PARAMS[self.superimpose - 1][1]
        heal_amount = int(self._character.stats.get_total_stat(StatType.ATK) * heal_pct)
        self._character.receive_heal(heal_amount)

    def on_unequip(self, character: "Character") -> None:
        from core.events import EventType

        character.stats.purge_source(self._SOURCE)
        if self._cb_kill is not None and character.event_bus is not None:
            character.event_bus.unsubscribe(EventType.ON_KILL, self._cb_kill)

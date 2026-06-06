from __future__ import annotations

"""不老者的仙舟 — 2件套 (使装备者的生命值上限提高12%。当装备者的速度大于等于120时，我方全体攻击力提高8%)。

注意: 多名角色同时装备此套装时效果叠加。每人使用独立 source 标识
(RelicSet_302_2pc_team_{id(character)})，确保卸装时只清理自己的队伍 buff。
"""

from typing import Optional

from core.enums import StatType, StatModifierType
from entities.base import StatModifier
from entities.relics.base import BaseRelic, RelicSetEffect
from starrail_combat import RelicPart


class FleetAgelessSphere(BaseRelic):
    _default_part = RelicPart.PLANAR_SPHERE
    _default_set_id = "302"


class FleetAgelessRope(BaseRelic):
    _default_part = RelicPart.LINK_ROPE
    _default_set_id = "302"


class FleetOfTheAgeless(RelicSetEffect):
    set_id = "302"
    set_type = "planar"

    _SOURCE_2PC = "RelicSet_302_2pc"

    def __init__(self) -> None:
        self._character: Optional["Character"] = None
        self._state = None
        self._team_source: str = ""
        self._cb_after_action: Optional[callable] = None

    def on_equip(self, character, piece_count):
        if piece_count >= 2:
            character.stats.add_modifier(StatModifier(
                StatType.HP, StatModifierType.PERCENT, 0.12,
                source=self._SOURCE_2PC, dispellable=False,
            ))

    def on_combat_start(self, state, character):
        from core.events import EventType

        self._character = character
        self._state = state
        self._team_source = f"RelicSet_302_2pc_team_{id(character)}"
        self._check_condition()
        self._cb_after_action = lambda **kw: self._check_condition()
        state.event_bus.subscribe(EventType.ON_ABILITY_PROPERTY_CHANGE, self._cb_after_action)  # JSON: OnAbilityPropertyChange:Speed

    def _check_condition(self) -> None:
        if not self._character.is_alive:
            self._purge_team_buff()
            return
        spd = self._character.speed
        if spd >= 120.0:
            for char in self._state.alive_characters:
                mod = StatModifier(
                    StatType.ATK, StatModifierType.PERCENT, 0.08,
                    source=self._team_source, dispellable=False,
                )
                char.stats.apply_modifier(mod, "no_stack")
        else:
            self._purge_team_buff()

    def _purge_team_buff(self) -> None:
        for char in self._state.characters:
            char.stats.purge_source(self._team_source)

    def on_unequip(self, character):
        from core.events import EventType

        character.stats.purge_source(self._SOURCE_2PC)
        if self._state is not None:
            for char in self._state.characters:
                char.stats.purge_source(self._team_source)
        if self._cb_after_action is not None and character.event_bus is not None:
            character.event_bus.unsubscribe(EventType.ON_ABILITY_PROPERTY_CHANGE, self._cb_after_action)  # JSON: OnAbilityPropertyChange:Speed

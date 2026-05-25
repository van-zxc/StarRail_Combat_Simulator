from __future__ import annotations
"""BaseRelic + RelicSetEffect — 遗器基类与套装效果。"""

from abc import ABC, abstractmethod
from typing import Optional


class BaseRelic:
    _default_part: "RelicPart" = None
    _default_set_id: str = ""
    _default_main_stat: "StatModifier" = None
    _default_sub_stats: list["StatModifier"] = []

    def __init__(
        self,
        part: "RelicPart" = None,
        set_id: str = "",
        main_stat: "StatModifier" = None,
        sub_stats: Optional[list["StatModifier"]] = None,
    ) -> None:
        self.part = part if part is not None else self._default_part
        self.set_id = set_id or self._default_set_id
        self.main_stat = main_stat if main_stat is not None else self._default_main_stat
        self.sub_stats = list(sub_stats) if sub_stats is not None else list(self._default_sub_stats)


class RelicSetEffect(ABC):
    set_id: str = ""
    set_type: str = "cavern"

    _registry: dict[str, type["RelicSetEffect"]] = {}

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        if cls.set_id:
            cls._registry[cls.set_id] = cls

    @abstractmethod
    def on_equip(self, character: "Character", piece_count: int) -> None:
        ...

    def on_combat_start(self, state: "GameState", character: "Character") -> None:
        pass

    def on_unequip(self, character: "Character") -> None:
        pass


def check_and_apply_set_effects(character: "Character") -> None:
    """装备/更换部件时重算套装效果。"""

    for old_eff in getattr(character, "_relic_set_active", {}).values():
        old_eff.on_unequip(character)

    counts: dict[str, int] = {}
    for relic in character.relics.values():
        if relic.set_id:
            counts[relic.set_id] = counts.get(relic.set_id, 0) + 1

    active: dict[str, "RelicSetEffect"] = {}
    for set_id, count in counts.items():
        if set_id in RelicSetEffect._registry:
            eff = RelicSetEffect._registry[set_id]()
            if count >= 2:
                eff.on_equip(character, count)
                active[set_id] = eff

    character._relic_set_active = active


def start_relic_set_effects(state: "GameState", character: "Character") -> None:
    for eff in getattr(character, "_relic_set_active", {}).values():
        eff.on_combat_start(state, character)

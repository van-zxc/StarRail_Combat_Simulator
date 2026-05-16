"""BaseRelic + RelicSetManager — 遗器基类与套装管理器。"""

from __future__ import annotations

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


class RelicSetManager:
    """套装效果管理器 — 当前为存根，预留接口。"""

    @staticmethod
    def check_and_apply_set_effects(character: "Character") -> None:
        pass

"""TemplateCharacter — 通用角色组装模板。"""
from __future__ import annotations

from entities.characters.base import BaseCharacter


class TemplateCharacter(BaseCharacter):
    """标准角色：通过 __init__ 加载技能/行迹/星魂到修饰器池。

    子类必须覆盖 _default_id, _base_stats 等类属性。
    """

    def __init__(
        self,
        character_id: str = "",
        level: int | None = None,
        unlocked_traces: list[str] | None = None,
        eidolon_level: int = 0,
        **kwargs: object,
    ) -> None:
        super().__init__(character_id, level, **kwargs)

        # 技能
        self._init_skills()

        # 行迹 (按解锁列表挂载)
        self._init_traces(unlocked_traces or [])

        # 星魂 (按等级挂载)
        self._init_eidolons(eidolon_level)

    # ─── 子类必须覆写 ───

    def _init_skills(self) -> None:
        """覆写：import skills.py 并绑定到 self._skills。"""
        raise NotImplementedError

    def _init_traces(self, unlocked: list[str]) -> None:
        """覆写：按 unlocked 列表加载 traces.py 中的修饰器。"""
        raise NotImplementedError

    def _init_eidolons(self, level: int) -> None:
        """覆写：按 level 加载 eidolons.py 中的修饰器。"""
        raise NotImplementedError

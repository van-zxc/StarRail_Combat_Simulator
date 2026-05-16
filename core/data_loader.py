"""DataLoader — JSON 数据加载与缓存。"""

from __future__ import annotations

import json
from typing import Optional


class DataLoader:
    """一次性读取 JSON 文件并缓存，供 Character/Enemy 实例化时查询。
    
    所有 JSON 路径均为可选 — 缺失文件时对应数据集为空，调用方自行 fallback。
    """

    def __init__(
        self,
        char_path: str = "",
        enemy_path: str = "",
        lc_path: str = "",
        relic_path: str = "",
    ) -> None:
        self._characters = self._load_json(char_path)
        self._enemies = self._load_json(enemy_path)
        self._light_cones = self._load_json(lc_path)
        self._relics = self._load_json(relic_path)

    @staticmethod
    def _load_json(path: str) -> dict[str, dict]:
        if not path:
            return {}
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return {}

    def get_character_data(self, char_id: str) -> dict:
        if char_id not in self._characters:
            raise KeyError(f"Unknown character: {char_id}")
        return self._characters[char_id]

    def get_enemy_data(self, enemy_id: str) -> dict:
        if enemy_id not in self._enemies:
            raise KeyError(f"Unknown enemy: {enemy_id}")
        return self._enemies[enemy_id]

    def get_light_cone_data(self, lc_id: str) -> dict:
        if lc_id not in self._light_cones:
            raise KeyError(f"Unknown light cone: {lc_id}")
        return self._light_cones[lc_id]

    def get_relic_data(self, relic_id: str) -> dict:
        if relic_id not in self._relics:
            raise KeyError(f"Unknown relic: {relic_id}")
        return self._relics[relic_id]


_data_loader: Optional[DataLoader] = None


def init_data(
    char_path: str = "",
    enemy_path: str = "",
    lc_path: str = "",
    relic_path: str = "",
) -> None:
    """初始化全局 DataLoader（只在程序启动时调用一次）。"""
    global _data_loader
    dl = DataLoader(char_path, enemy_path, lc_path, relic_path)
    _data_loader = dl
    # 解决 __main__ vs starrail_combat 双加载问题
    import sys
    main_module = sys.modules.get("__main__")
    if main_module is not None and hasattr(main_module, "_data_loader"):
        main_module._data_loader = dl


def get_data_loader() -> DataLoader:
    if _data_loader is None:
        import sys
        main_module = sys.modules.get("__main__")
        if main_module is not None and hasattr(main_module, "_data_loader"):
            return main_module._data_loader
        raise RuntimeError("DataLoader not initialized — call init_data() first.")
    return _data_loader

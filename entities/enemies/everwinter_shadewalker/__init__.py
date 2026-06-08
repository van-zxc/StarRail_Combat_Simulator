from __future__ import annotations
"""Everwinter Shadewalker — 深寒徘徊者 (W1 冰·普通)"""

from pathlib import Path
from entities.enemies.base import BaseEnemy
from entities.enemies.enemy_config import load_config_from_json

_HERE = Path(__file__).parent


class EverwinterShadewalker(BaseEnemy):
    _default_name = "Everwinter Shadewalker"

    def __init__(self, level: int = 95, **kwargs: object) -> None:
        kwargs.setdefault("name", "Everwinter Shadewalker")
        super().__init__(level=level, config=load_config_from_json(_HERE), **kwargs)

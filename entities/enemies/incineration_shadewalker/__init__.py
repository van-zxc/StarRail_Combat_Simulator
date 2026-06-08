from __future__ import annotations
"""Incineration Shadewalker — 炽燃徘徊者 (W1 火焰·普通)"""

from pathlib import Path
from entities.enemies.base import BaseEnemy
from entities.enemies.enemy_config import load_config_from_json

_HERE = Path(__file__).parent


class IncinerationShadewalker(BaseEnemy):
    _default_name = "Incineration Shadewalker"

    def __init__(self, level: int = 95, **kwargs: object) -> None:
        kwargs.setdefault("name", "Incineration Shadewalker")
        super().__init__(level=level, config=load_config_from_json(_HERE), **kwargs)

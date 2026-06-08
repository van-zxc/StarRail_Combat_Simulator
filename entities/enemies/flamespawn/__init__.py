from __future__ import annotations
"""Flamespawn — 炎华造物 (XP 火焰·普通)"""

from pathlib import Path
from entities.enemies.base import BaseEnemy
from entities.enemies.enemy_config import load_config_from_json

_HERE = Path(__file__).parent


class Flamespawn(BaseEnemy):
    _default_name = "Flamespawn"

    def __init__(self, level: int = 95, **kwargs: object) -> None:
        kwargs.setdefault("name", "Flamespawn")
        super().__init__(level=level, config=load_config_from_json(_HERE), **kwargs)

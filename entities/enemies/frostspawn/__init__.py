from __future__ import annotations
"""Frostspawn — 霜晶造物 (XP 冰霜·普通)"""

from pathlib import Path
from entities.enemies.base import BaseEnemy
from entities.enemies.enemy_config import load_config_from_json

_HERE = Path(__file__).parent


class Frostspawn(BaseEnemy):
    _default_name = "Frostspawn"

    def __init__(self, level: int = 95, **kwargs: object) -> None:
        kwargs.setdefault("name", "Frostspawn")
        super().__init__(level=level, config=load_config_from_json(_HERE), **kwargs)

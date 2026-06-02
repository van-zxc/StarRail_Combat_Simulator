from __future__ import annotations
"""Baryon — 重子 (反物质军团·普通)"""

from pathlib import Path
from entities.enemies.base import BaseEnemy
from entities.enemies.enemy_config import load_config_from_json

_HERE = Path(__file__).parent


class Baryon(BaseEnemy):
    _default_name = "Baryon"

    def __init__(self, level: int = 95, **kwargs: object) -> None:
        kwargs.setdefault("name", "Baryon")
        super().__init__(level=level, config=load_config_from_json(_HERE), **kwargs)

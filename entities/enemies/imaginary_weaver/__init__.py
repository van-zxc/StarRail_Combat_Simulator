from __future__ import annotations
"""Imaginary Weaver — 虚数编织者 (XP 虚数·普通)"""

from pathlib import Path
from entities.enemies.base import BaseEnemy
from entities.enemies.enemy_config import load_config_from_json

_HERE = Path(__file__).parent


class ImaginaryWeaver(BaseEnemy):
    _default_name = "Imaginary Weaver"

    def __init__(self, level: int = 95, **kwargs: object) -> None:
        kwargs.setdefault("name", "Imaginary Weaver")
        super().__init__(level=level, config=load_config_from_json(_HERE), **kwargs)

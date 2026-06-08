from __future__ import annotations
"""Mask of No Thought — 无想面具 (XP 虚数·普通)"""

from pathlib import Path
from entities.enemies.base import BaseEnemy
from entities.enemies.enemy_config import load_config_from_json

_HERE = Path(__file__).parent


class MaskOfNoThought(BaseEnemy):
    _default_name = "Mask of No Thought"

    def __init__(self, level: int = 95, **kwargs: object) -> None:
        kwargs.setdefault("name", "Mask of No Thought")
        super().__init__(level=level, config=load_config_from_json(_HERE), **kwargs)

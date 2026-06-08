from __future__ import annotations
"""Entranced Dracolion — 入魔机巧·率从狻猊 (W2 仙舟·普通)"""

from pathlib import Path
from entities.enemies.base import BaseEnemy
from entities.enemies.enemy_config import load_config_from_json

_HERE = Path(__file__).parent


class EntrancedDracolion(BaseEnemy):
    _default_name = "Entranced Ingenium Obedient Dracolion"

    def __init__(self, level: int = 95, **kwargs: object) -> None:
        kwargs.setdefault("name", "Entranced Ingenium Obedient Dracolion")
        super().__init__(level=level, config=load_config_from_json(_HERE), **kwargs)

from __future__ import annotations
"""Automaton Spider — 自动机兵·蜘蛛 (W1 机械·普通)"""

from pathlib import Path
from entities.enemies.base import BaseEnemy
from entities.enemies.enemy_config import load_config_from_json

_HERE = Path(__file__).parent


class AutomatonSpider(BaseEnemy):
    _default_name = "Automaton Spider"

    def __init__(self, level: int = 95, **kwargs: object) -> None:
        kwargs.setdefault("name", "Automaton Spider")
        super().__init__(level=level, config=load_config_from_json(_HERE), **kwargs)

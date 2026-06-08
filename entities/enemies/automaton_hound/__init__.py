from __future__ import annotations
"""Automaton Hound — 自动机兵·猎犬 (W1 机械·普通)"""

from pathlib import Path
from entities.enemies.base import BaseEnemy
from entities.enemies.enemy_config import load_config_from_json

_HERE = Path(__file__).parent


class AutomatonHound(BaseEnemy):
    _default_name = "Automaton Hound"

    def __init__(self, level: int = 95, **kwargs: object) -> None:
        kwargs.setdefault("name", "Automaton Hound")
        super().__init__(level=level, config=load_config_from_json(_HERE), **kwargs)

from __future__ import annotations
"""Automaton Beetle — 机械造物 (反物质军团·普通)"""

from pathlib import Path
from entities.enemies.base import BaseEnemy
from entities.enemies.enemy_config import load_config_from_json

_HERE = Path(__file__).parent


class AutomatonBeetle(BaseEnemy):
    _default_name = "Automaton Beetle"

    def __init__(self, level: int = 95, **kwargs: object) -> None:
        kwargs.setdefault("name", "Automaton Beetle")
        super().__init__(level=level, config=load_config_from_json(_HERE), **kwargs)

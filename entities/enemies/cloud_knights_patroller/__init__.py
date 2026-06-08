from __future__ import annotations
"""Cloud Knights Patroller — 云骑军巡逻兵 (W2 仙舟·普通)"""

from pathlib import Path
from entities.enemies.base import BaseEnemy
from entities.enemies.enemy_config import load_config_from_json

_HERE = Path(__file__).parent


class CloudKnightsPatroller(BaseEnemy):
    _default_name = "Cloud Knights Patroller"

    def __init__(self, level: int = 95, **kwargs: object) -> None:
        kwargs.setdefault("name", "Cloud Knights Patroller")
        super().__init__(level=level, config=load_config_from_json(_HERE), **kwargs)

from __future__ import annotations
"""Internal Alchemist — 药王秘传·内丹士 (W2 仙舟·普通)"""

from pathlib import Path
from entities.enemies.base import BaseEnemy
from entities.enemies.enemy_config import load_config_from_json

_HERE = Path(__file__).parent


class InternalAlchemist(BaseEnemy):
    _default_name = "Disciples of Sanctus Medicus Internal Alchemist"

    def __init__(self, level: int = 95, **kwargs: object) -> None:
        kwargs.setdefault("name", "Disciples of Sanctus Medicus Internal Alchemist")
        super().__init__(level=level, config=load_config_from_json(_HERE), **kwargs)

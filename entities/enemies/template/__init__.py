from __future__ import annotations
"""TemplateEnemy — 新敌人的起手式。复制本目录，修改 data.json 和下方类名即可。"""

from pathlib import Path
from entities.enemies.base import BaseEnemy
from entities.enemies.enemy_config import load_config_from_json

_HERE = Path(__file__).parent


class TemplateEnemy(BaseEnemy):
    _default_name = "TemplateEnemy"

    def __init__(self, level: int = 95, **kwargs: object) -> None:
        kwargs.setdefault("name", "TemplateEnemy")
        super().__init__(level=level, config=load_config_from_json(_HERE), **kwargs)

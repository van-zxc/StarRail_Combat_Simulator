from __future__ import annotations

"""Voidranger — 虚卒·敌方怪物。"""

from starrail_combat import ElementType
from entities.enemies.base import BaseEnemy


class Voidranger(BaseEnemy):
    _default_name = "Voidranger"
    _default_hp = 300
    _default_speed = 90
    _default_base_damage = 25
    _default_weaknesses = [ElementType.FIRE, ElementType.ICE]
    _default_max_toughness = 30.0
    _default_level = 95

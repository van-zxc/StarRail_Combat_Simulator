from __future__ import annotations

"""Cruising in the Stellar Sea — 巡猎光锥。"""

from entities.light_cones.base import BaseLightCone


class Cruising(BaseLightCone):
    _default_id = "24001"
    _default_name = "星海巡航"
    _default_path_key = "Rogue"

    _PROMOTIONS = [
        {"hp_base": 43.2, "hp_step": 6.48, "atk_base": 24, "atk_step": 3.6, "def_base": 21, "def_step": 3.15},
        {"hp_base": 95.04, "hp_step": 6.48, "atk_base": 52.8, "atk_step": 3.6, "def_base": 46.2, "def_step": 3.15},
        {"hp_base": 164.16, "hp_step": 6.48, "atk_base": 91.2, "atk_step": 3.6, "def_base": 79.8, "def_step": 3.15},
        {"hp_base": 233.28, "hp_step": 6.48, "atk_base": 129.6, "atk_step": 3.6, "def_base": 113.4, "def_step": 3.15},
        {"hp_base": 302.4, "hp_step": 6.48, "atk_base": 168, "atk_step": 3.6, "def_base": 147, "def_step": 3.15},
        {"hp_base": 371.52, "hp_step": 6.48, "atk_base": 206.4, "atk_step": 3.6, "def_base": 180.6, "def_step": 3.15},
        {"hp_base": 440.64, "hp_step": 6.48, "atk_base": 244.8, "atk_step": 3.6, "def_base": 214.2, "def_step": 3.15},
    ]

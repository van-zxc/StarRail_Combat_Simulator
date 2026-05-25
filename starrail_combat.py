"""崩坏：星穹铁道 — 回合制战斗引擎 (入口模块)

本文件仅做 re-export，所有实现位于 core/ 和 entities/ 模块。
"""

from __future__ import annotations

# 保留顶层 import 以支撑 mock patch("starrail_combat.random")
import random  # noqa: F401

# ── 枚举 ──
from core.enums import (
    ActionType,
    DamageType,
    ElementType,
    PathType,
    RelicPart,
    StatModifierType,
    StatType,
)

# ── 数据加载 ──
from core.data_loader import DataLoader, get_data_loader, init_data

# ── 属性面板 ──
from core.entity_stats import EntityStats

# ── 战斗引擎 ──
from core.game_state import GameState
from core.combat_engine import CombatEngine

# ── 测试工厂 ──
from core.test_factory import create_test_character

# ── 实体导入 + 向后兼容别名 ──
from entities.characters.base import BaseCharacter
from entities.enemies.base import BaseEnemy
from entities.light_cones.base import BaseLightCone
from entities.relics.base import BaseRelic, RelicSetEffect, check_and_apply_set_effects, start_relic_set_effects
from entities.base import DoTStatus, EquipmentEffect, Fighter, StatModifier, ShieldStatus, Memosprite, CCStatus, CertifiedBanger, ToughnessDamagePacket, HitPacket
from entities.aha import Aha

Character = BaseCharacter
Enemy = BaseEnemy
LightCone = BaseLightCone
Relic = BaseRelic

# ── 演示脚本 ──
if __name__ == "__main__":
    init_data()
    march = Character("March7th")
    dan_heng = Character("DanHeng")
    voidranger = Enemy.from_template("Voidranger")
    state = GameState(characters=[march, dan_heng], enemies=[voidranger])
    CombatEngine(state).run()

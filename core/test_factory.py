"""create_test_character — 测试辅助工厂，走 BaseCharacter.__init__ 正常链路。"""

from core.entity_stats import stats_defaults
from core.enums import ElementType, PathType, StatType


def create_test_character(
    name: str,
    hp: int = 200,
    speed: int = 100,
    atk: float = 50.0,
    max_energy: int = 100,
    crit_rate: float = 0.05,
    crit_dmg: float = 0.50,
    element: ElementType = ElementType.PHYSICAL,
    path: PathType = PathType.HUNT,
    level: int = 1,
) -> "Character":
    """用自定义属性创建角色（供测试使用），不依赖 JSON 数据。"""
    from entities.characters.base import BaseCharacter

    stats = stats_defaults()
    stats[StatType.HP] = float(hp)
    stats[StatType.ATK] = atk
    stats[StatType.SPD] = float(speed)
    stats[StatType.DEF] = 60.0
    stats[StatType.CRIT_RATE] = crit_rate
    stats[StatType.CRIT_DMG] = crit_dmg
    stats[StatType.ERR] = 1.0
    stats[StatType.MAX_ENERGY] = float(max_energy)
    return BaseCharacter(
        name,
        level=level,
        _stats_override=stats,
        _element_override=element,
        _path_override=path,
    )

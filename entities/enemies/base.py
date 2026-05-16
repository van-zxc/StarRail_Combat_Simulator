"""BaseEnemy — 敌方目标基类 (JSON 优先，类属性 fallback)。"""

from __future__ import annotations

from typing import Optional

from core.entity_stats import stats_defaults
from entities.base import DoTStatus, Fighter, CCStatus, ImplantedWeakness


class BaseEnemy(Fighter):
    """敌方目标，拥有固定伤害值、弱点属性、韧性条、与等级驱动的防御面板。

    子类可覆盖类属性设置默认值；from_template() JSON 优先 → 子类 fallback。
    """

    _enemy_registry: dict[str, type["BaseEnemy"]] = {}

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        if cls._default_name:
            BaseEnemy._enemy_registry[cls._default_name] = cls

    def __new__(cls, name: str = "", **kwargs: object) -> "BaseEnemy":
        if cls is not BaseEnemy:
            return super().__new__(cls)
        if name and name in cls._enemy_registry:
            sub_cls = cls._enemy_registry[name]
            return sub_cls.__new__(sub_cls)
        return super().__new__(cls)

    _SPD_SCALING: list[tuple[tuple[int, int], float]] = [
        ((1, 64), 1.0),
        ((65, 77), 1.1),
        ((78, 85), 1.2),
        ((86, 100), 1.32),
    ]

    _default_name: str = ""
    _default_hp: int = 300
    _default_speed: int = 90
    _default_base_damage: int = 25
    _default_weaknesses: list["ElementType"] = None
    _default_max_toughness: float = 0.0
    _default_level: int = 95

    def __init__(
        self,
        name: str = "",
        hp: Optional[int] = None,
        speed: Optional[int] = None,
        base_damage: Optional[int] = None,
        weaknesses: Optional[list["ElementType"]] = None,
        max_toughness: Optional[float] = None,
        level: Optional[int] = None,
    ) -> None:
        from starrail_combat import ElementType, EntityStats, StatType

        n = name or self._default_name
        lv = level if level is not None else self._default_level
        hp_val = hp if hp is not None else self._default_hp
        spd_val = speed if speed is not None else self._default_speed

        self.level = lv
        # 效果命中等级成长
        eh_base = 0.0
        if lv > 50:
            eh_base = min((lv - 50) * 0.008, 0.40)
        if lv >= 120:
            eh_base += 0.10
        # 速度等级乘区
        scale = 1.0
        for (lo, hi), s in self._SPD_SCALING:
            if lo <= lv <= hi:
                scale = s
                break
        spd_val = int(spd_val * scale)
        def_base = lv * 10 + 200
        base_data = stats_defaults()
        base_data[StatType.HP] = float(hp_val)
        base_data[StatType.SPD] = float(spd_val)
        base_data[StatType.DEF] = float(def_base)
        base_data[StatType.EFFECT_HIT_RATE] = eh_base
        self.stats = EntityStats(base_data)
        self.stats.bind(self)

        super().__init__(n, int(self.stats.get_base_stat(StatType.HP)), int(self.stats.get_base_stat(StatType.SPD)))

        self.base_damage = base_damage if base_damage is not None else self._default_base_damage
        self.weaknesses: list[ElementType] = (
            weaknesses
            if weaknesses is not None
            else (self._default_weaknesses or [])
        )
        self.max_toughness = max_toughness if max_toughness is not None else self._default_max_toughness
        self.current_toughness = self.max_toughness
        self.broken: bool = False
        self.broken_by: Optional["ElementType"] = None
        self.broken_source_id: Optional[str] = None
        self.weightless_remaining_turns: int = 0
        self.weightless_hit_count: int = 0
        self.dot_statuses: list[DoTStatus] = []
        self.cc_statuses: list["CCStatus"] = []
        self.hit_energy_bucket: float = 10.0  # 受击回能分段 (§17.2)
        self.implanted_weakness: Optional[ImplantedWeakness] = None  # 弱点植入
        self.element_res_modifiers: dict[ElementType, float] = {}  # per-element RES 修改

    @classmethod
    def from_template(cls, enemy_id: str) -> "BaseEnemy":
        """创建 Enemy 实例：JSON 优先，不可用时回退到已注册子类。"""
        from starrail_combat import ElementType, get_data_loader

        try:
            data = get_data_loader().get_enemy_data(enemy_id)
        except KeyError:
            data = None

        if data is not None:
            weaknesses = [
                ElementType[w]
                for w in data.get("weaknesses", [])
                if w in ElementType.__members__
            ]
            return cls(
                name=enemy_id,
                hp=data["hp"],
                speed=data["speed"],
                base_damage=data["base_damage"],
                weaknesses=weaknesses,
                max_toughness=data.get("max_toughness", 0.0),
            )

        # JSON 不可用 → 已注册子类 -> 使用其类属性默认值
        if enemy_id in cls._enemy_registry:
            return cls._enemy_registry[enemy_id]()

        raise KeyError(f"Unknown enemy: {enemy_id}")

    def attack(self, targets: list["Character"], is_bounce: bool = False) -> tuple[str, int]:
        """按索敌规则选择目标造成固定伤害。"""
        from core.targeting import TargetManager

        target = TargetManager.select_target(self, targets, is_bounce=is_bounce)
        if target is None:
            return ("", 0)
        damage = target.take_damage(self.base_damage)
        return (target.name, damage)

    def apply_dot(self, dot: DoTStatus) -> None:
        """挂载 DoT：同来源同元素则叠加层数 + 刷新持续。"""
        for existing in self.dot_statuses:
            if existing.element == dot.element and existing.source_character is dot.source_character:
                existing.stacks += dot.stacks
                existing.duration = max(existing.duration, dot.duration)
                return
        self.dot_statuses.append(dot)

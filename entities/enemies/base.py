from __future__ import annotations
"""BaseEnemy — 敌方目标基类 (Config 驱动 + 类属性 fallback)。"""

from typing import Optional

from core.entity_stats import stats_defaults
from entities.base import DoTStatus, Fighter, CCStatus, ImplantedWeakness
from entities.enemies.enemy_skill import EnemySkill
from entities.enemies.enemy_ai import EnemyAI, SimpleAI


class BaseEnemy(Fighter):
    """敌方目标。支持两套初始化路径:

    1. Config 驱动 (推荐): 传 EnemyConfig, 从成长表读取属性
    2. 显式参数 (兼容旧代码): 传 name/hp/speed/base_damage 等

    子类可覆盖 _CONFIG 类属性达到零代码定义。
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
    _default_element: "ElementType | None" = None
    _default_crit_rate: float = 0.0
    _default_crit_dmg: float = 0.20
    _default_base_res: float = 0.20

    def __init__(
        self,
        name: str = "",
        hp: Optional[int] = None,
        speed: Optional[int] = None,
        base_damage: Optional[int] = None,
        weaknesses: Optional[list["ElementType"]] = None,
        max_toughness: Optional[float] = None,
        level: Optional[int] = None,
        *,
        config: Optional["EnemyConfig"] = None,
    ) -> None:
        from starrail_combat import ElementType, EntityStats, StatType

        n = name or self._default_name
        lv = level if level is not None else self._default_level

        self.level = lv

        if config is not None:
            self._init_from_config(config, lv, n)
        else:
            self._init_from_args(n, lv, hp, speed, base_damage, weaknesses, max_toughness)

        self.max_toughness = (
            max_toughness if max_toughness is not None
            else (config.max_toughness if config else self._default_max_toughness)
        )
        self.current_toughness = self.max_toughness
        self.broken: bool = False
        self.broken_by: Optional["ElementType"] = None
        self.broken_source_id: Optional[str] = None
        self.weightless_remaining_turns: int = 0
        self.weightless_hit_count: int = 0
        self.dot_statuses: list[DoTStatus] = []
        self.cc_statuses: list["CCStatus"] = []
        self.hit_energy_bucket: float = (
            config.hit_energy_bucket if config else 10.0
        )
        self.implanted_weakness: Optional[ImplantedWeakness] = None
        self.element_res_modifiers: dict[ElementType, float] = {}
        self.damage_type_resistance: dict[str, float] = (
            config.damage_type_resistance if config else {}
        )
        self.marked_targets: list["Character"] = []
        self.deathrattle: dict | None = (
            config.deathrattle if config else None
        )
        self._config = config

        from core.enums import StatType as ST
        spd_final = int(self.stats.get_total_stat(ST.SPD))
        hp_final = int(self.stats.get_total_stat(ST.HP))
        super().__init__(n, hp_final, spd_final)

        _init_old = not config
        if _init_old:
            self.base_damage = base_damage if base_damage is not None else self._default_base_damage
            self._element = self._default_element
        self.weaknesses: list[ElementType] = (
            weaknesses if weaknesses is not None
            else (config.weaknesses if config else (self._default_weaknesses or []))
        )
        if config:
            self._element = config.element

    def _init_from_config(self, config: "EnemyConfig", lv: int, name: str) -> None:
        from starrail_combat import ElementType, EntityStats, StatType
        from entities.enemies.enemy_skill import EnemySkill as ES

        stats = self._resolve_level_stats(config, lv)

        base_data = stats_defaults()
        base_data[StatType.HP] = float(stats["hp"])
        base_data[StatType.ATK] = float(stats["atk"])
        base_data[StatType.DEF] = float(stats["def"])
        base_data[StatType.SPD] = float(stats["spd"])
        base_data[StatType.EFFECT_HIT_RATE] = float(stats.get("ehr", 0.0))
        base_data[StatType.EFFECT_RES] = float(stats.get("eres", 0.0))
        base_data[StatType.CRIT_RATE] = config.crit_rate
        base_data[StatType.CRIT_DMG] = config.crit_dmg
        self.stats = EntityStats(base_data)
        self.stats.bind(self)

        self._skills: dict[str, EnemySkill] = {s.skill_id: s for s in config.skills}
        self._ai: EnemyAI = config.ai

        # 存储 config 引用以便延迟初始化被动效果
        self._config = config

        fallback = next(iter(self._skills.values()), None)
        if fallback is None:
            fallback = ES(
                skill_id="default_attack", name="攻击",
                multiplier=1.0, element=config.element or ElementType.PHYSICAL,
                targeting="single",
            )
        self._default_skill: EnemySkill = fallback

        self._energy: float = 0.0
        self._max_energy: float = config.max_energy if config.max_energy is not None else 0.0

        self.base_damage = int(stats["atk"])

    def _apply_passive_effects_from_skills(self) -> None:
        """延迟初始化被动技能效果（CombatEngine 注入 event_bus 后调用）。"""
        config = self._config
        if config is None:
            return
        from entities.base import StatModifier
        from entities.enemies.enemy_skill import BuffEffect
        from entities.enemies.enemy_ai import SequenceAI, PriorityAI
        ai_sequence: set[str] = set()
        if isinstance(config.ai, SequenceAI):
            ai_sequence = set(config.ai._sequence)
        elif isinstance(config.ai, PriorityAI):
            ai_sequence = {r.skill_id for r in config.ai._rules}
        for skill in config.skills:
            if skill.multiplier != 0:
                continue
            if skill.skill_id in ai_sequence:
                continue
            for eff in skill.effects:
                if isinstance(eff, BuffEffect):
                    mod = StatModifier(
                        stat_type=eff.stat_type,
                        modifier_type=eff.modifier_type,
                        value=eff.value,
                        source=f"{config.name}_passive",
                        duration=eff.duration,
                    )
                    self.stats.apply_modifier(mod, "refresh")

    def _init_from_args(self, name: str, lv: int, hp, speed, base_damage, weaknesses, max_toughness) -> None:
        from starrail_combat import ElementType, EntityStats, StatType

        hp_val = hp if hp is not None else self._default_hp
        spd_val = speed if speed is not None else self._default_speed

        eh_base = 0.0
        if lv > 50:
            eh_base = min((lv - 50) * 0.008, 0.40)
        if lv >= 120:
            eh_base += 0.10

        scale = 1.0
        for (lo, hi), s in self._SPD_SCALING:
            if lo <= lv <= hi:
                scale = s
                break
        spd_val = int(spd_val * scale)
        def_base = lv * 10 + 200
        base_data = stats_defaults()
        base_data[StatType.HP] = float(hp_val)
        base_data[StatType.ATK] = float(base_damage if base_damage is not None else self._default_base_damage)
        base_data[StatType.SPD] = float(spd_val)
        base_data[StatType.DEF] = float(def_base)
        base_data[StatType.EFFECT_HIT_RATE] = eh_base
        base_data[StatType.CRIT_RATE] = self._default_crit_rate
        base_data[StatType.CRIT_DMG] = self._default_crit_dmg
        self.stats = EntityStats(base_data)
        self.stats.bind(self)

        self._skills: dict[str, EnemySkill] = {}
        self._ai: Optional[EnemyAI] = None
        self._default_skill: EnemySkill = EnemySkill(
            skill_id="default_attack", name="攻击",
            multiplier=1.0, element=ElementType.PHYSICAL,
            targeting="single",
        )
        self._energy: float = 0.0
        self._max_energy: float = 0.0

    @staticmethod
    def _resolve_level_stats(config: "EnemyConfig", level: int) -> dict:
        table = config.level_stats
        if level in table:
            return table[level]
        keys = sorted(table.keys())
        if not keys:
            return {"hp": 300, "atk": 25, "def": 200, "spd": 90, "ehr": 0.0, "eres": 0.0}
        if level <= keys[0]:
            return table[keys[0]]
        if level >= keys[-1]:
            return table[keys[-1]]
        for i in range(len(keys) - 1):
            lo, hi = keys[i], keys[i + 1]
            if lo <= level <= hi:
                lo_data = table[lo]
                hi_data = table[hi]
                ratio = (level - lo) / (hi - lo)
                return {
                    k: lo_data[k] + (hi_data[k] - lo_data[k]) * ratio
                    for k in lo_data if k in hi_data
                }
        return table[keys[-1]]

    # ── 属性代理 ──

    @property
    def element(self) -> Optional["ElementType"]:
        return getattr(self, "_element", None)

    @element.setter
    def element(self, value: Optional["ElementType"]) -> None:
        self._element = value

    @property
    def atk(self) -> float:
        from core.enums import StatType
        return self.stats.get_total_stat(StatType.ATK)

    @property
    def crit_rate(self) -> float:
        from core.enums import StatType
        return self.stats.get_total_stat(StatType.CRIT_RATE)

    @property
    def crit_dmg(self) -> float:
        from core.enums import StatType
        return self.stats.get_total_stat(StatType.CRIT_DMG)

    @property
    def energy(self) -> float:
        return self._energy

    @property
    def max_energy(self) -> float:
        return self._max_energy

    # ── 技能与 AI ──

    def decide_skill(self, state: "GameState") -> "EnemySkill":
        if self._ai is not None:
            return self._ai.select_skill(self, state)
        return self._default_skill

    def gain_energy(self, amount: float) -> float:
        if self._max_energy <= 0:
            return 0.0
        capped = max(0.0, min(amount, self._max_energy - self._energy))
        self._energy += capped
        return capped

    def consume_energy(self, amount: float) -> None:
        self._energy = max(0.0, self._energy - amount)

    def after_action(self, skill: "EnemySkill") -> None:
        skill.start_cooldown()
        self.gain_energy(skill.energy_gain)

    def on_turn_start(self) -> None:
        for s in self._skills.values():
            s.tick_cooldown()

    # ── 工厂方法 ──

    @classmethod
    def from_template(cls, enemy_id: str) -> "BaseEnemy":
        from starrail_combat import ElementType, get_data_loader

        try:
            data = get_data_loader().get_enemy_data(enemy_id)
        except KeyError:
            data = None

        if data is not None:
            weaknesses = [
                ElementType[w.upper()]
                for w in data.get("weaknesses", [])
                if w.upper() in ElementType.__members__
            ]
            return cls(
                name=enemy_id,
                hp=data["hp"],
                speed=data["speed"],
                base_damage=data["base_damage"],
                weaknesses=weaknesses,
                max_toughness=data.get("max_toughness", 0.0),
            )

        if enemy_id in cls._enemy_registry:
            return cls._enemy_registry[enemy_id]()

        raise KeyError(f"Unknown enemy: {enemy_id}")

    # ── 旧攻击接口 (兼容) ──

    def attack(self, targets: list["Character"], is_bounce: bool = False) -> tuple[str, int]:
        from core.targeting import TargetManager

        target = TargetManager.select_target(self, targets, is_bounce=is_bounce)
        if target is None:
            return ("", 0)
        damage = target.take_damage(self.base_damage)
        return (target.name, damage)

    # ── DoT ──

    def apply_dot(self, dot: DoTStatus) -> None:
        for existing in self.dot_statuses:
            if existing.element == dot.element and existing.source_character is dot.source_character:
                existing.stacks += dot.stacks
                existing.duration = max(existing.duration, dot.duration)
                return
        self.dot_statuses.append(dot)

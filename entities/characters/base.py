from __future__ import annotations
"""BaseCharacter — 己方角色基类 (JSON 优先，类属性 fallback)。"""

from typing import Optional

from entities.base import Fighter


class BaseCharacter(Fighter):
    """己方角色，属性面板由 EntityStats 组件管理。

    子类可覆盖类属性设置默认值；实例化时 JSON 优先于类属性，
    JSON 不可用时回退到子类的 _base_stats 类属性。
    """

    _default_id: str = ""
    _default_level: int = 80
    _base_stats: dict["StatType", float] = {}
    _default_element: "ElementType" = None
    _default_path: "PathType" = None
    # 角色级削韧/回能覆盖: 空 dict = 使用全局 config
    _toughness_map: dict["ActionType", float] = {}
    _energy_map: dict["ActionType", float] = {}

    # 子类注册表：_default_id → 子类
    _character_registry: dict[str, type["BaseCharacter"]] = {}

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        if cls._default_id:
            BaseCharacter._character_registry[cls._default_id] = cls

    def __new__(cls, character_id: str = "", **kwargs: object) -> "BaseCharacter":
        if cls is not BaseCharacter:
            return super().__new__(cls)
        if character_id and character_id in cls._character_registry:
            sub_cls = cls._character_registry[character_id]
            return sub_cls.__new__(sub_cls)
        return super().__new__(cls)

    def __init__(
        self,
        character_id: str = "",
        level: Optional[int] = None,
        *,
        _stats_override: Optional[dict["StatType", float]] = None,
        _element_override: "ElementType" = None,
        _path_override: "PathType" = None,
    ) -> None:
        from starrail_combat import (
            ElementType,
            EntityStats,
            PathType,
            StatType,
            get_data_loader,
        )

        cid = character_id or self._default_id
        lv = level if level is not None else self._default_level

        # 优先从 JSON 读取
        if _stats_override is not None:
            stat_dict = dict(_stats_override)
            self.element = _element_override or ElementType.PHYSICAL
            self.path = _path_override or PathType.HUNT
        else:
            try:
                loader = get_data_loader()
                char_data = loader.get_character_data(cid)
                self.element = ElementType[char_data["element"]]
                self.path = PathType[char_data["path"]]
                stat_dict = {StatType[k]: v for k, v in char_data["stats"].items()}
            except (KeyError, RuntimeError):
                # JSON 不可用 → 类属性 fallback
                if not self._base_stats:
                    raise KeyError(f"Unknown character: {cid} (no JSON or class defaults)")
                self.element = self._default_element or ElementType.PHYSICAL
                self.path = self._default_path or PathType.HUNT
                stat_dict = dict(self._base_stats)

        # 允许 _path_override / _element_override 覆盖来源
        if _path_override is not None:
            self.path = _path_override
        if _element_override is not None:
            self.element = _element_override

        self.character_id = cid
        self.level = lv
        self.stats = EntityStats(stat_dict)

        hp = int(self.stats.get_base_stat(StatType.HP))
        speed = int(self.stats.get_base_stat(StatType.SPD))
        super().__init__(cid, hp, speed)

        self.energy: int = 0
        self.light_cone: Optional["LightCone"] = None
        self.relics: dict["RelicPart", "Relic"] = {}
        self.stats.bind(self)
        # 技能/行迹/星魂
        self._traces: list = []
        self._eidolons: list = []
        self._skills: dict[str, object] = {}
        # 能量系统标记
        self.uses_energy: bool = True
        self.can_half_cast_ult: bool = False
        # 忆灵
        self.memosprite: Optional["Memosprite"] = None

    # -- 行迹/星魂管理 --

    def add_trace_modifiers(self, trace: object) -> None:
        """将行迹修饰器挂载到角色面板。子类覆写。"""
        pass

    def add_eidolon_modifiers(self, eidolon: object) -> None:
        """将星魂修饰器挂载到角色面板。子类覆写。"""
        pass

    def decide_skill(self, state: "GameState") -> object:
        """根据当前 SP/能量选择技能。返回技能对象。"""
        ultimate = self._skills.get("ultimate")
        if ultimate and self.is_ultimate_ready:
            return ultimate
        if state is not None and state.skill_points > 0:
            return self._skills.get("skill")
        return self._skills.get("basic")

    # -- 忆灵管理 --

    def summon_memosprite(self, speed: int, hp_scale: float = 1.0) -> "Memosprite":
        """召唤忆灵 (已存在则返回现有)。"""
        if self.memosprite is not None:
            return self.memosprite
        from entities.base import Memosprite
        self.memosprite = Memosprite(f"{self.name}_Sprite", self, speed, hp_scale)
        return self.memosprite

    def dismiss_memosprite(self) -> None:
        """解除忆灵。"""
        self.memosprite = None

    # -- 属性代理 (绿值) --

    @property
    def atk(self) -> float:
        return self.stats.get_total_stat(_get_stat_type("ATK"))

    @property
    def crit_rate(self) -> float:
        return self.stats.get_total_stat(_get_stat_type("CRIT_RATE"))

    @property
    def crit_dmg(self) -> float:
        return self.stats.get_total_stat(_get_stat_type("CRIT_DMG"))

    @property
    def max_energy(self) -> int:
        return int(self.stats.get_total_stat(_get_stat_type("MAX_ENERGY")))

    # -- 装备操作 --

    def equip_light_cone(self, lc: "LightCone") -> None:
        if self.light_cone is lc:
            return
        if self.light_cone is not None:
            old = self.light_cone
            if old.effect is not None:
                old.effect.on_unequip(self)
            self.stats.purge_source(f"LightCone_{old.id}")
        self.light_cone = lc

        lc._init_path_key_map()
        lc_path = lc.path
        if lc_path is not None and lc_path != self.path:
            print(f"  [提示] {self.name} 命途({self.path.name})与{lc.name}不匹配，光锥特效未激活")
        elif lc.effect is not None:
            lc.effect.on_equip(self)

        self._recalc_max_hp()

    def equip_relic(self, relic: "Relic") -> None:
        if relic.part in self.relics:
            old = self.relics[relic.part]
            for mod in [old.main_stat] + old.sub_stats:
                self.stats.remove_modifier(mod)

        source = f"Relic_{relic.part.name}"
        for mod in [relic.main_stat] + relic.sub_stats:
            mod.source = source
            self.stats.add_modifier(mod)

        self.relics[relic.part] = relic
        from entities.relics.base import check_and_apply_set_effects
        check_and_apply_set_effects(self)
        self._recalc_max_hp()

    def _recalc_max_hp(self) -> None:
        new_max = int(self.stats.get_total_stat(_get_stat_type("HP")))
        self.max_hp = new_max
        self.hp = min(self.hp, self.max_hp)

    # -- 能量管理 --

    def gain_energy(self, amount: float, affected_by_err: bool = True) -> float:
        """增加能量 (受限 cap + ERR 影响)。返回实际增加值。"""
        if not self.uses_energy:
            return 0.0
        if affected_by_err:
            from core.enums import StatType
            err = self.stats.get_total_stat(StatType.ERR)
            amount = amount * err
        capped = int(max(0, min(amount, self.max_energy - self.energy)))
        self.energy = int(self.energy + capped)
        return capped

    def set_energy(self, value: int) -> None:
        """直接设置能量值 (大招清空等)。不受 ERR 影响。"""
        self.energy = max(0, min(value, self.max_energy))

    @property
    def is_ultimate_ready(self) -> bool:
        """终结技可用状态: 非能体系→False, 半能→>=50%, 常规→>=100%。"""
        if not self.uses_energy:
            return False
        if self.can_half_cast_ult:
            return self.energy >= self.max_energy / 2
        return self.energy >= self.max_energy


def _get_stat_type(name: str) -> "StatType":
    from starrail_combat import StatType
    return StatType[name]

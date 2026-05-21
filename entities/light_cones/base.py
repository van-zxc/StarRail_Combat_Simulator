"""BaseLightCone — 光锥基类。"""

from __future__ import annotations

from typing import Optional


class BaseLightCone:
    id: str = ""
    name: str = ""
    base_hp: float = 0.0
    base_atk: float = 0.0
    base_def: float = 0.0
    superimpose: int = 1
    level: int = 80
    path_key: str = ""
    effect: Optional["EquipmentEffect"] = None

    _default_id: str = ""
    _default_name: str = ""
    _default_base_hp: float = 0.0
    _default_base_atk: float = 0.0
    _default_base_def: float = 0.0
    _default_superimpose: int = 1
    _default_level: int = 80
    _default_path_key: str = ""

    _BREAKPOINTS: tuple[int, ...] = (1, 20, 30, 40, 50, 60, 70, 80)
    _PROMOTIONS: list[dict[str, float]] = []

    _light_cone_registry: dict[str, type["BaseLightCone"]] = {}

    _PATH_KEY_TO_ENUM: dict[str, "PathType"] = {}

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        if cls._default_id:
            BaseLightCone._light_cone_registry[cls._default_id] = cls

    def __new__(cls, id: str = "", **kwargs: object) -> "BaseLightCone":
        if cls is not BaseLightCone:
            return super().__new__(cls)
        if id and id in cls._light_cone_registry:
            sub_cls = cls._light_cone_registry[id]
            return sub_cls.__new__(sub_cls)
        return super().__new__(cls)

    def __init__(
        self,
        id: str = "",
        name: str = "",
        base_hp: Optional[float] = None,
        base_atk: Optional[float] = None,
        base_def: Optional[float] = None,
        superimpose: Optional[int] = None,
        level: Optional[int] = None,
        path_key: Optional[str] = None,
        effect: Optional["EquipmentEffect"] = None,
    ) -> None:
        self.id = id or self._default_id
        self.name = name or self._default_name
        self.base_hp = base_hp if base_hp is not None else self._default_base_hp
        self.base_atk = base_atk if base_atk is not None else self._default_base_atk
        self.base_def = base_def if base_def is not None else self._default_base_def
        self.superimpose = superimpose if superimpose is not None else self._default_superimpose
        self.level = level if level is not None else self._default_level
        self.path_key = path_key if path_key is not None else self._default_path_key
        self.effect = effect

        if self._PROMOTIONS:
            self._recalc_stats()

    def _recalc_stats(self) -> None:
        self.base_hp = self._calc_stat("hp", self.level)
        self.base_atk = self._calc_stat("atk", self.level)
        self.base_def = self._calc_stat("def", self.level)

    @classmethod
    def _calc_stat(cls, key: str, level: int) -> float:
        """分段线性插值计算指定等级的面板值。"""
        proms = cls._PROMOTIONS
        bps = cls._BREAKPOINTS
        N = len(bps) - 1
        level = max(1, min(level, bps[-1]))

        for i in range(N):
            if bps[i] <= level < bps[i + 1]:
                v_low = proms[i][f"{key}_base"]
                if i + 1 < N:
                    v_high = proms[i + 1][f"{key}_base"]
                else:
                    v_high = proms[N - 1][f"{key}_base"] + proms[N - 1][f"{key}_step"] * 10
                t = (level - bps[i]) / (bps[i + 1] - bps[i])
                return v_low + (v_high - v_low) * t

        return proms[N - 1][f"{key}_base"] + proms[N - 1][f"{key}_step"] * 10

    @property
    def path(self):
        return self._PATH_KEY_TO_ENUM.get(self.path_key) if self.path_key else None

    @staticmethod
    def _init_path_key_map() -> None:
        if BaseLightCone._PATH_KEY_TO_ENUM:
            return
        from core.enums import PathType
        BaseLightCone._PATH_KEY_TO_ENUM = {
            "Warrior": PathType.DESTRUCTION,
            "Rogue": PathType.HUNT,
            "Mage": PathType.ERUDITION,
            "Shaman": PathType.HARMONY,
            "Warlock": PathType.NIHILITY,
            "Knight": PathType.PRESERVATION,
            "Priest": PathType.ABUNDANCE,
            "Memory": PathType.REMEMBRANCE,
        }

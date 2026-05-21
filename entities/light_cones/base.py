"""BaseLightCone — 光锥基类。"""

from __future__ import annotations

from typing import Optional


class BaseLightCone:
    id: str = ""
    name: str = ""
    base_hp: float = 0.0
    base_atk: float = 0.0
    base_def: float = 0.0
    effect: Optional["EquipmentEffect"] = None

    _default_id: str = ""
    _default_name: str = ""
    _default_base_hp: float = 0.0
    _default_base_atk: float = 0.0
    _default_base_def: float = 0.0

    _light_cone_registry: dict[str, type["BaseLightCone"]] = {}

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
        effect: Optional["EquipmentEffect"] = None,
    ) -> None:
        self.id = id or self._default_id
        self.name = name or self._default_name
        self.base_hp = base_hp if base_hp is not None else self._default_base_hp
        self.base_atk = base_atk if base_atk is not None else self._default_base_atk
        self.base_def = base_def if base_def is not None else self._default_base_def
        self.effect = effect

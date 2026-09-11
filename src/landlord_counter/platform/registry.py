"""适配器注册表: 按名字取适配器(Runtime 只需 name)。"""
from __future__ import annotations

from typing import Callable

_REGISTRY: dict[str, Callable[[], object]] = {}


def register(name: str, factory: Callable[[], object]) -> None:
    _REGISTRY[name] = factory


def create(name: str):
    if name not in _REGISTRY:
        raise KeyError(f"未注册的适配器: {name} (已注册: {sorted(_REGISTRY)})")
    return _REGISTRY[name]()


def names() -> list[str]:
    return sorted(_REGISTRY)


def _load_builtin() -> None:
    from .games.ddz_adapter import DoudizhuAdapter
    from .games.guandan_adapter import GuandanAdapter
    from .games.mahjong_adapter import MahjongAdapter

    register("guandan", GuandanAdapter)
    register("doudizhu", DoudizhuAdapter)
    register("mahjong", MahjongAdapter)   # 进行中, 未通过真机验收


_load_builtin()

"""
异步工具函数

提供在异步上下文中安全执行同步函数的工具，避免阻塞事件循环。
"""

from __future__ import annotations

import asyncio
from functools import partial, wraps
from typing import Any, Callable, Coroutine, TypeVar

T = TypeVar("T")


async def run_in_executor(func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """
    在线程池中运行同步函数，避免阻塞事件循环。

    用法:
        result = await run_in_executor(some_sync_function, arg1, arg2)
    """
    loop = asyncio.get_running_loop()
    bound = partial(func, *args, **kwargs)
    return await loop.run_in_executor(None, bound)


def async_wrap_sync(func: Callable[..., T]) -> Callable[..., Coroutine[Any, Any, T]]:
    """
    装饰器：将同步函数包装成异步函数（在线程池中执行）。

    用法:
        @async_wrap_sync
        def do_sync(...): ...

        result = await do_sync(...)
    """

    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> T:
        return await run_in_executor(func, *args, **kwargs)

    return wrapper


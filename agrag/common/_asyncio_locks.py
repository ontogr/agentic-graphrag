"""Loop-scoped async locks shared by internal callers."""

import asyncio
from collections.abc import Hashable
from threading import Lock
from weakref import WeakKeyDictionary, WeakValueDictionary


_LoopLockRegistry = WeakKeyDictionary[
    asyncio.AbstractEventLoop,
    WeakValueDictionary[Hashable, asyncio.Lock],
]
# Different event loops can use these registries from different threads.
_registry_lock = Lock()


def _get_loop_lock(registry: _LoopLockRegistry, key: Hashable) -> asyncio.Lock:
    """Return the shared lock for a key on the running event loop."""
    loop = asyncio.get_running_loop()
    with _registry_lock:
        locks = registry.get(loop)
        if locks is None:
            locks = WeakValueDictionary()
            registry[loop] = locks
        lock = locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            locks[key] = lock
        return lock

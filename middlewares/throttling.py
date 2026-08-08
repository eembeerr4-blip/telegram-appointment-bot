import asyncio
import time
from collections import OrderedDict

from aiogram.dispatcher.middlewares.base import BaseMiddleware


class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self, min_interval: float = 0.8) -> None:
        super().__init__()
        self.min_interval = min_interval
        self._last_action: dict[int, float] = {}
        self._lock = asyncio.Lock()

    async def __call__(self, handler, event, data):
        user_id = None
        if getattr(getattr(event, "from_user", None), "id", None) is not None:
            user_id = event.from_user.id
        elif getattr(getattr(event, "chat", None), "id", None) is not None:
            user_id = event.chat.id

        if user_id is None:
            return await handler(event, data)

        now = time.monotonic()
        async with self._lock:
            previous = self._last_action.get(user_id)
            if previous is not None and now - previous < self.min_interval:
                return None
            self._last_action[user_id] = now

        return await handler(event, data)


class UpdateDedupMiddleware(BaseMiddleware):
    def __init__(self, max_entries: int = 5000) -> None:
        super().__init__()
        self.max_entries = max_entries
        self._processed_updates: OrderedDict[int, None] = OrderedDict()
        self._lock = asyncio.Lock()

    async def __call__(self, handler, event, data):
        update_id = getattr(event, "update_id", None)
        if update_id is None:
            return await handler(event, data)

        async with self._lock:
            if update_id in self._processed_updates:
                return None
            self._processed_updates[update_id] = None
            if len(self._processed_updates) > self.max_entries:
                self._processed_updates.popitem(last=False)

        return await handler(event, data)

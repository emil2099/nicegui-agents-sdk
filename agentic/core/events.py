# events.py

from __future__ import annotations
from typing import Any, Callable, List, Optional, Dict, Awaitable
from pydantic import BaseModel, Field
from datetime import datetime, timezone
import asyncio, inspect

class AgentEvent(BaseModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    event_type: str
    event_name: Optional[str] = None
    source: str
    span_id: Optional[str] = None
    data: Dict[str, Any] = Field(default_factory=dict)

# Define the subscriber as an async callable
EventSubscriber = Callable[[AgentEvent], Awaitable[None]]

class EventPublisher:
    def __init__(self, subscribers: Optional[List[EventSubscriber]] = None):
        self._subscribers = subscribers or []

    # Make this method async
    async def publish_event(self, event: AgentEvent):
        tasks = []
        for subscriber in self._subscribers:
            try:
                if inspect.iscoroutinefunction(subscriber):
                    tasks.append(asyncio.create_task(subscriber(event)))
                else:
                    # run sync subscribers immediately
                    subscriber(event)
            except Exception as e:

                raise
        if tasks:
            await asyncio.gather(*tasks)

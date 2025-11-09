# events.py

from __future__ import annotations
from typing import Any, Callable, List, Optional, Dict, Awaitable
from pydantic import BaseModel, Field
import asyncio, inspect

class AgentEvent(BaseModel):
    event_type: str
    event_name: Optional[str] = None
    source: str
    data: Dict[str, Any] = Field(default_factory=dict)

# Define the subscriber as an async callable
EventSubscriber = Callable[[AgentEvent], Awaitable[None]]

class EventPublisher:
    def __init__(self, subscribers: Optional[List[EventSubscriber]] = None):
        self._subscribers = subscribers or []

    # Make this method async
    async def publish_event(self, event: AgentEvent):
        tasks = []
        print(event)
        for subscriber in self._subscribers:
            try:
                if inspect.iscoroutinefunction(subscriber):
                    tasks.append(asyncio.create_task(subscriber(event)))
                else:
                    # run sync subscribers immediately
                    subscriber(event)
            except Exception as e:
                print(f"[EventPublisher Error] Failed to create task for {getattr(subscriber, '__name__', str(subscriber))}: {e}")
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
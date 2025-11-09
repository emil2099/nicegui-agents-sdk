from __future__ import annotations

from typing import Any, Callable, List, Optional, Dict
from pydantic import BaseModel, Field

from agents.stream_events import (
    StreamEvent,
    AgentUpdatedStreamEvent,
    RunItemStreamEvent,
)
from agents.items import ToolCallItem, ToolCallOutputItem

class AgentEvent(BaseModel):
    """A lightweight, UI-agnostic event object that mirrors SDK event names."""
    event_type: str
    event_name: Optional[str] = None
    source: str
    data: Dict[str, Any] = Field(default_factory=dict)

# 2. THE SUBSCRIBER INTERFACE
# This is what our "listeners" (like the terminal logger) will be.
EventSubscriber = Callable[[AgentEvent], None]

class EventPublisher:
    def __init__(self, subscribers: Optional[List[EventSubscriber]] = None):
        """
        Initializes the publisher with a list of subscribers.
        Subscribers are simple functions that accept an AgentEvent.
        """
        self._subscribers = subscribers or []

    def _publish(self, event: AgentEvent):
        """Private method to send the event to all subscribers."""
        for subscriber in self._subscribers:
            try:
                subscriber(event)
            except Exception as e:
                # Don't let a bad subscriber stop the presses
                print(f"[EventPublisher Error] Subscriber {subscriber.__name__} failed: {e}")

    def _process_openai_agents_event(self, raw_event: StreamEvent) -> Optional[AgentEvent]:
        """
        THE CORE TRANSLATION LOGIC.
        Translates raw, heavy SDK events into our lightweight AgentEvent.
        Returns None if we want to filter the event out.
        """
        
        # This is the "adapter" logic you requested.
        
        if isinstance(raw_event, AgentUpdatedStreamEvent):
            return AgentEvent(
                event_type=raw_event.type, # Pass through: 'agent_updated_stream_event'
                source=raw_event.new_agent.name,
                data={"new_agent_name": raw_event.new_agent.name}
            )

        if isinstance(raw_event, RunItemStreamEvent):
            item = raw_event.item
            agent_name = item.agent.name
            
            if item.type == "tool_call_item" and isinstance(item, ToolCallItem):
                return AgentEvent(
                    event_type=raw_event.type, # Pass through: 'run_item_stream_event'
                    event_name=raw_event.name, # Pass through: 'tool_called'
                    source=agent_name,
                    data={
                        "tool_name": item.tool_name,
                        "tool_args": item.tool_arguments
                    }
                )
            
            if item.type == "tool_call_output_item" and isinstance(item, ToolCallOutputItem):
                return AgentEvent(
                    event_type=raw_event.type, # Pass through: 'run_item_stream_event'
                    event_name=raw_event.name, # Pass through: 'tool_output'
                    source=agent_name,
                    data={"output": item.output}
                )
        
        # We can add more translations here later (e.g., for 'message_output_created')
        # We filter out other events (like RawResponsesStreamEvent) by default.
        return None

    def publish_openai_agents_event(self, raw_event: StreamEvent):
        # This is the *only* method agent_service.py will call.
        our_event = self._process_openai_agents_event(raw_event)
        if our_event:
            self._publish(our_event)
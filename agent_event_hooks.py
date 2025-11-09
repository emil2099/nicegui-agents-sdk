"""Agent lifecycle hooks that publish events to the UI event bus."""

from __future__ import annotations

from typing import Any, Optional

from agents import Agent, AgentHooks, ModelResponse, RunContextWrapper, Tool, TResponseInputItem

from events import AgentEvent, EventPublisher


class EventPublishingHook(AgentHooks):
    """Broadcasts every lifecycle callback to the shared EventPublisher."""

    @staticmethod
    def _get_publisher(context: RunContextWrapper) -> Optional[EventPublisher]:
        ctx = getattr(context, "context", None)
        if isinstance(ctx, dict):
            pub = ctx.get("event_publisher")
            return pub if isinstance(pub, EventPublisher) else None
        return None

    async def _emit(
        self,
        context_wrapper: RunContextWrapper,
        source: str,
        event_type: str,
        **data: Any,
    ) -> None:
        publisher = self._get_publisher(context_wrapper)
        if publisher:
            await publisher.publish_event(
                AgentEvent(event_type=event_type, source=source, data=data)
            )

    async def on_start(self, context: RunContextWrapper, agent: Agent) -> None:
        await self._emit(
            context,
            agent.name,
            "agent_started_stream_event",
            agent=agent,
        )

    async def on_end(self, context: RunContextWrapper, agent: Agent, output: Any) -> None:
        await self._emit(
            context,
            agent.name,
            "agent_ended_stream_event",
            agent=agent,
            output=output,
        )

    async def on_handoff(self, context: RunContextWrapper, agent: Agent, source: Agent) -> None:
        await self._emit(
            context,
            source.name,
            "agent_handoff_stream_event",
            from_agent=source,
            to_agent=agent,
        )

    async def on_tool_start(self, context: RunContextWrapper, agent: Agent, tool: Tool) -> None:
        await self._emit(
            context,
            agent.name,
            "tool_started_stream_event",
            agent=agent,
            tool=tool,
        )

    async def on_tool_end(self, context: RunContextWrapper, agent: Agent, tool: Tool, result: str) -> None:
        await self._emit(
            context,
            agent.name,
            "tool_ended_stream_event",
            agent=agent,
            tool=tool,
            result=result,
        )

    async def on_llm_end(
        self,
        context: RunContextWrapper,
        agent: Agent,
        response: ModelResponse,
    ) -> None:
        await self._emit(
            context,
            agent.name,
            "llm_ended_stream_event",
            agent=agent,
            response=response,
        )

    async def on_llm_start(
        self,
        context: RunContextWrapper,
        agent: Agent,
        system_prompt: Optional[str],
        input_items: list[TResponseInputItem],
    ) -> None:
        await self._emit(
            context,
            agent.name,
            "llm_started_stream_event",
            agent=agent,
            system_prompt=system_prompt,
            input_items=input_items,
        )

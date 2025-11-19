"""Agent lifecycle hooks that publish events to the UI event bus."""

from __future__ import annotations

from typing import Any, Optional

from agents import Agent, AgentHooks, ModelResponse, RunContextWrapper, Tool, TResponseInputItem

from events import AgentEvent, EventPublisher
from agents.tracing import get_current_span


def get_event_publisher(context_wrapper: RunContextWrapper) -> Optional[EventPublisher]:
    ctx = getattr(context_wrapper, "context", None)
    if isinstance(ctx, dict):
        pub = ctx.get("event_publisher")
        return pub if isinstance(pub, EventPublisher) else None
    return None


async def emit_agent_event(
    context_wrapper: RunContextWrapper,
    source: str,
    event_type: str,
    **data: Any,
) -> None:
    publisher = get_event_publisher(context_wrapper)
    span = get_current_span()
    span_id = span.span_id if span else None
    
    if publisher:
        await publisher.publish_event(
            AgentEvent(event_type=event_type, source=source, span_id=span_id, data=data)
        )


class EventPublishingHook(AgentHooks):
    """Broadcasts every lifecycle callback to the shared EventPublisher."""

    async def _emit(
        self,
        context_wrapper: RunContextWrapper,
        source: str,
        event_type: str,
        **data: Any,
    ) -> None:
        await emit_agent_event(context_wrapper, source, event_type, **data)

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
        # Inspect output for hosted tool calls and emit specific events
        if hasattr(response, 'output'):
            # First, collect all annotations from any message items
            # These likely contain the citations for the web searches in this turn
            citations = []
            seen_urls = set()
            
            for item in response.output:
                if hasattr(item, 'type') and item.type == 'message':
                    for content_part in item.content:
                        if hasattr(content_part, 'annotations'):
                            for annotation in content_part.annotations:
                                if hasattr(annotation, 'type') and annotation.type == 'url_citation':
                                    # Deduplicate by URL
                                    if annotation.url not in seen_urls:
                                        citations.append(annotation)
                                        seen_urls.add(annotation.url)

            # Now emit events, attaching citations to web_search calls
            for item in response.output:
                if hasattr(item, 'type'):
                    if item.type == 'web_search_call':
                        # Use citations found in the response as sources
                        # If item.action.sources is None (which it usually is), use the collected citations
                        sources = getattr(item.action, 'sources', None) or citations
                        
                        await self._emit(
                            context,
                            agent.name,
                            "tool_web_search_event",
                            query=item.action.query,
                            sources=sources,
                            tool_call_id=item.id
                        )
                    elif item.type == 'code_interpreter_call':
                        print(f"[\033[94mCodeInterpreter\033[0m] Found code_interpreter_call in on_llm_end")
                        print(f"  Code: {item.code[:50] if item.code else 'None'}...")
                        print(f"  Outputs: {item.outputs}")
                        
                        await self._emit(
                            context,
                            agent.name,
                            "tool_code_interpreter_event",
                            code=item.code,
                            outputs=item.outputs,
                            tool_call_id=item.id
                        )
                    elif item.type == 'function_call':
                        await self._emit(
                            context,
                            agent.name,
                            "tool_call_detected_event",
                            tool_name=item.name,
                            arguments=item.arguments,
                            tool_call_id=item.id
                        )

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

from typing import AsyncIterator, Optional, Dict, Any
from agents import Agent, Runner
from agents.stream_events import AgentUpdatedStreamEvent, RawResponsesStreamEvent
from openai.types.responses.response_text_delta_event import ResponseTextDeltaEvent
from agentic.core.events import EventPublisher

async def stream_agent_output(
    agent: Agent, 
    prompt: str, 
    event_publisher: Optional[EventPublisher] = None
) -> AsyncIterator[str]:
    
    context: Optional[Dict[str, Any]] = None
    
    if event_publisher:
        context = {"event_publisher": event_publisher}
    
    result = Runner.run_streamed(
        agent, 
        prompt,
        context=context
    )

    yielded = False
    active_agent_name = agent.name
    
    async for event in result.stream_events():
        
        if isinstance(event, AgentUpdatedStreamEvent):
            active_agent_name = event.new_agent.name
            continue

        if isinstance(event, RawResponsesStreamEvent):
            if active_agent_name != agent.name:
                continue
            data = event.data
            if isinstance(data, ResponseTextDeltaEvent):
                chunk = data.delta or ""
                if chunk:
                    yielded = True
                    yield chunk

    if not yielded:
        final_output = result.final_output
        if isinstance(final_output, str) and final_output:
            yield final_output

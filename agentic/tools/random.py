from typing import Any
from agents import function_tool, RunContextWrapper
from agentic.core.hooks import emit_agent_event

@function_tool
async def random_number(ctx: RunContextWrapper[Any], max: int) -> int:
    import random
    """Generate a random number from 0 to max (inclusive)."""
    value = random.randint(0, max)
    await emit_agent_event(
        ctx,
        source="random_number_tool",
        event_type="tool_random_number_event",
        tool_name="random_number",
        max=max,
        result=value,
    )
    return value

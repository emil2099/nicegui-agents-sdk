from typing import AsyncIterator, Optional
from agents import Agent, ModelSettings
from agentic.core.events import EventPublisher
from agentic.core.hooks import EventPublishingHook
from agentic.core.utils import stream_agent_output

from agentic.tools.random import random_number
from agentic.library.planner import planner_tool
from agentic.library.executor import executor_tool, BASE_TOOLS

DEFAULT_MODEL = 'gpt-5.1'
DEFAULT_MODEL_SETTINGS = ModelSettings(tool_choice="auto")

MANAGER_PROMPT = """
You are a helpful assistant, who is responsible for helping the user in the most efficient way without being annoying.

Approach:
- Call the draft_plan tool for multi-step queries or when clarification is needed before execution.
- Use the tools provided to achieve the goal.
- Reflect on results after each step, and re-plan if necessary. 
- Track useful URLs or citations mentioned by tools. 
- Finish with a concise response that includes a summary paragraph, a few bullet highlights, and a short citations section.

Parallel tool calls:
- Analyse the plan to determine if steps can be executed concurrently
- Call tools in parallel where possible to speed up completion
- Use executor or concurrent tool calls to work out the answer

Outputs:
- Provide a natural response to the initial user query, do not mention the process or planning steps you took to get there.
""".strip()

# Manager Agent defined locally as it's specific to this workflow
manager_agent = Agent(
    name="Manager",
    instructions=MANAGER_PROMPT,
    model=DEFAULT_MODEL,
    model_settings=DEFAULT_MODEL_SETTINGS,
    hooks=EventPublishingHook(),
    tools=[*BASE_TOOLS, planner_tool, executor_tool, random_number],
)

async def run_plan_execute(
    prompt: str, 
    event_publisher: Optional[EventPublisher] = None
) -> AsyncIterator[str]:
    
    async for chunk in stream_agent_output(
        manager_agent, 
        prompt, 
        event_publisher=event_publisher
    ):
        yield chunk

from typing import AsyncIterator, List, Optional, Dict, Any
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from agents import (
    Agent, Runner, ModelSettings, WebSearchTool, CodeInterpreterTool, function_tool,
    RunContextWrapper
)

from openai.types.responses.response_text_delta_event import ResponseTextDeltaEvent
from agents.stream_events import AgentUpdatedStreamEvent, RawResponsesStreamEvent
from openai.types.responses.web_search_tool_param import UserLocation

from events import EventPublisher
from agent_event_hooks import EventPublishingHook, emit_agent_event

load_dotenv()

default_model = 'gpt-5.1'
default_model_settings = ModelSettings(tool_choice="auto")

class PlanStep(BaseModel):
    id: int
    goal: str
    deliverable: str
    tool_hint: Optional[str] = Field(
        default=None,
        description="Optional hint: 'web_search' | 'code' | 'none'"
    )

class TaskPlan(BaseModel):
    steps: List[PlanStep]

planner_prompt = """
Break the user's objective into concrete steps. 
Keep each step crisp, focused on a deliverable. Make the smallest number of steps possible (maximum 5). 

Return plan as numbered list of actions containing the following fields:
Goal: str
Deliverable: str
""".strip()

planner = Agent(
    name="Planner",
    instructions=planner_prompt,
    model='gpt-4.1',
    output_type=TaskPlan,
    hooks=EventPublishingHook(),
)

_base_tools = [
    WebSearchTool(user_location=UserLocation(country='GB', type='approximate')),
    CodeInterpreterTool(
        tool_config={
            "type": "code_interpreter",
            "container": {"type": "auto"},
        }
    ),
]

executor = Agent(
    name="Executor",
    instructions=(
        "Execute provided task. Use tools if helpful. "
        "For web results, include reputable sources with titles and URLs. "
        "For code, print concise, human-readable outputs."
    ),
    model=default_model,
    model_settings=default_model_settings,
    tools=_base_tools,
    hooks=EventPublishingHook(),
)

executor_tool = executor.as_tool(
    tool_name="execute_step",
    tool_description=(
        "Use this to run a single research or analysis step. "
        "Pass the specific instructions and any context gathered so far."
    )
)

planner_tool = planner.as_tool(
    tool_name="draft_plan",
    tool_description=(
        "Break the user's request into a short numbered plan (max 5 steps). "
        "Use for multi-step or ambiguous objectives before executing."
    )
)

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

manager_prompt = """
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

manager = Agent(
    name="Manager",
    instructions=manager_prompt,
    model=default_model,
    model_settings=default_model_settings,
    hooks=EventPublishingHook(),
    tools=[*_base_tools, planner_tool, executor_tool, random_number],
)

async def _stream_agent_output(
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

async def run_plan_execute(
    prompt: str, 
    event_publisher: Optional[EventPublisher] = None
) -> AsyncIterator[str]:
    
    async for chunk in _stream_agent_output(
        manager, 
        prompt, 
        event_publisher=event_publisher
    ):
        yield chunk

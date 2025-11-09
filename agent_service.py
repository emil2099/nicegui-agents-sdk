"""Agent service: Manager orchestrates Planner + Executor."""

from __future__ import annotations

from typing import AsyncIterator, List, Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from openai.types.responses.response_text_delta_event import ResponseTextDeltaEvent
# NOTE: adjust imports below if your SDK package path differs
from agents import Agent, Runner, ModelSettings, WebSearchTool, CodeInterpreterTool
from agents.stream_events import AgentUpdatedStreamEvent, RawResponsesStreamEvent, RunItemStreamEvent

from openai.types.shared import Reasoning

from events import EventPublisher

load_dotenv()

default_model = 'gpt-4.1'
default_model_settings = ModelSettings(tool_choice="auto")
# default_model_settings = ModelSettings(reasoning=Reasoning(effort="medium"), tool_choice="auto", parallel_tool_calls=True)

# ---------------------------
# Structured output models
# ---------------------------

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

# ---------------------------
# Planner (outputs a typed plan)
# ---------------------------

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
)

# ---------------------------
# Executor (tool-enabled)
# ---------------------------

# WebSearchTool works as-is. CodeInterpreterTool requires tool_config in recent SDK versions.
_base_tools = [
    WebSearchTool(),
    CodeInterpreterTool(
        tool_config={
            "type": "code_interpreter",
            "container": {"type": "auto"},  # or {"type": "ref", "session_id": "..."}
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
    model='gpt-5-mini',
    model_settings=ModelSettings(reasoning=Reasoning(effort="low"), verbosity="low"),
    tools=_base_tools,
)


# ---------------------------
# Manager setup
# ---------------------------

# Allow the executor to be used as a callable tool by other agents (Manager).
executor_tool = executor.as_tool(
    tool_name="execute_step",
    tool_description=(
        "Use this to run a single research or analysis step. "
        "Pass the specific instructions and any context gathered so far."
    ),
)

planner_tool = planner.as_tool(
    tool_name="draft_plan",
    tool_description=(
        "Break the user's request into a short numbered plan (max 5 steps). "
        "Use for multi-step or ambiguous objectives before executing."
    ),
)

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
    tools=[*_base_tools, planner_tool, executor_tool],
)


# ---------------------------
# UI-friendly wrappers
# ---------------------------

async def _stream_agent_output(
    agent: Agent, 
    prompt: str, 
    event_publisher: EventPublisher | None = None
) -> AsyncIterator[str]:
    """Return an async iterator that yields text deltas for the given agent."""

    result = Runner.run_streamed(agent, prompt)

    yielded = False
    active_agent_name = agent.name
    async for event in result.stream_events():
        
        if event_publisher:
            try:
                event_publisher.publish_openai_agents_event(event)
            except Exception as e:
                print(f"[AgentService Error] Failed to publish event: {e}")

        if isinstance(event, AgentUpdatedStreamEvent):
            active_agent_name = event.new_agent.name
            continue

        if isinstance(event, RawResponsesStreamEvent):
            # Only output text from top-level agent, not sub-agents
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

async def run_plan_execute(prompt: str, event_publisher: EventPublisher | None = None) -> AsyncIterator[str]:
    """Stream deltas from the Manager (planner/executor) pipeline."""
    async for chunk in _stream_agent_output(manager, prompt, event_publisher=event_publisher):
        yield chunk

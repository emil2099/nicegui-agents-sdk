"""Agent service: Manager orchestrates Planner + Executor with optional simple chat."""

from __future__ import annotations

from typing import AsyncIterator, List, Optional

from pydantic import BaseModel, Field
from openai.types.responses.response_text_delta_event import ResponseTextDeltaEvent
# NOTE: adjust imports below if your SDK package path differs
from agents import Agent, Runner, ModelSettings, WebSearchTool, CodeInterpreterTool
from agents.stream_events import RawResponsesStreamEvent

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
    topic: str
    steps: List[PlanStep]

# ---------------------------
# Base assistant (simple chat)
# ---------------------------

assistant = Agent(
    name="Assistant",
    instructions=(
        "You are a concise, helpful assistant. "
        "Answer clearly and avoid unnecessary verbosity."
    ),
    model="gpt-4.1-mini",
)

# ---------------------------
# Planner (outputs a typed plan)
# ---------------------------

planner = Agent(
    name="Planner",
    instructions=(
        "Break the user's objective into concrete steps. "
        "Prefer web_search for facts and code for calculations or data analysis. "
        "Keep each step crisp, focused on a deliverable."
        "Make the smallest number of steps possible, no more than 5 steps in total."
    ),
    model="gpt-4.1-mini",
    output_type=TaskPlan,  # <- Pydantic-typed output
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
        "Execute the given step. Use tools if helpful. "
        "For web results, include reputable sources with titles and URLs. "
        "For code, print concise, human-readable outputs."
    ),
    model="gpt-4.1-mini",
    tools=_base_tools,
    model_settings=ModelSettings(tool_choice="auto"),
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

manager_prompt = """
You are a helpful assistant, who is responsible for helping the user in the most efficient way without being annoying.

Approach:
- Read the user's request, decide if it is simple, and respond directly when possible. 
- When additional structure will help, call the Planner tool and provide the full context so it can generate completion plan for the user query.
- Follow the plan as outlined.
- If specific steps can be run in parallel or have significant complexity, pass the tasks to Executor tool. 
- Reflect on results after each step, and re-plan if necessary. 
- Track useful URLs or citations mentioned by tools. 
- Finish with a concise response that includes a summary paragraph, a few bullet highlights, and a short citations section.
""".strip()

manager = Agent(
    name="Manager",
    instructions=manager_prompt,
    model="gpt-4.1-mini",
    handoffs=[planner],
    tools=[*_base_tools, executor_tool],
    model_settings=ModelSettings(tool_choice="auto", parallel_tool_calls=True),
)


# ---------------------------
# UI-friendly wrappers
# ---------------------------

def _stream_agent_output(agent: Agent, prompt: str) -> AsyncIterator[str]:
    """Return an async iterator that yields text deltas for the given agent."""

    result = Runner.run_streamed(agent, prompt)

    async def _generator() -> AsyncIterator[str]:
        yielded = False
        async for event in result.stream_events():
            if isinstance(event, RawResponsesStreamEvent):
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

    return _generator()


async def run_prompt(prompt: str) -> AsyncIterator[str]:
    """Stream deltas from the Assistant agent."""
    async for chunk in _stream_agent_output(assistant, prompt):
        yield chunk

async def run_plan_execute(prompt: str) -> AsyncIterator[str]:
    """Stream deltas from the Manager (planner/executor) pipeline."""
    async for chunk in _stream_agent_output(manager, prompt):
        yield chunk

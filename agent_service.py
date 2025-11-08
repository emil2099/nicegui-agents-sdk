"""Agent service: Manager orchestrates Planner + Executor with optional simple chat."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field
# NOTE: adjust imports below if your SDK package path differs
from agents import Agent, Runner, ModelSettings, WebSearchTool, CodeInterpreterTool

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
# Base assistant (simple chat)
# ---------------------------

assistant = Agent(
    name="Assistant",
    instructions=(
        "You are a concise, helpful assistant. "
        "Answer clearly and avoid unnecessary verbosity."
    ),
    model="gpt-5-mini",
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
    model="gpt-5-mini",
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
    model="gpt-5-mini",
    tools=_base_tools,
    model_settings=ModelSettings(tool_choice="auto"),
)


# ---------------------------
# Manager setup
# ---------------------------

# Allow the executor to be used as a callable tool by other agents (Manager).
executor_tool = executor.as_tool(
    tool_name="execute_research_step",
    tool_description=(
        "Use this to run a single research or analysis step. "
        "Pass the specific instructions and any context gathered so far."
    ),
)


manager = Agent(
    name="Manager",
    instructions=(
        "You are the orchestration manager. Read the user's request, decide if it is simple, "
        "and respond directly when possible. When additional structure will help, call the "
        "Planner handoff and provide the full conversation context so it can return a TaskPlan "
        "(topic + steps with id, goal, deliverable, optional tool_hint). Use the plan to "
        "determine which steps can be executed simultaneously. Call the Executor tool for each "
        "step—parallelise independent steps, run sequentially when dependencies are stated. "
        "Track useful URLs or citations mentioned by tools. Finish with a concise response that "
        "includes a summary paragraph, a few bullet highlights, and a short citations section."
    ),
    model="gpt-5-mini",
    handoffs=[planner],
    tools=[*_base_tools, executor_tool],
    model_settings=ModelSettings(tool_choice="auto", parallel_tool_calls=True),
)


# ---------------------------
# UI-friendly wrappers
# ---------------------------

async def run_prompt(prompt: str) -> str:
    """Simple chat-style run (used by your original button)."""
    try:
        result = await Runner.run(assistant, prompt)
        return result.final_output or "(no response)"
    except Exception as e:
        return f"Error: {e}"

# Backward-compat alias if you previously referenced run_simple elsewhere
run_simple = run_prompt


async def run_plan_execute(prompt: str) -> str:
    """Manager-led pipeline (Planner + Executor handoffs as needed)."""
    try:
        result = await Runner.run(manager, prompt)
        return result.final_output or "(no response)"
    except Exception as e:
        return f"Error (plan→execute): {e}"

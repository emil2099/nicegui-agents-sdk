"""Agent service: simple chat + planner→executor with WebSearchTool & CodeInterpreterTool."""

from __future__ import annotations

import re
from typing import List, Optional

from pydantic import BaseModel, Field
# NOTE: adjust imports below if your SDK package path differs
from agents import (
    Agent,
    Runner,
    ModelSettings,
    WebSearchTool,
    CodeInterpreterTool,
)

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

class ResearchBrief(BaseModel):
    topic: str
    summary: str
    citations: List[str] = []


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
        "Break the user's objective into 2–5 concrete steps. "
        "Prefer web_search for facts and code for calculations or data analysis. "
        "Keep each step crisp, focused on a deliverable."
    ),
    model="gpt-5-mini",
    output_type=TaskPlan,  # <- Pydantic-typed output
)

# ---------------------------
# Executor (tool-enabled)
# ---------------------------

# WebSearchTool works as-is. CodeInterpreterTool requires tool_config in recent SDK versions.
executor = Agent(
    name="Executor",
    instructions=(
        "Execute the given step. Use tools if helpful. "
        "For web results, include reputable sources with titles and URLs. "
        "For code, print concise, human-readable outputs."
    ),
    model="gpt-5-mini",
    tools=[
        WebSearchTool(),
        CodeInterpreterTool(
            tool_config={
                "type": "code_interpreter",
                "container": {"type": "auto"},   # or {"type": "ref", "session_id": "..."} to reuse
            }
        ),
    ],
    model_settings=ModelSettings(tool_choice="auto"),
)


# ---------------------------
# Orchestration
# ---------------------------

_URL_RE = re.compile(r"(https?://[^\s)<>\]]+)", re.IGNORECASE)

def _extract_urls(text: str) -> List[str]:
    if not text:
        return []
    urls = _URL_RE.findall(text)
    # De-dup and keep order
    seen = set()
    uniq = []
    for u in urls:
        if u not in seen:
            uniq.append(u)
            seen.add(u)
    return uniq


async def plan_then_execute(user_prompt: str) -> ResearchBrief:
    """Create a plan with the Planner, execute steps with the Executor, and summarise."""
    # 1) Plan
    plan_result = await Runner.run(planner, f"Topic: {user_prompt}")
    plan: TaskPlan = plan_result.final_output  # typed (Pydantic)

    # 2) Execute steps
    collected_markdown: List[str] = []
    gathered_urls: List[str] = []

    for step in plan.steps:
        step_msg = (
            f"Step {step.id}\n"
            f"Goal: {step.goal}\n"
            f"Deliverable: {step.deliverable}\n"
            f"Tool hint: {step.tool_hint or 'auto'}"
        )

        exec_result = await Runner.run(executor, step_msg)
        out_text = exec_result.final_output or ""

        collected_markdown.append(f"### Step {step.id}\n{out_text}")

        # Try to collect URLs from tool output text
        gathered_urls.extend(_extract_urls(out_text))

        # Also scan any item payloads, if exposed (SDK dependent). Safe no-op if absent.
        for attr in ("items", "events", "tool_calls"):
            maybe = getattr(exec_result, attr, None)
            if not maybe:
                continue
            for obj in maybe:
                url = getattr(obj, "url", None)
                if isinstance(url, str):
                    gathered_urls.append(url)

    # 3) Summarise into a typed brief
    summariser = Agent(
        name="Summariser",
        instructions=(
            "Summarise the findings into a short brief. "
            "Start with a tight paragraph; then give 3–6 bullet points."
        ),
        model="gpt-5-mini",
        output_type=ResearchBrief,
    )

    joined = "\n\n".join(collected_markdown)
    brief_result = await Runner.run(
        summariser,
        f"Topic: {plan.topic}\n\nFindings:\n{joined}"
    )
    brief: ResearchBrief = brief_result.final_output
    # De-duplicate citations, keep first 8
    uniq_citations = []
    seen = set()
    for u in gathered_urls:
        if u not in seen:
            uniq_citations.append(u)
            seen.add(u)
        if len(uniq_citations) >= 8:
            break
    brief.citations = uniq_citations
    return brief


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
    """Planner → Executor pipeline, returning Markdown for direct rendering."""
    try:
        brief = await plan_then_execute(prompt)
        citations_md = (
            "\n".join(f"- {u}" for u in brief.citations)
            if brief.citations else "_No citations._"
        )
        return (
            f"# {brief.topic}\n\n"
            f"{brief.summary}\n\n"
            f"---\n**Citations**\n{citations_md}"
        )
    except Exception as e:
        return f"Error (plan→execute): {e}"

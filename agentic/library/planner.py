from typing import List, Optional
from pydantic import BaseModel, Field
from agents import Agent
from agentic.core.hooks import EventPublishingHook

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

PLANNER_PROMPT = """
Break the user's objective into concrete steps. 
Keep each step crisp, focused on a deliverable. Make the smallest number of steps possible (maximum 5). 

Return plan as numbered list of actions containing the following fields:
Goal: str
Deliverable: str
""".strip()

planner_agent = Agent(
    name="Planner",
    instructions=PLANNER_PROMPT,
    model='gpt-4.1',
    output_type=TaskPlan,
    hooks=EventPublishingHook(),
)

planner_tool = planner_agent.as_tool(
    tool_name="draft_plan",
    tool_description=(
        "Break the user's request into a short numbered plan (max 5 steps). "
        "Use for multi-step or ambiguous objectives before executing."
    )
)

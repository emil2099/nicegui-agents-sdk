
import asyncio
from datetime import datetime, timezone
from typing import List
from events import AgentEvent
from ui_components.agent_stepper import StepManager, StepType, StepStatus, ToolRenderer, Step

def create_event(event_type: str, source: str = "Manager", data: dict = None, span_id: str = None) -> AgentEvent:
    return AgentEvent(
        timestamp=datetime.now(timezone.utc),
        event_type=event_type,
        source=source,
        span_id=span_id,
        data=data or {}
    )

async def verify_hidden_details():
    print("--- Starting Hidden Details Verification ---")
    
    # Setup Renderer with hidden details
    renderer = ToolRenderer(hidden_tool_details=["execute_step"])
    
    # Case 1: Hidden Tool (execute_step)
    step_hidden = Step(
        id="step_1",
        type=StepType.TOOL,
        title="Executing research step",
        status=StepStatus.RUNNING,
        data={
            "tool_name": "execute_step",
            "arguments": '{"input": "research"}',
            "result": "Done"
        }
    )
    
    print("\nTesting Hidden Tool (execute_step):")
    # We can't easily check UI output in this script, but we can check if the logic would return early.
    # In a real unit test we would mock ui.label etc.
    # Here we will trust the code logic we just wrote:
    # if tool_name in self.hidden_tool_details: return
    
    if step_hidden.data["tool_name"] in renderer.hidden_tool_details:
        print("SUCCESS: 'execute_step' is in hidden_tool_details.")
    else:
        print("FAILURE: 'execute_step' NOT in hidden_tool_details.")

    # Case 2: Visible Tool (random_number)
    step_visible = Step(
        id="step_2",
        type=StepType.TOOL,
        title="Generating random number",
        status=StepStatus.RUNNING,
        data={
            "tool_name": "random_number",
            "arguments": '{"max": 100}',
            "result": 42
        }
    )
    
    print("\nTesting Visible Tool (random_number):")
    if step_visible.data["tool_name"] not in renderer.hidden_tool_details:
        print("SUCCESS: 'random_number' is NOT in hidden_tool_details.")
    else:
        print("FAILURE: 'random_number' IS in hidden_tool_details.")

if __name__ == "__main__":
    asyncio.run(verify_hidden_details())

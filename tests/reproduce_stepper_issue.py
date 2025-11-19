
import asyncio
from datetime import datetime, timezone
from typing import List
from events import AgentEvent
from ui_components.agent_stepper import StepManager, StepType, StepStatus

def create_event(event_type: str, source: str = "Manager", data: dict = None, span_id: str = None) -> AgentEvent:
    return AgentEvent(
        timestamp=datetime.now(timezone.utc),
        event_type=event_type,
        source=source,
        span_id=span_id,
        data=data or {}
    )

async def reproduce_issue():
    print("--- Starting Reproduction ---")
    manager = StepManager()
    
    # Simulate the event stream from the user request
    events = [
        create_event("agent_started_stream_event", source="Manager"),
        # Draft plan (sequential)
        create_event("tool_started_stream_event", data={"tool": {"name": "draft_plan"}}, span_id="span_1"),
        create_event("tool_ended_stream_event", data={"result": "plan..."}, span_id="span_1"),
        
        # Parallel execution starts
        # 1. Random number tool starts
        create_event("tool_started_stream_event", data={"tool": {"name": "random_number"}}, span_id="span_2"),
        
        # 2. Execute step (weather) starts - THIS SHOULD NOT CLOSE RANDOM NUMBER
        create_event("tool_started_stream_event", data={"tool": {"name": "execute_step"}}, span_id="span_3"),
        
        # 3. Random number finishes
        create_event("tool_ended_stream_event", data={"result": 3}, span_id="span_2"),
        
        # 4. Execute step finishes
        create_event("tool_ended_stream_event", data={"result": "Weather info..."}, span_id="span_3"),
    ]

    for i, event in enumerate(events):
        print(f"\nEvent {i+1}: {event.event_type} (span_id={event.span_id})")
        manager.handle_event(event)
        
        print("Current Steps:")
        for step in manager.steps:
            print(f"  - {step.title} [{step.status.value}] (id={step.id})")

    print("\n--- Final State Analysis ---")
    random_step = next((s for s in manager.steps if "random" in s.title.lower() or "Executing random_number" in s.title), None)
    weather_step = next((s for s in manager.steps if "Executing step" in s.title), None)
    
    if random_step and weather_step:
        print(f"Random Step Status: {random_step.status}")
        print(f"Weather Step Status: {weather_step.status}")
        
        if random_step.status == StepStatus.COMPLETED and weather_step.status == StepStatus.COMPLETED:
             # In the broken state, random_step might be completed prematurely or weather step might overwrite it?
             # Actually, the issue described is "Generating random number item doesn’t actually have the output produced by the tool"
             # This happens if the step is closed before the result arrives, or if the result event doesn't match the open step.
             pass
    else:
        print("Missing steps!")

if __name__ == "__main__":
    asyncio.run(reproduce_issue())

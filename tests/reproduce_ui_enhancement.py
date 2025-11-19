
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

async def reproduce_ui():
    print("--- Starting UI Enhancement Reproduction ---")
    manager = StepManager()
    
    events = [
        create_event("agent_started_stream_event", source="Manager"),
        
        # 1. Tool Call Detected (LLM proposes tool)
        create_event("tool_call_detected_event", data={
            "tool_name": "random_number",
            "arguments": '{"max": 100}',
            "tool_call_id": "call_123"
        }),
        
        # 2. Tool Started (Runner executes)
        create_event("tool_started_stream_event", data={"tool": {"name": "random_number"}}, span_id="span_1"),
        
        # 3. Tool Ended (Result)
        create_event("tool_ended_stream_event", data={"result": 42}, span_id="span_1"),
    ]

    for i, event in enumerate(events):
        print(f"\nEvent {i+1}: {event.event_type}")
        manager.handle_event(event)
        
        print("Current Steps:")
        for step in manager.steps:
            print(f"  - {step.title} [{step.status.value}] (id={step.id})")
            if step.data.get("arguments"):
                print(f"    Args: {step.data.get('arguments')}")
            if step.data.get("result"):
                print(f"    Result: {step.data.get('result')}")

    print("\n--- Final State Analysis ---")
    step = manager.steps[-1]
    if step.title == "Executing random_number" and step.status == StepStatus.COMPLETED:
        if step.data.get("arguments") == '{"max": 100}' and step.data.get("result") == 42:
            print("SUCCESS: Arguments and Result preserved.")
        else:
            print("FAILURE: Data mismatch.")
    else:
        print("FAILURE: Step state incorrect.")

if __name__ == "__main__":
    asyncio.run(reproduce_ui())

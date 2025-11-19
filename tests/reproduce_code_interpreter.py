
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

async def reproduce_code_interpreter():
    print("--- Starting Code Interpreter Reproduction ---")
    manager = StepManager()
    
    events = [
        create_event("agent_started_stream_event", source="Manager"),
        
        # 1. Code Interpreter Call (LLM proposes code)
        create_event("tool_code_interpreter_event", data={
            "code": "print('Hello World')",
            "outputs": [], # Initially empty
            "tool_call_id": "call_code_1"
        }, span_id="span_code_1"),
        
        # 2. Tool Started (Runner executes)
        create_event("tool_started_stream_event", data={
            "tool": {"name": "code_interpreter", "type": "code_interpreter"}
        }, span_id="span_code_1"),
        
        # 3. Tool Ended (Result)
        # Simulating a result that might come back as a string or a structured object
        create_event("tool_ended_stream_event", data={
            "result": "Hello World\n" 
        }, span_id="span_code_1"),
    ]

    for i, event in enumerate(events):
        print(f"\nEvent {i+1}: {event.event_type}")
        manager.handle_event(event)
        
        print("Current Steps:")
        for step in manager.steps:
            print(f"  - {step.title} [{step.status.value}] (id={step.id})")
            if step.data.get("tool_type") == "code_interpreter":
                print(f"    Code: {step.data.get('code')}")
                print(f"    Outputs: {step.data.get('outputs')}")
                print(f"    Result: {step.data.get('result')}")

    print("\n--- Final State Analysis ---")
    step = manager.steps[-1]
    if step.data.get("tool_type") == "code_interpreter" and step.status == StepStatus.COMPLETED:
        outputs = step.data.get("outputs")
        result = step.data.get("result")
        
        if outputs and len(outputs) > 0 and outputs[0] == result:
             print("SUCCESS: Result was correctly merged into outputs.")
        elif result and (not outputs):
             print("FAILURE: Result exists but outputs is empty.")
        else:
             print(f"INFO: Outputs: {outputs}, Result: {result}")

if __name__ == "__main__":
    asyncio.run(reproduce_code_interpreter())

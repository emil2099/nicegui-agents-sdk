import asyncio
import json
from datetime import datetime
from typing import Any

# Ensure we can import from current directory
import sys
import os
sys.path.append(os.getcwd())

from agent_service import run_plan_execute
from events import AgentEvent, EventPublisher

def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if hasattr(obj, 'model_dump'):
        return obj.model_dump()
    if hasattr(obj, '__dict__'):
        return obj.__dict__
    return str(obj)

async def capture_subscriber(event: AgentEvent):
    with open("captured_events.jsonl", "a") as f:
        f.write(json.dumps(event.model_dump(), default=json_serial) + "\n")

async def main():
    print("Starting event capture...")
    # Clear previous capture
    if os.path.exists("captured_events.jsonl"):
        os.remove("captured_events.jsonl")

    publisher = EventPublisher(subscribers=[capture_subscriber])
    
    # Use a prompt that triggers planning and execution
    prompt = "What is the weather in London? Plan it out first."
    
    print(f"Prompt: {prompt}")
    stream = run_plan_execute(prompt, event_publisher=publisher)
    
    async for chunk in stream:
        print(".", end="", flush=True)
    
    print("\nCapture complete. Events saved to captured_events.jsonl")

if __name__ == "__main__":
    asyncio.run(main())

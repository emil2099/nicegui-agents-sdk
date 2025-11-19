
import asyncio
from agent_service import manager, Runner

async def inspect_tool():
    print("--- Starting Tool Inspection ---")
    # Trigger a simple tool call (random number)
    result = Runner.run_streamed(manager, "Generate a random number between 1 and 10")
    async for event in result.stream_events():
        pass

if __name__ == "__main__":
    asyncio.run(inspect_tool())

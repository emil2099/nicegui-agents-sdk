import asyncio
import json
from typing import Any
from dotenv import load_dotenv
from agents import Agent, Runner, WebSearchTool, CodeInterpreterTool
from agents import AgentHooks, RunContextWrapper, ModelResponse

# Load env vars
load_dotenv()

class InspectionHook(AgentHooks):
    async def on_llm_end(self, context: RunContextWrapper, agent: Agent, response: ModelResponse) -> None:
        print(f"\n[HOOK] on_llm_end triggered for agent: {agent.name}")
        
        # Inspect output items for messages and annotations
        if hasattr(response, 'output'):
            for i, item in enumerate(response.output):
                print(f"\nItem {i} type: {type(item)}")
                
                if hasattr(item, 'type') and item.type == 'web_search_call':
                    print("--- Web Search Call Item ---")
                    print(f"  Item dir: {dir(item)}")
                    try:
                        print(f"  Item dump: {item.model_dump()}")
                    except:
                        print("  Could not dump item")
                    
                    if hasattr(item, 'action'):
                        print(f"  Action: {item.action}")
                        print(f"  Action dir: {dir(item.action)}")
                
                if hasattr(item, 'type') and item.type == 'message':
                    print("--- Message Item ---")
                    for j, content_part in enumerate(item.content):
                        print(f"  Content Part {j} type: {type(content_part)}")
                        if hasattr(content_part, 'text'):
                            print(f"  Text: {content_part.text[:50]}...") # Truncate text
                        
                        if hasattr(content_part, 'annotations'):
                            print(f"  Annotations found: {len(content_part.annotations)}")
                            for k, annotation in enumerate(content_part.annotations):
                                print(f"    Annotation {k} type: {type(annotation)}")
                                print(f"    Annotation {k} data: {annotation}")
                                if hasattr(annotation, 'type') and annotation.type == 'url_citation':
                                    print(f"    -> Found URL Citation: {annotation.url} - {annotation.title}")

async def run_debug():
    print("--- Starting Debug ---")
    
    tools = [WebSearchTool()]
    
    agent = Agent(
        name="Debugger",
        instructions="You are a researcher. Use web search to answer. ALWAYS cite your sources.",
        model="gpt-4o",
        tools=tools
    )
    
    agent.hooks = InspectionHook()
    
    print("\n--- Running Web Search ---")
    result = await Runner.run(agent, "Find 3 recent news articles about AI and cite them.")
    print("\nFinal Result:", result)

if __name__ == "__main__":
    asyncio.run(run_debug())

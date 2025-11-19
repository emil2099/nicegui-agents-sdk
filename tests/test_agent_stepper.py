import unittest
from datetime import datetime, timezone
from ui_components.agent_stepper import StepManager, StepType, StepStatus
from events import AgentEvent

def create_event(event_type: str, source: str = "test_agent", **data) -> AgentEvent:
    return AgentEvent(
        event_type=event_type,
        source=source,
        data=data,
        timestamp=datetime.now(timezone.utc)
    )

class TestStepManager(unittest.TestCase):
    def test_linear_flow(self):
        manager = StepManager()
        
        # 1. Agent Starts
        manager.handle_event(create_event("agent_started_stream_event", source="Manager"))
        self.assertEqual(len(manager.steps), 0)
        
        # 2. Thinking
        manager.handle_event(create_event("llm_started_stream_event", source="Manager"))
        self.assertEqual(len(manager.steps), 1)
        self.assertEqual(manager.steps[0].type, StepType.THINKING)
        self.assertEqual(manager.steps[0].status, StepStatus.RUNNING)
        
        # 3. Tool Use (should replace or follow thinking? Plan says "Replaces or follows")
        # Let's assume it follows for history tracking.
        manager.handle_event(create_event("tool_started_stream_event", source="Manager", tool={"name": "execute_step"}))
        
        self.assertEqual(len(manager.steps), 2)
        self.assertEqual(manager.steps[0].status, StepStatus.COMPLETED) # Thinking implicitly done
        self.assertEqual(manager.steps[1].type, StepType.TOOL)
        self.assertEqual(manager.steps[1].title, "Executing step")
        
        # 4. Nested Agent Events (should be ignored or treated as part of current tool step)
        # Executor starts -> Ignored
        manager.handle_event(create_event("agent_started_stream_event", source="Executor"))
        self.assertEqual(len(manager.steps), 2)
        
        # Executor Thinking -> Ignored or updates tool step status?
        # Plan says "Nested agent events are treated as part of the parent's current step or ignored"
        # Let's ignore them to keep it simple, or maybe just log them?
        # For now, verify they don't create new top-level steps.
        manager.handle_event(create_event("llm_started_stream_event", source="Executor"))
        self.assertEqual(len(manager.steps), 2)
        
        # 5. Tool Ends
        manager.handle_event(create_event("tool_ended_stream_event", source="Manager", tool={"name": "execute_step"}, result="Done"))
        self.assertEqual(manager.steps[1].status, StepStatus.COMPLETED)
        
        # 6. Final Message (LLM ends with message)
        manager.handle_event(create_event("llm_ended_stream_event", source="Manager", response={"output": [{"type": "message", "content": "Hello"}]}))
        # This might create a message step or just be the end.
        # If LLM ended without tool calls, it usually means it produced a message.
        # Let's check if we have a new step or if it updated the last thinking step (if we had one).
        # In this flow, we had Thinking -> Tool -> (Back to Thinking usually) -> Message.
        
        # Let's simulate the "Back to Thinking" part
        manager.handle_event(create_event("llm_started_stream_event", source="Manager"))
        self.assertEqual(len(manager.steps), 3)
        self.assertEqual(manager.steps[2].type, StepType.THINKING)
        
        # Now LLM ends with message
        manager.handle_event(create_event("llm_ended_stream_event", source="Manager", response={"output": [{"type": "message", "content": "Hello"}]}))
        self.assertEqual(manager.steps[2].status, StepStatus.COMPLETED)

        # 7. Agent Ends
        manager.handle_event(create_event("agent_ended_stream_event", source="Manager"))
        self.assertEqual(len(manager.steps), 4)
        self.assertEqual(manager.steps[3].type, StepType.FINISHED)
        self.assertEqual(manager.steps[3].status, StepStatus.COMPLETED)

    def test_custom_tool_map(self):
        custom_map = {"execute_step": "Running the Step"}
        manager = StepManager(tool_title_map=custom_map)
        
        # Start agent
        manager.handle_event(create_event("agent_started_stream_event", source="Manager"))
        
        # Tool start
        manager.handle_event(create_event("tool_started_stream_event", source="Manager", tool={"name": "execute_step"}))
        
        self.assertEqual(manager.steps[0].title, "Running the Step")

if __name__ == '__main__':
    unittest.main()

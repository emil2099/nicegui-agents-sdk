import unittest
from datetime import datetime, timezone
from typing import List
from ui_components.agent_stepper import (
    Step, StepType, StepStatus, EventContext, 
    EventHandlerRegistry
)
# Import handlers directly for testing
from ui_components.agent_stepper.tool_thinking import ThinkingEventHandler
from ui_components.agent_stepper.tool_generic import GenericToolEventHandler
from ui_components.agent_stepper.lifecycle import LifecycleEventHandler
from events import AgentEvent

def create_event(event_type: str, source: str = "Manager", **data) -> AgentEvent:
    return AgentEvent(
        event_type=event_type,
        source=source,
        data=data,
        timestamp=datetime.now(timezone.utc)
    )

class TestAgentStepperLogic(unittest.TestCase):
    def setUp(self):
        self.steps: List[Step] = []
        self.tool_map = {}
        # Initialize context with "Manager" as main agent
        self.context = EventContext(self.steps, "Manager", self.tool_map)
        
        # Setup Registry with the handlers we want to test
        self.registry = EventHandlerRegistry()
        self.registry.register(ThinkingEventHandler())
        self.registry.register(GenericToolEventHandler())
        self.registry.register(LifecycleEventHandler())

    def handle_event(self, event: AgentEvent):
        handlers = self.registry.get_handlers(event)
        for handler in handlers:
            handler.handle(event, self.context)

    def test_linear_flow(self):
        # 1. Thinking Starts
        self.handle_event(create_event("llm_started_stream_event"))
        self.assertEqual(len(self.steps), 1)
        self.assertEqual(self.steps[0].type, StepType.THINKING)
        self.assertEqual(self.steps[0].status, StepStatus.RUNNING)
        
        # 1.5 Thinking Ends (triggers tool call usually)
        self.handle_event(create_event("llm_ended_stream_event"))
        self.assertEqual(self.steps[0].status, StepStatus.COMPLETED)

        # 2. Tool Use (Generic)
        # Should start a tool step
        self.handle_event(create_event("tool_started_stream_event", tool={"name": "execute_step"}, span_id="span1"))
        
        self.assertEqual(len(self.steps), 2)
        self.assertEqual(self.steps[1].type, StepType.TOOL)
        self.assertEqual(self.steps[1].title, "Executing step")
        self.assertEqual(self.steps[1].status, StepStatus.RUNNING)
        
        # 3. Tool Ends
        self.handle_event(create_event("tool_ended_stream_event", tool={"name": "execute_step"}, result="Done", span_id="span1"))
        self.assertEqual(self.steps[1].status, StepStatus.COMPLETED)
        
        # 4. Back to Thinking
        self.handle_event(create_event("llm_started_stream_event"))
        self.assertEqual(len(self.steps), 3)
        self.assertEqual(self.steps[2].type, StepType.THINKING)
        self.assertEqual(self.steps[2].status, StepStatus.RUNNING)
        
        # 5. Agent Ends
        self.handle_event(create_event("agent_ended_stream_event"))
        self.assertEqual(len(self.steps), 4)
        self.assertEqual(self.steps[2].status, StepStatus.COMPLETED) # Last thinking done
        self.assertEqual(self.steps[3].type, StepType.FINISHED)
        self.assertEqual(self.steps[3].status, StepStatus.COMPLETED)

    def test_custom_tool_map(self):
        self.context.tool_title_map["execute_step"] = "Running the Step"
        
        # Tool start
        self.handle_event(create_event("tool_started_stream_event", tool={"name": "execute_step"}))
        
        self.assertEqual(self.steps[0].title, "Running the Step")

if __name__ == '__main__':
    unittest.main()

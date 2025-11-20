# Agent Stepper Component Documentation

The `AgentStepper` is a modular UI component for visualizing agent execution steps (thinking, tool usage, completion). It uses a registry-based architecture to allow easy extension without modifying core code.

## Architecture

The component is split into 7 files in `ui_components/agent_stepper/`:

- **`core.py`**: Defines data models (`Step`, `StepType`), protocols (`EventHandler`, `StepRenderer`), and the `EventContext`.
- **`components.py`**: Contains the main `AgentStepper` UI component.
- **`tool_*.py`**: Consolidated modules containing both the **Event Handler** and **Renderer** for specific tools.
- **`lifecycle.py`**: Handles agent start/finish events.

### Key Concepts

- **Event Handler**: Listens for specific `AgentEvent` types and updates the list of `Step` objects.
- **Step Renderer**: Renders a specific `Step` into the NiceGUI interface.
- **Registry**: `AgentStepper` maintains registries for both handlers and renderers.

## Usage

```python
from ui_components.agent_stepper import AgentStepper

# Create the stepper
stepper = AgentStepper()

# In your event loop/handler
await stepper.handle_event(event)
```

## Adding Custom Tools

To add support for a new tool, you don't need to touch the core library. Just create a new file (e.g., `my_tool.py`) and register your handler and renderer.

### 1. Define Handler and Renderer

```python
from ui_components.agent_stepper import EventHandler, StepRenderer, EventContext, Step, StepType, StepStatus
from nicegui import ui

class MyToolHandler(EventHandler):
    def can_handle(self, event):
        return event.event_type == "my_tool_event"

    def handle(self, event, context: EventContext):
        step = context.create_step(
            StepType.TOOL,
            "My Custom Tool",
            data=event.data
        )
        step.status = StepStatus.COMPLETED
        context.steps.append(step)
        return [step]

class MyToolRenderer(StepRenderer):
    def can_handle(self, step):
        return step.title == "My Custom Tool"

    def render(self, step, container):
        with container:
            ui.label(f"Tool Data: {step.data}")
```

### 2. Register with Stepper

```python
# Access the registries on the stepper instance
stepper.event_registry.register(MyToolHandler())
stepper.renderer_registry.register(MyToolRenderer())
```

## Testing

Unit tests are located in `tests/test_agent_stepper.py`. They test the logic by directly invoking handlers via a registry, bypassing the UI layer.

```bash
python -m unittest tests/test_agent_stepper.py
```

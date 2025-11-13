# Good Agent Design Specification

## Core APIs

Basic Usage:

```python
from good_agent import Agent

async with Agent("You are a helpful assistant.") as agent:
    agent.append("What is 2+2?")
    resp = await agent.call()
    assert resp.content == "4"

    # Typed, role-aware message history
    assert agent[-1].content == "4"  # last message
    assert agent[-1].role == "assistant"
    assert agent.assistant[-1].content == "4"  # last assistant message
    assert agent.user[-1].content == "What is 2+2?"  # last user message

```

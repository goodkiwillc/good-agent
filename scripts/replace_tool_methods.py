#!/usr/bin/env python3
"""Replace tool-related methods in agent.py with delegations to ToolExecutor."""

import re

# Read the file
with open("src/good_agent/agent.py", "r") as f:
    content = f.read()

# Replace invoke_many (lines 2980-3171)
invoke_many_pattern = r'    async def invoke_many\(\s*self,\s*invocations: Sequence\[tuple\[Tool \| str \| Callable, dict\[str, Any\]\]\],\s*\) -> list\[ToolResponse\]:.*?(?=\n    def invoke_func)'

invoke_many_replacement = '''    async def invoke_many(
        self,
        invocations: Sequence[tuple[Tool | str | Callable, dict[str, Any]]],
    ) -> list[ToolResponse]:
        """Execute multiple tools in parallel.

        Args:
            invocations: Sequence of (tool, parameters) tuples

        Returns:
            List of ToolResponse objects in invocation order
        """
        return await self._tool_executor.invoke_many(invocations)

'''

content = re.sub(invoke_many_pattern, invoke_many_replacement, content, flags=re.DOTALL)

# Replace get_pending_tool_calls
get_pending_pattern = r'    def get_pending_tool_calls\(self\) -> list\[ToolCall\]:.*?return pending_calls'

get_pending_replacement = '''    def get_pending_tool_calls(self) -> list[ToolCall]:
        """Get list of tool calls that don't have corresponding responses.

        Returns:
            List of ToolCall objects that are pending execution
        """
        return self._tool_executor.get_pending_tool_calls()'''

content = re.sub(get_pending_pattern, get_pending_replacement, content, flags=re.DOTALL)

# Replace has_pending_tool_calls
has_pending_pattern = r'    def has_pending_tool_calls\(self\) -> bool:.*?return .*?\n'

has_pending_replacement = '''    def has_pending_tool_calls(self) -> bool:
        """Check if there are any pending tool calls.

        Returns:
            True if there are pending tool calls
        """
        return self._tool_executor.has_pending_tool_calls()
'''

content = re.sub(has_pending_pattern, has_pending_replacement, content, flags=re.DOTALL)

# Replace resolve_pending_tool_calls
resolve_pending_pattern = r'    async def resolve_pending_tool_calls\(self\) -> AsyncIterator\[ToolMessage\]:.*?(?=\n    # async def resolve_pending_tool_calls)'

resolve_pending_replacement = '''    async def resolve_pending_tool_calls(self) -> AsyncIterator[ToolMessage]:
        """Find and execute all pending tool calls in conversation.

        Yields:
            ToolMessage for each resolved tool call
        """
        async for msg in self._tool_executor.resolve_pending_tool_calls():
            yield msg

'''

content = re.sub(resolve_pending_pattern, resolve_pending_replacement, content, flags=re.DOTALL)

# Write back
with open("src/good_agent/agent.py", "w") as f:
    f.write(content)

print("Replaced tool methods in agent.py")

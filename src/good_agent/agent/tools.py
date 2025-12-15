"""ToolExecutor manages tool execution, parallel invocation, and pending tool call resolution."""

import contextlib
import logging
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from typing import TYPE_CHECKING, Any, TypeVar, cast, overload

import orjson
from ulid import ULID

from good_agent.events import AgentEvents
from good_agent.messages import AssistantMessage, ToolMessage
from good_agent.tools import (
    BoundTool,
    Tool,
    ToolCall,
    ToolCallFunction,
    ToolResponse,
)

if TYPE_CHECKING:
    from good_agent.agent import Agent

logger = logging.getLogger(__name__)

T_FuncResp = TypeVar("T_FuncResp")


class ToolExecutor:
    """Manages tool execution lifecycle including invocation and pending call resolution.

    Handles:
    - Direct tool invocation with parameter rendering
    - Parallel tool execution
    - Pending tool call resolution
    - Tool error handling and event emission
    """

    def __init__(self, agent: Agent) -> None:
        """Initialize ToolExecutor.

        Args:
            agent: Parent Agent instance
        """
        self.agent = agent

    def _format_tool_message_content(self, tool_response: ToolResponse) -> str:
        """Render tool responses into message content strings."""

        if not tool_response.success:
            return f"Error: {tool_response.error}"

        if hasattr(tool_response.response, "render") and callable(  # type: ignore[attr-defined]
            tool_response.response.render  # type: ignore[attr-defined]
        ):
            try:
                return tool_response.response.render()  # type: ignore[call-arg]
            except Exception:  # pragma: no cover - defensive fallback
                return str(tool_response.response)

        return str(tool_response.response)

    @overload
    async def invoke(
        self,
        tool: Tool[..., T_FuncResp] | BoundTool[Any, Any, T_FuncResp],
        *,
        tool_name: str | None = None,
        tool_call_id: str | None = None,
        skip_assistant_message: bool = False,
        **parameters: Any,
    ) -> ToolResponse[T_FuncResp]: ...

    @overload
    async def invoke(
        self,
        tool: str,
        *,
        tool_name: str | None = None,
        tool_call_id: str | None = None,
        skip_assistant_message: bool = False,
        **parameters: Any,
    ) -> ToolResponse: ...

    @overload
    async def invoke(
        self,
        tool: Callable[..., Awaitable[T_FuncResp]],
        *,
        tool_name: str | None = None,
        tool_call_id: str | None = None,
        skip_assistant_message: bool = False,
        **parameters: Any,
    ) -> ToolResponse[T_FuncResp]: ...

    async def invoke(
        self,
        tool: Tool | Callable | str,
        *,
        tool_name: str | None = None,
        tool_call_id: str | None = None,
        skip_assistant_message: bool = False,
        hide: list[str] | None = None,
        **parameters: Any,
    ) -> ToolResponse:
        """Directly invoke a tool and add messages to conversation.

        Args:
            tool: Tool instance, callable, or tool name string
            tool_name: Optional name override
            tool_call_id: Optional tool call ID (generated if not provided)
            skip_assistant_message: If True, only add tool response
            hide: List of parameter names to hide from tool definition
            **parameters: Parameters to pass to the tool

        Returns:
            ToolResponse with execution result
        """
        # Render any Template parameters with agent context
        rendered_params = await self.agent._render_template_parameters(parameters)

        # Resolve tool if string name provided
        resolved_tool, resolved_name = self._resolve_tool(tool_name, tool, hide)

        logger.debug(f"Invoking tool: {resolved_name} with params: {rendered_params}")

        # Generate tool call ID if not provided
        tool_call_id = tool_call_id or f"call_{ULID()}"

        # Separate visible and hidden parameters
        visible_params = {
            key: value
            for key, value in rendered_params.items()
            if key not in {"_agent", "_tool_call"}
        }
        hidden_param_set: set[str] = set()
        if isinstance(resolved_tool, Tool) and hasattr(resolved_tool, "_hidden_params"):
            hidden_param_set = set(resolved_tool._hidden_params)
        if hide:
            hidden_param_set = hidden_param_set.union(hide)
        for hidden_param in hidden_param_set:
            visible_params.pop(hidden_param, None)

        # Create tool call with only visible parameters
        tool_call = ToolCall(
            id=tool_call_id,
            type="function",
            function=ToolCallFunction(
                name=resolved_name,
                arguments=orjson.dumps(visible_params).decode("utf-8"),
            ),
        )

        # Emit tool:call event with visible parameters only
        ctx = await self.agent.events.apply(
            AgentEvents.TOOL_CALL_BEFORE,
            tool_name=resolved_name,
            parameters=visible_params,
            tool_call_id=tool_call_id,
        )

        # Use potentially modified parameters from apply hook
        modified_params = (
            ctx.return_value
            if ctx.return_value is not None
            else ctx.parameters.get("parameters", visible_params)
        )

        # Merge modified visible params with hidden params for execution
        execution_params = dict(rendered_params)
        execution_params.update(modified_params)

        # Execute the tool
        try:
            # Coerce JSON-like strings to proper types based on tool schema
            execution_params = self._coerce_tool_parameters(resolved_tool, execution_params)

            # Remove special parameters if they're in execution_params to avoid duplicates
            execution_params.pop("_agent", None)
            execution_params.pop("_tool_call", None)

            result = await resolved_tool(
                **execution_params, _agent=self.agent, _tool_call=tool_call
            )

            # Handle different return types
            if isinstance(result, ToolResponse):
                tool_response = ToolResponse(
                    tool_name=resolved_name,
                    tool_call_id=tool_call_id,
                    response=result.response,
                    parameters=result.parameters or visible_params,
                    success=result.success,
                    error=result.error,
                )
            else:
                tool_response = ToolResponse(
                    tool_name=resolved_name,
                    tool_call_id=tool_call_id,
                    response=result,
                    parameters=visible_params,
                    success=True,
                    error=None,
                )

            # Emit event based on success status
            if tool_response.success:
                self.agent.do(
                    AgentEvents.TOOL_CALL_AFTER,
                    tool_name=resolved_name,
                    tool_call_id=tool_call_id,
                    response=tool_response,  # Pass the full ToolResponse object
                    parameters=visible_params,
                    success=True,
                )
            else:
                self.agent.do(
                    AgentEvents.TOOL_CALL_ERROR,
                    tool_name=resolved_name,
                    tool_call_id=tool_call_id,
                    error=tool_response.error,
                    parameters=visible_params,
                )

        except Exception as e:
            logger.exception(f"Error invoking tool {resolved_name}: {e}")
            tool_response = ToolResponse(
                tool_name=resolved_name,
                tool_call_id=tool_call_id,
                response=None,
                parameters=visible_params,
                success=False,
                error=str(e),
            )

            # Emit error event
            self.agent.do(
                AgentEvents.TOOL_CALL_ERROR,
                tool_name=resolved_name,
                tool_call_id=tool_call_id,
                error=str(e),
                parameters=visible_params,
            )

        # Add assistant message with tool call if not skipped
        if not skip_assistant_message:
            assistant_message = self.agent.model.create_message(
                content="",
                role="assistant",
                tool_calls=[tool_call],
            )
            self.agent.append(assistant_message)

        # Create and add tool message
        tool_message = self.agent.model.create_message(
            content=self._format_tool_message_content(tool_response),
            tool_call_id=tool_call_id,
            tool_name=resolved_name,
            tool_response=tool_response,
            role="tool",
        )
        self.agent.append(tool_message)

        return tool_response

    async def invoke_many(
        self,
        invocations: Sequence[tuple[Tool | str | Callable, dict[str, Any]]],
    ) -> list[ToolResponse]:
        """Execute multiple tools in parallel.

        Args:
            invocations: Sequence of (tool, parameters) tuples

        Returns:
            List of ToolResponse objects in invocation order
        """
        if not invocations:
            return []

        # Build tool calls and prepare execution tasks
        tool_calls = []
        tasks = []
        tool_infos = []

        for tool_ref, params in invocations:
            # Render any Template parameters
            rendered_params = await self.agent._render_template_parameters(params)

            # Resolve tool - handle errors gracefully
            tool = None
            tool_error = None

            try:
                tool_name = self._resolve_tool_name(tool_ref)
            except ValueError as e:
                tool_name = str(tool_ref)
                tool_error = str(e)

            if not tool_error:
                if isinstance(tool_ref, str):
                    if tool_ref in self.agent.tools:
                        tool = self.agent.tools[tool_ref]
                    else:
                        tool_error = f"Tool '{tool_ref}' not found in agent's tools"
                elif isinstance(tool_ref, Tool):
                    tool = tool_ref
                elif callable(tool_ref):
                    if getattr(tool_ref, "_is_invoke_func_bound", False):
                        # Type ignore needed because we're handling a special bound function case
                        tool = tool_ref  # type: ignore[assignment]
                        tool_name = getattr(tool_ref, "__name__", "bound_invoke")
                    else:
                        try:
                            tool = Tool(tool_ref)
                        except Exception as e:
                            tool_error = f"Failed to convert function to tool: {e}"

            # Create tool call
            tool_call_id = f"call_{ULID()}"
            tool_call = ToolCall(
                id=tool_call_id,
                type="function",
                function=ToolCallFunction(
                    name=tool_name,
                    arguments=orjson.dumps(rendered_params).decode("utf-8"),
                ),
            )

            tool_calls.append(tool_call)
            tool_infos.append((tool, tool_name, tool_call_id, tool_call, tool_error))

            # Determine whether we need to route through bound invoke_func
            is_bound_invoke = getattr(tool_ref, "_is_invoke_func_bound", False)

            # Create execution task
            async def execute_tool(
                t=tool,
                p=rendered_params,
                tid=tool_call_id,
                tn=tool_name,
                tc=tool_call,
                error=tool_error,
                is_bound=is_bound_invoke,
            ):
                if error:
                    return ToolResponse(
                        tool_name=tn,
                        tool_call_id=tid,
                        response=None,
                        parameters=p,
                        success=False,
                        error=error,
                    )

                try:
                    if t is None:
                        return ToolResponse(
                            tool_name=tn,
                            tool_call_id=tid,
                            response=None,
                            parameters=p,
                            success=False,
                            error=f"Tool '{tn}' not found",
                        )

                    # Coerce parameters
                    execution_params = self._coerce_tool_parameters(t, p)

                    if is_bound:
                        # Route through bound invoke_func helper so hidden params merge properly
                        bound_callable = cast(Callable[..., Awaitable[ToolResponse]], t)
                        result = await bound_callable(
                            **execution_params,
                            _agent=self.agent,
                            _from_invoke_many=True,
                            _tool_call_id=tid,
                            _tool_call=tc,
                        )
                    else:
                        # Execute tool
                        result = await t(**execution_params, _agent=self.agent, _tool_call=tc)

                    # Handle return types
                    if isinstance(result, ToolResponse):
                        merged_params = result.parameters or execution_params
                        merged_params = {
                            k: v
                            for k, v in merged_params.items()
                            if k not in {"_agent", "_tool_call"}
                        }
                        if not result.tool_call_id:
                            result.tool_call_id = tid
                        return ToolResponse(
                            tool_name=tn,
                            tool_call_id=tid,
                            response=result.response,
                            parameters=merged_params,
                            success=result.success,
                            error=result.error,
                        )
                    else:
                        visible_params = {
                            k: v
                            for k, v in execution_params.items()
                            if k not in {"_agent", "_tool_call"}
                        }
                        return ToolResponse(
                            tool_name=tn,
                            tool_call_id=tid,
                            response=result,
                            parameters=visible_params,
                            success=True,
                            error=None,
                        )

                except Exception as e:
                    logger.exception(f"Error executing tool {tn}: {e}")
                    return ToolResponse(
                        tool_name=tn,
                        tool_call_id=tid,
                        response=None,
                        parameters=p,
                        success=False,
                        error=str(e),
                    )

            tasks.append(execute_tool())

        # Add assistant message with all tool calls
        assistant_message = self.agent.model.create_message(
            content="",
            role="assistant",
            tool_calls=tool_calls,
        )
        self.agent.append(assistant_message)

        # Execute all tools in parallel
        import asyncio

        results = await asyncio.gather(*tasks)

        # Add tool messages for all results (preserve tool_call_id ordering)
        pending_tool_call_ids = [tc.id for tc in tool_calls]

        for tool_response in results:
            if tool_response.tool_call_id in (None, "") and pending_tool_call_ids:
                tool_response.tool_call_id = pending_tool_call_ids.pop(0)
            elif tool_response.tool_call_id and tool_response.tool_call_id in pending_tool_call_ids:
                pending_tool_call_ids.remove(tool_response.tool_call_id)

            tool_message = self.agent.model.create_message(
                content=self._format_tool_message_content(tool_response),
                tool_call_id=tool_response.tool_call_id,
                tool_name=tool_response.tool_name,
                tool_response=tool_response,
                parameters=tool_response.parameters,
                role="tool",
            )
            self.agent.append(tool_message)

            # Emit events
            if tool_response.success:
                self.agent.do(
                    AgentEvents.TOOL_CALL_AFTER,
                    tool_name=tool_response.tool_name,
                    tool_call_id=tool_response.tool_call_id,
                    response=tool_response,  # Pass the full ToolResponse object
                    parameters=tool_response.parameters,
                    success=tool_response.success,
                )
            else:
                self.agent.do(
                    AgentEvents.TOOL_CALL_ERROR,
                    tool_name=tool_response.tool_name,
                    tool_call_id=tool_response.tool_call_id,
                    error=tool_response.error,
                    parameters=tool_response.parameters,
                )

        return results

    def invoke_func(
        self,
        tool: Tool | str | Callable,
        *,
        tool_name: str | None = None,
        hide: list[str] | None = None,
        tool_call_id: str | None = None,
        **bound_parameters: Any,
    ) -> Callable[..., Awaitable[ToolResponse]]:
        """Create a bound function that invokes a tool with preset parameters."""

        resolved_name = tool_name

        if not resolved_name:
            if isinstance(tool, str):
                resolved_name = tool
            elif isinstance(tool, Tool):
                resolved_name = tool.name
            elif callable(tool):
                resolved_name = getattr(tool, "__name__", str(tool))
            logger.debug("Resolved tool name: %s", resolved_name)

        async def bound_invoke(**kwargs: Any) -> ToolResponse:
            from_invoke_many = kwargs.pop("_from_invoke_many", False)
            runtime_tool_call_id = kwargs.pop("_tool_call_id", None)
            tool_call = kwargs.pop("_tool_call", None)

            explicit_tool_call_id = runtime_tool_call_id or tool_call_id

            all_params = dict(bound_parameters)
            for key, value in kwargs.items():
                if key in {"_agent", "_tool_call"}:
                    continue
                all_params[key] = value

            if from_invoke_many:
                actual_tool: Tool | Callable[..., Awaitable[Any]] | None = tool  # type: ignore[assignment]
                if isinstance(tool, str):
                    try:
                        actual_tool = self.agent.tools[tool]
                    except KeyError as exc:  # pragma: no cover - defensive
                        raise ValueError(f"Tool '{tool}' not found") from exc
                elif not isinstance(tool, Tool):
                    actual_tool = Tool(tool)

                assert callable(actual_tool), "Resolved tool is not callable"

                result = await actual_tool(
                    **all_params,
                    _agent=self.agent,
                    _tool_call=tool_call,
                )

                if isinstance(result, ToolResponse):
                    if explicit_tool_call_id:
                        result.tool_call_id = explicit_tool_call_id
                    return result

                return ToolResponse(
                    tool_name=resolved_name or getattr(actual_tool, "name", str(tool)),
                    tool_call_id=explicit_tool_call_id or "",
                    response=result,
                    parameters=all_params,
                    success=True,
                    error=None,
                )

            return await self.invoke(
                tool,
                tool_name=resolved_name,
                tool_call_id=explicit_tool_call_id,
                hide=hide,
                **all_params,
            )

        bound_invoke.__name__ = resolved_name or getattr(tool, "__name__", str(tool))
        bound_invoke._is_invoke_func_bound = True  # type: ignore[attr-defined]
        bound_invoke._bound_tool = tool  # type: ignore[attr-defined]
        bound_invoke._bound_parameters = bound_parameters  # type: ignore[attr-defined]
        bound_invoke._hide_params = hide  # type: ignore[attr-defined]

        return bound_invoke

    def invoke_many_func(
        self,
        invocations: Sequence[tuple[Tool | str | Callable, dict[str, Any]]],
    ) -> Callable[[], Awaitable[list[ToolResponse]]]:
        """Create a bound coroutine that executes a batch of tool invocations."""

        async def bound_invoke_many() -> list[ToolResponse]:
            return await self.invoke_many(invocations)

        return bound_invoke_many

    async def resolve_pending_tool_calls(self) -> AsyncIterator[ToolMessage]:
        """Find and execute all pending tool calls in conversation.

        Yields:
            ToolMessage for each resolved tool call
        """
        pending = self.get_pending_tool_calls()
        for tool_call in pending:
            tool_name = tool_call.function.name

            if tool_name not in self.agent.tools:
                logger.warning(f"Tool '{tool_name}' not found for pending tool call {tool_call.id}")

                # Create error response
                tool_response = ToolResponse(
                    tool_name=tool_name,
                    tool_call_id=tool_call.id,
                    response=None,
                    parameters=tool_call.parameters,
                    success=False,
                    error=f"Tool '{tool_name}' not found",
                )

                # Create and add tool message for the error
                tool_message = self.agent.model.create_message(
                    content=self._format_tool_message_content(tool_response),
                    tool_call_id=tool_call.id,
                    tool_name=tool_name,
                    tool_response=tool_response,
                    role="tool",
                )
                self.agent.append(tool_message)

                # Emit error event
                self.agent.do(
                    AgentEvents.TOOL_CALL_ERROR,
                    tool_name=tool_name,
                    tool_call_id=tool_call.id,
                    error=tool_response.error,
                    parameters=tool_call.parameters,
                )
                yield tool_message
            else:
                tool_response = await self.invoke(
                    tool_name,
                    tool_call_id=tool_call.id,
                    skip_assistant_message=True,
                    **tool_call.parameters,
                )

                tool_message = self.agent.tool[-1]
                assert tool_message.tool_call_id == tool_call.id
                yield tool_message

    def record_invocation(
        self,
        tool: Tool | Callable | str,
        response: ToolResponse | Any,
        parameters: dict[str, Any] | None = None,
        *,
        tool_call_id: str | None = None,
        skip_assistant_message: bool = False,
    ) -> None:
        """Record a single tool invocation without executing the tool."""

        tool_name = self._resolve_tool_name(tool)
        tool_call_id = tool_call_id or f"call_{ULID()}"
        tool_response = self._coerce_tool_response(response, tool_name, tool_call_id, parameters)
        visible_params = parameters or tool_response.parameters or {}

        if not skip_assistant_message:
            existing_tool_call = False
            for msg in reversed(self.agent._messages):
                match msg:
                    case AssistantMessage(tool_calls=tool_calls) if tool_calls:
                        for tc in tool_calls:
                            if tc.id == tool_call_id:
                                existing_tool_call = True
                                break
                        if existing_tool_call:
                            break
                    case _:
                        continue

            if not existing_tool_call:
                tool_call = ToolCall(
                    id=tool_call_id,
                    type="function",
                    function=ToolCallFunction(
                        name=tool_name,
                        arguments=orjson.dumps(visible_params).decode("utf-8"),
                    ),
                )
                assistant_msg = self.agent.model.create_message(
                    content="",
                    tool_calls=[tool_call],
                    role="assistant",
                )
                self.agent.append(assistant_msg)

        tool_msg = self.agent.model.create_message(
            content=self._format_tool_message_content(tool_response),
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            tool_response=tool_response,
            role="tool",
        )
        self.agent.append(tool_msg)

        self.agent.do(
            AgentEvents.TOOL_CALL_AFTER,
            tool_name=tool_name,
            tool_call_id=tool_call_id,
            response=tool_response,
            success=tool_response.success,
        )

    def record_invocations(
        self,
        tool: Tool | Callable | str,
        invocations: Sequence[tuple[dict[str, Any], ToolResponse | Any]],
        *,
        skip_assistant_message: bool = False,
    ) -> None:
        """Record multiple tool invocations, consolidating when possible."""

        if not invocations:
            return

        tool_name = self._resolve_tool_name(tool)
        supports_parallel = self.agent.model.supports_parallel_function_calling()
        tool_call_ids: list[str] = []
        tool_calls: list[ToolCall] = []

        if not skip_assistant_message:
            if supports_parallel:
                for parameters, _ in invocations:
                    tool_call_id = f"call_{ULID()}"
                    tool_call_ids.append(tool_call_id)
                    tool_call = ToolCall(
                        id=tool_call_id,
                        type="function",
                        function=ToolCallFunction(
                            name=tool_name,
                            arguments=orjson.dumps(parameters).decode("utf-8"),
                        ),
                    )
                    tool_calls.append(tool_call)

                assistant_msg = self.agent.model.create_message(
                    content="",
                    tool_calls=tool_calls,
                    role="assistant",
                )
                self.agent.append(assistant_msg)
            else:
                for parameters, response in invocations:
                    self.record_invocation(
                        tool,
                        response,
                        parameters,
                        skip_assistant_message=False,
                    )
                return
        else:
            for _ in invocations:
                tool_call_ids.append(f"call_{ULID()}")

        for index, (parameters, response) in enumerate(invocations):
            tool_call_id = tool_call_ids[index] if tool_call_ids else f"call_{ULID()}"
            tool_response = self._coerce_tool_response(
                response, tool_name, tool_call_id, parameters
            )

            tool_msg = self.agent.model.create_message(
                content=self._format_tool_message_content(tool_response),
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                tool_response=tool_response,
                role="tool",
            )
            self.agent.append(tool_msg)

            self.agent.do(
                AgentEvents.TOOL_CALL_AFTER,
                tool_name=tool_name,
                tool_call_id=tool_call_id,
                response=tool_response,
                success=tool_response.success,
            )

    def get_pending_tool_calls(self) -> list[ToolCall]:
        """Get list of tool calls that don't have corresponding responses.

        Returns:
            List of ToolCall objects that are pending execution
        """
        from good_agent.messages import AssistantMessage, ToolMessage

        pending_calls = []
        resolved_call_ids = set()

        # Collect all resolved tool call IDs
        for msg in self.agent.messages:
            if isinstance(msg, ToolMessage) and msg.tool_call_id:
                resolved_call_ids.add(msg.tool_call_id)

        # Find assistant messages with unresolved tool calls
        for msg in self.agent.messages:
            if isinstance(msg, AssistantMessage) and msg.tool_calls:
                for tool_call in msg.tool_calls:
                    if tool_call.id not in resolved_call_ids:
                        pending_calls.append(tool_call)

        return pending_calls

    def has_pending_tool_calls(self) -> bool:
        """Check if there are any pending tool calls.

        Returns:
            True if there are pending tool calls
        """
        return len(self.get_pending_tool_calls()) > 0

    # Helper methods

    def _coerce_tool_response(
        self,
        response: ToolResponse | Any,
        tool_name: str,
        tool_call_id: str,
        parameters: dict[str, Any] | None = None,
    ) -> ToolResponse:
        """Convert arbitrary responses into :class:`ToolResponse` objects."""

        if not isinstance(response, ToolResponse):
            return ToolResponse(
                tool_name=tool_name,
                tool_call_id=tool_call_id,
                response=response,
                parameters=parameters if parameters is not None else {},
                success=True,
                error=None,
            )

        return ToolResponse(
            tool_name=response.tool_name or tool_name,
            tool_call_id=response.tool_call_id or tool_call_id,
            response=response.response,
            parameters=response.parameters if parameters is None else parameters,
            success=response.success,
            error=response.error,
        )

    def _resolve_tool_name(self, tool: Tool | Callable | str) -> str:
        """Resolve tool name from various input types.

        Args:
            tool: Tool instance, callable, or string name

        Returns:
            Resolved tool name

        Raises:
            ValueError: If tool name cannot be determined
        """
        if isinstance(tool, str):
            return tool
        elif isinstance(tool, Tool):
            # Tool instances have a name property
            return str(tool.name) if hasattr(tool, "name") else str(tool)
        elif callable(tool):
            if hasattr(tool, "__name__"):
                return str(tool.__name__)
            else:
                raise ValueError(f"Cannot determine name for callable: {tool}")
        else:
            raise ValueError(f"Invalid tool type: {type(tool)}")

    def _resolve_tool(
        self,
        tool_name: str | None,
        tool: Tool | Callable | str,
        hide: list[str] | None = None,
    ) -> tuple[Tool | Callable, str]:
        """Resolve tool instance and name from inputs.

        Args:
            tool_name: Optional explicit tool name
            tool: Tool instance, callable, or string name
            hide: Optional list of parameters to hide

        Returns:
            Tuple of (resolved_tool, resolved_name)
        """
        if isinstance(tool, str):
            if tool not in self.agent.tools:
                raise ValueError(f"Tool '{tool}' not found in agent's tools")
            resolved_tool = self.agent.tools[tool]
            resolved_name = tool_name or tool
        elif isinstance(tool, Tool):
            resolved_tool = tool
            resolved_name = tool_name or str(tool.name)
        elif callable(tool):
            # Convert callable to Tool if not already
            resolved_tool = Tool(tool, hidden_params=hide or [])
            resolved_name = tool_name or str(getattr(tool, "__name__", "unknown"))
        else:
            raise ValueError(f"Invalid tool type: {type(tool)}")

        return resolved_tool, resolved_name

    def _coerce_tool_parameters(
        self, tool: Tool | Callable, parameters: dict[str, Any]
    ) -> dict[str, Any]:
        """Coerce JSON-like string parameters to proper types based on tool schema.

        Args:
            tool: Tool instance or callable
            parameters: Raw parameters dict

        Returns:
            Coerced parameters dict
        """
        if not isinstance(tool, Tool):
            return parameters

        # Get tool schema to understand expected types
        # Tool might not have get_schema method, check first
        if not hasattr(tool, "get_schema"):
            return parameters

        schema = tool.get_schema()  # type: ignore[attr-defined]
        if "parameters" not in schema:
            return parameters

        coerced = dict(parameters)
        param_schemas = schema["parameters"].get("properties", {})

        # Debug: print parameter schemas
        # import json
        # print(f"DEBUG: Coercing parameters for tool. Schema params: {json.dumps(param_schemas, indent=2)}")

        # Helper to resolve nested tool schemas
        def _resolve_tool_for_schema(t: Any) -> Any:
            if isinstance(t, Tool):
                return t.get_schema()  # type: ignore[attr-defined]
            elif isinstance(t, type) and hasattr(t, "model_json_schema"):
                # For Pydantic models, get schema
                return t.model_json_schema()  # type: ignore[attr-defined]
            return None

        for param_name, param_value in parameters.items():
            if param_name not in param_schemas:
                continue

            param_schema = param_schemas[param_name]

            # Handle string values that should be coerced
            if isinstance(param_value, str):
                # DEBUG
                # print(f"DEBUG: param={param_name} val={param_value} schema={param_schema}")

                # Check if parameter has a type definition
                if "anyOf" in param_schema:
                    # Handle anyOf types (e.g. Optional[T])
                    types = [t.get("type") for t in param_schema["anyOf"]]
                    if "boolean" in types:
                        param_type = "boolean"
                    elif "integer" in types:
                        param_type = "integer"
                    elif "number" in types:
                        param_type = "number"
                    elif "object" in types:
                        param_type = "object"
                    elif "array" in types:
                        param_type = "array"
                    else:
                        # Default to string but try to infer if it looks like JSON
                        param_type = "string"
                        if (
                            (param_value.startswith("{") and param_value.endswith("}"))
                            or (param_value.startswith("[") and param_value.endswith("]"))
                        ) and ("object" in types or "array" in types):
                            # Check if object or array are allowed types in anyOf
                            try:
                                coerced[param_name] = orjson.loads(param_value)
                                # Skip further coercion if successful
                                continue
                            except Exception:
                                pass
                else:
                    param_type = param_schema.get("type")

                # Coerce based on schema type
                if param_type == "boolean":
                    if param_value.lower() in ("true", "1", "yes"):
                        coerced[param_name] = True
                    elif param_value.lower() in ("false", "0", "no"):
                        coerced[param_name] = False
                elif param_type == "integer":
                    with contextlib.suppress(ValueError):
                        coerced[param_name] = int(param_value)
                elif param_type == "number":
                    with contextlib.suppress(ValueError):
                        coerced[param_name] = float(param_value)
                elif param_type in ("object", "array"):
                    with contextlib.suppress(Exception):
                        coerced[param_name] = orjson.loads(param_value)
                # Some tools define dict parameters as simply 'type: object' without Pydantic definition
                elif param_type == "object":
                    try:
                        parsed = orjson.loads(param_value)
                        if isinstance(parsed, dict):
                            coerced[param_name] = parsed
                    except Exception:
                        pass
                elif param_type == "array":
                    try:
                        parsed = orjson.loads(param_value)
                        if isinstance(parsed, list):
                            coerced[param_name] = parsed
                    except Exception:
                        pass

                # Fallback: If schema has type=object or type=array but wasn't caught above
                # e.g. because it wasn't processed correctly
                elif param_schema.get("type") in ("object", "array") and (
                    (param_value.startswith("{") and param_value.endswith("}"))
                    or (param_value.startswith("[") and param_value.endswith("]"))
                ):
                    with contextlib.suppress(Exception):
                        coerced[param_name] = orjson.loads(param_value)
                # Handle simple types that might be wrapped in anyOf
                # Or handle generic string inputs that look like JSON but have no explicit type (or unknown type)
                elif (param_value.startswith("{") and param_value.endswith("}")) or (
                    param_value.startswith("[") and param_value.endswith("]")
                ):
                    # If no type constraint is strictly against it, try parsing
                    # (This is aggressive but needed for some LLM outputs that send JSON strings for everything)
                    try:
                        parsed = orjson.loads(param_value)
                        # Only coerce if it looks like a complex type (dict/list)
                        if isinstance(parsed, (dict, list)):
                            # Check if schema allows this structure
                            should_coerce = False

                            # Case 1: Schema is ambiguous (no type specified)
                            if (
                                "type" not in param_schema
                                or param_schema.get("type") in ("object", "array")
                                or "anyOf" in param_schema
                                or "oneOf" in param_schema
                            ):
                                should_coerce = True
                            # Case 4: Schema says string but it looks like JSON (risky but sometimes needed)
                            # Some LLMs output JSON even for string fields if they think it should be structured.
                            # However, forcing dict->str can break validation if Pydantic expects str.
                            # But if we don't coerce, it remains a string (which is fine for str fields).
                            # So we ONLY coerce if we think it's NOT supposed to be a string.
                            elif param_schema.get("type") == "string":
                                # Don't coerce to dict/list if schema explicitly wants a string
                                should_coerce = False

                            if should_coerce:
                                coerced[param_name] = parsed
                    except Exception:
                        pass

        return coerced

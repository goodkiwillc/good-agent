import pytest
from good_agent import Agent, AgentEvents
from good_agent.messages import RenderMode, UserMessage
from good_agent.utilities.event_router import EventContext


@pytest.mark.asyncio
class TestAgentRenderEvents:
    """Test the MESSAGE_RENDER_BEFORE and MESSAGE_RENDER_AFTER events."""

    async def test_render_before_event_triggered(self):
        """Test that MESSAGE_RENDER_BEFORE event is triggered during render."""
        events_captured = []

        async with Agent("Test") as agent:
            # Register handler for RENDER_BEFORE
            @agent.on(AgentEvents.MESSAGE_RENDER_BEFORE)
            def capture_render_before(ctx: EventContext) -> None:
                from good_agent.content import TextContentPart

                output = ctx.parameters["output"]
                # Extract text from content parts
                content_text = (
                    output[0].text
                    if isinstance(output[0], TextContentPart)
                    else str(output[0])
                )
                events_captured.append(
                    {
                        "event": "RENDER_BEFORE",
                        "message_id": ctx.parameters["message"].id,
                        "mode": ctx.parameters["mode"],
                        "content": content_text,
                    }
                )

            # Add a message
            agent.user.append("Hello world")
            msg = agent.messages[-1]  # Get the last message

            # Render the message
            rendered = msg.render(RenderMode.DISPLAY)

            # Verify event was triggered
            assert len(events_captured) == 1
            assert events_captured[0]["event"] == "RENDER_BEFORE"
            assert events_captured[0]["message_id"] == msg.id
            assert events_captured[0]["mode"] == RenderMode.DISPLAY
            assert events_captured[0]["content"] == "Hello world"
            assert rendered == "Hello world"

    async def test_render_before_can_modify_content(self):
        """Test that RENDER_BEFORE handlers can modify the rendered content."""
        async with Agent("Test") as agent:
            # Register handler that modifies content
            @agent.on(AgentEvents.MESSAGE_RENDER_BEFORE)
            def modify_content(ctx: EventContext) -> None:
                from good_agent.content import TextContentPart

                # Transform content parts to uppercase
                output = ctx.parameters["output"]
                modified_parts = []
                for part in output:
                    if isinstance(part, TextContentPart):
                        modified_parts.append(TextContentPart(text=part.text.upper()))
                    else:
                        modified_parts.append(part)
                ctx.parameters["output"] = modified_parts

            # Add a message
            agent.user.append("hello world")
            msg = agent.messages[-1]  # Get the last message

            # Render the message
            rendered = msg.render(RenderMode.DISPLAY)

            # Verify content was modified
            assert rendered == "HELLO WORLD"
            # Original text content part should be unchanged
            assert msg.content_parts[0].text == "hello world"

    async def test_render_after_event_triggered(self):
        """Test that MESSAGE_RENDER_AFTER event is triggered after render."""
        events_captured = []

        async with Agent("Test") as agent:
            # Register handler for RENDER_AFTER
            @agent.on(AgentEvents.MESSAGE_RENDER_AFTER)
            def capture_render_after(ctx: EventContext) -> None:
                events_captured.append(
                    {
                        "event": "RENDER_AFTER",
                        "message_id": ctx.parameters["message"].id,
                        "mode": ctx.parameters["mode"],
                        "rendered_content": ctx.parameters["rendered_content"],
                    }
                )

            # Add a message
            agent.user.append("Test message")
            msg = agent.messages[-1]  # Get the last message

            # Render the message
            rendered = msg.render(RenderMode.LLM)

            # Verify event was triggered
            assert len(events_captured) == 1
            assert events_captured[0]["event"] == "RENDER_AFTER"
            assert events_captured[0]["message_id"] == msg.id
            assert events_captured[0]["mode"] == RenderMode.LLM
            assert events_captured[0]["rendered_content"] == rendered

    async def test_render_after_cannot_modify_content(self):
        """Test that RENDER_AFTER handlers cannot modify rendered content."""
        async with Agent("Test") as agent:
            # Register handler that tries to modify content
            @agent.on(AgentEvents.MESSAGE_RENDER_AFTER)
            def try_modify(ctx: EventContext) -> None:
                # This should not affect the returned content
                ctx.parameters["rendered_content"] = "MODIFIED"

            # Add a message
            agent.user.append("Original content")
            msg = agent.messages[-1]  # Get the last message

            # Render the message
            rendered = msg.render(RenderMode.DISPLAY)

            # Verify content was NOT modified
            assert rendered == "Original content"

    async def test_multiple_render_before_handlers(self):
        """Test that multiple RENDER_BEFORE handlers are applied in order."""
        async with Agent("Test") as agent:
            # Register multiple handlers
            @agent.on(AgentEvents.MESSAGE_RENDER_BEFORE)
            def add_prefix(ctx: EventContext) -> None:
                from good_agent.content import TextContentPart

                output = ctx.parameters["output"]
                modified_parts = []
                for part in output:
                    if isinstance(part, TextContentPart):
                        modified_parts.append(
                            TextContentPart(text=f"[PREFIX] {part.text}")
                        )
                    else:
                        modified_parts.append(part)
                ctx.parameters["output"] = modified_parts

            @agent.on(AgentEvents.MESSAGE_RENDER_BEFORE)
            def add_suffix(ctx: EventContext) -> None:
                from good_agent.content import TextContentPart

                output = ctx.parameters["output"]
                modified_parts = []
                for part in output:
                    if isinstance(part, TextContentPart):
                        modified_parts.append(
                            TextContentPart(text=f"{part.text} [SUFFIX]")
                        )
                    else:
                        modified_parts.append(part)
                ctx.parameters["output"] = modified_parts

            # Add a message
            agent.user.append("content")
            msg = agent.messages[-1]  # Get the last message

            # Render the message
            rendered = msg.render(RenderMode.DISPLAY)

            # Verify both transformations were applied
            assert rendered == "[PREFIX] content [SUFFIX]"

    async def test_render_events_with_different_modes(self):
        """Test that render events work correctly with different render modes."""
        mode_renders = {}

        async with Agent("Test") as agent:

            @agent.on(AgentEvents.MESSAGE_RENDER_BEFORE)
            def mode_specific_transform(ctx: EventContext) -> None:
                from good_agent.content import TextContentPart

                mode = ctx.parameters["mode"]
                output = ctx.parameters["output"]

                modified_parts = []
                for part in output:
                    if isinstance(part, TextContentPart):
                        if mode == RenderMode.LLM:
                            modified_parts.append(
                                TextContentPart(text=f"<llm>{part.text}</llm>")
                            )
                        elif mode == RenderMode.DISPLAY:
                            modified_parts.append(
                                TextContentPart(text=f"**{part.text}**")
                            )
                        else:
                            # No transformation for RAW
                            modified_parts.append(part)
                    else:
                        modified_parts.append(part)
                ctx.parameters["output"] = modified_parts

            # Add a message
            agent.user.append("test")
            msg = agent.messages[-1]  # Get the last message

            # Test different render modes
            mode_renders[RenderMode.LLM] = msg.render(RenderMode.LLM)
            mode_renders[RenderMode.DISPLAY] = msg.render(RenderMode.DISPLAY)
            mode_renders[RenderMode.RAW] = msg.render(RenderMode.RAW)

            assert mode_renders[RenderMode.LLM] == "<llm>test</llm>"
            assert mode_renders[RenderMode.DISPLAY] == "**test**"
            assert mode_renders[RenderMode.RAW] == "'test'"  # RAW mode includes quotes

    async def test_render_events_with_assistant_message(self):
        """Test render events with assistant messages containing tool calls."""
        from good_agent.tools import ToolCall, ToolCallFunction

        async with Agent("Test") as agent:
            events = []

            @agent.on(AgentEvents.MESSAGE_RENDER_BEFORE)
            def capture_event(ctx: EventContext) -> None:
                events.append(
                    {
                        "message_type": type(ctx.parameters["message"]).__name__,
                        "has_tool_calls": bool(
                            getattr(ctx.parameters["message"], "tool_calls", None)
                        ),
                    }
                )

            # Add assistant message with tool calls
            tool_call = ToolCall(
                id="test_id",
                type="function",
                function=ToolCallFunction(
                    name="test_tool", arguments='{"arg": "value"}'
                ),
            )

            agent.assistant.append("", tool_calls=[tool_call])
            msg = agent.messages[-1]  # Get the last message

            # Render should trigger events
            msg.render(RenderMode.LLM)

            assert len(events) == 1
            assert events[0]["message_type"] == "AssistantMessage"
            assert events[0]["has_tool_calls"] is True

    async def test_render_event_exception_handling(self):
        """Test that exceptions in render handlers are handled gracefully."""
        async with Agent("Test") as agent:

            @agent.on(AgentEvents.MESSAGE_RENDER_BEFORE)
            def failing_handler(ctx: EventContext) -> None:
                raise ValueError("Handler error")

            # Add a message
            agent.user.append("Original")
            msg = agent.messages[-1]  # Get the last message

            # Exceptions in handlers are swallowed/handled gracefully
            rendered = msg.render(RenderMode.DISPLAY)
            # Content should still render even with handler exception
            assert "Original" in rendered

    async def test_render_events_not_triggered_without_agent(self):
        """Test that render events aren't triggered for messages without agent."""
        # Create a message directly without agent
        msg = UserMessage(content="Direct message")

        # Render should work but no events
        rendered = msg.render(RenderMode.DISPLAY)
        assert rendered == "Direct message"

    async def test_render_caching_with_events(self):
        """Test that render caching works correctly with event modifications."""
        render_count = {"count": 0}

        async with Agent("Test") as agent:

            @agent.on(AgentEvents.MESSAGE_RENDER_BEFORE)
            def count_renders(ctx: EventContext) -> None:
                from good_agent.content import TextContentPart

                render_count["count"] += 1
                # Add a counter to the content
                output = ctx.parameters["output"]
                modified_parts = []
                for part in output:
                    if isinstance(part, TextContentPart):
                        modified_parts.append(
                            TextContentPart(
                                text=f"{part.text} (render {render_count['count']})"
                            )
                        )
                    else:
                        modified_parts.append(part)
                ctx.parameters["output"] = modified_parts

            agent.user.append("Test")
            msg = agent.messages[-1]  # Get the last message

            # First render
            rendered1 = msg.render(RenderMode.DISPLAY)
            assert rendered1 == "Test (render 1)"

            # Second render - caching prevents re-triggering of events
            rendered2 = msg.render(RenderMode.DISPLAY)
            assert rendered2 == "Test (render 1)"  # Same as cached result

            # Different mode should trigger new render
            rendered3 = msg.render(RenderMode.LLM)
            assert rendered3 == "Test (render 2)"

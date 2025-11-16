from unittest.mock import patch

import pytest
from good_agent.agent import Agent
from good_agent.content import (
    FileContentPart,
    ImageContentPart,
    RenderMode,
    TemplateContentPart,
    TextContentPart,
    is_template,
)
from good_agent.messages import SystemMessage, UserMessage


class TestContentParts:
    """Test v2 content part implementations."""

    def test_text_content_part(self):
        """Test simple text content part."""
        part = TextContentPart(text="Hello world")

        assert part.render(RenderMode.DISPLAY) == "Hello world"
        assert part.render(RenderMode.LLM) == "Hello world"

        # Test serialization
        storage = part.model_dump()
        assert storage["type"] == "text"
        assert storage["text"] == "Hello world"
        assert storage["metadata"] == {}

        # Test LLM format
        llm_format = part.to_llm_format()
        assert llm_format["type"] == "text"
        assert llm_format["text"] == "Hello world"

    def test_template_content_part_without_context(self):
        """Test template content part without context."""
        part = TemplateContentPart(
            template="Hello {{ name }}", context_requirements=["name"]
        )

        # Without context, template renders with empty variables
        assert part.render(RenderMode.DISPLAY) == "Hello "

        # Create a new part for testing with context (avoid cache)
        part2 = TemplateContentPart(
            template="Hello {{ name }}", context_requirements=["name"]
        )

        # With context
        rendered = part2.render(RenderMode.DISPLAY, context={"name": "World"})
        assert rendered == "Hello World"

    def test_template_content_part_with_snapshot(self):
        """Test template with context snapshot."""
        part = TemplateContentPart(
            template="User: {{ user.name }}, Age: {{ user.age }}",
            context_snapshot={"user": {"name": "Alice", "age": 30}},
            context_requirements=["user"],
        )

        # Should use snapshot even without provided context
        rendered = part.render(RenderMode.DISPLAY)
        assert rendered == "User: Alice, Age: 30"

        # Snapshot takes priority over provided context
        rendered = part.render(RenderMode.DISPLAY, context={"user": {"name": "Bob"}})
        assert rendered == "User: Alice, Age: 30"

    def test_template_caching(self):
        """Test template render caching."""
        part = TemplateContentPart(
            template="Static: {{ value }}", context_snapshot={"value": "cached"}
        )

        # First render
        result1 = part.render(RenderMode.DISPLAY)
        assert result1 == "Static: cached"
        assert RenderMode.DISPLAY.value in part.rendered_cache

        # Second render should use cache
        with patch.object(part, "template", "Should not be used"):
            result2 = part.render(RenderMode.DISPLAY)
            assert result2 == "Static: cached"  # From cache

    def test_image_content_part_with_url(self):
        """Test image content part with URL."""
        part = ImageContentPart(
            image_url="https://example.com/image.jpg", detail="high"
        )

        # Display rendering
        assert (
            part.render(RenderMode.DISPLAY) == "[Image: https://example.com/image.jpg]"
        )

        # LLM format
        llm_format = part.to_llm_format()
        assert llm_format["type"] == "image_url"
        assert llm_format["image_url"]["url"] == "https://example.com/image.jpg"
        assert llm_format["image_url"]["detail"] == "high"

    def test_image_content_part_with_base64(self):
        """Test image content part with base64."""
        part = ImageContentPart(image_base64="iVBORw0KGgoAAAANS...", detail="low")

        # Display rendering
        assert part.render(RenderMode.DISPLAY) == "[Image: base64 encoded, detail=low]"

        # LLM format
        llm_format = part.to_llm_format()
        assert llm_format["type"] == "image_url"
        assert "data:image/jpeg;base64," in llm_format["image_url"]["url"]

    def test_file_content_part(self):
        """Test file content part."""
        part = FileContentPart(
            file_path="/path/to/file.txt",
            file_content="File contents",
            mime_type="text/plain",
        )

        # Display rendering
        rendered = part.render(RenderMode.DISPLAY)
        assert "/path/to/file.txt" in rendered or "File contents" in rendered

        # Serialization
        storage = part.model_dump()
        assert storage["type"] == "file"
        assert storage["file_path"] == "/path/to/file.txt"


class TestTemplateDetection:
    """Test template detection logic."""

    def test_detects_variable_syntax(self):
        """Test detection of Jinja2 variable syntax."""
        assert is_template("Hello {{ name }}")
        assert is_template("{{ user.email }}")
        assert is_template("Price: {{ price|currency }}")

    def test_detects_control_structures(self):
        """Test detection of control structures."""
        assert is_template("{% if condition %} yes {% endif %}")
        assert is_template("{% for item in items %}{{ item }}{% endfor %}")

    def test_detects_comments(self):
        """Test detection of comments."""
        assert is_template("{# This is a comment #}")

    def test_detects_line_statements(self):
        """Test detection of line statements."""
        assert is_template("# for item in items")
        assert is_template("  # if user.is_admin")
        assert is_template("# endif")
        assert is_template("""
# for user in users
    Name: {{ user.name }}
# endfor
        """)

    def test_does_not_detect_regular_text(self):
        """Test that regular text is not detected as template."""
        assert not is_template("Hello world")
        assert not is_template("Price: $100")
        assert not is_template("# This is just a comment")
        assert not is_template("# TODO: fix this later")


class TestMessageRendering:
    """Test message rendering with v2 content parts."""

    def test_message_with_single_text_part(self):
        """Test message with single text content part."""
        message = UserMessage(content_parts=[TextContentPart(text="Hello")])

        assert message.render(RenderMode.DISPLAY) == "Hello"
        assert message.__display__() == "Hello"
        assert message.__llm__() == "Hello"

    def test_message_with_multiple_parts(self):
        """Test message with multiple content parts."""
        message = UserMessage(
            content_parts=[
                TextContentPart(text="Part 1"),
                TextContentPart(text="Part 2"),
                TextContentPart(text="Part 3"),
            ]
        )

        # Default render joins with newlines
        assert message.render() == "Part 1\nPart 2\nPart 3"

    def test_message_with_mixed_content_types(self):
        """Test message with different content part types."""
        message = UserMessage(
            content_parts=[
                TextContentPart(text="Check this image:"),
                ImageContentPart(image_url="https://example.com/img.jpg"),
                TextContentPart(text="What do you see?"),
            ]
        )

        rendered = message.render(RenderMode.DISPLAY)
        assert "Check this image:" in rendered
        assert "[Image:" in rendered
        assert "What do you see?" in rendered

    def test_message_with_template_parts(self):
        """Test message with template content parts."""
        message = UserMessage(
            content_parts=[
                TextContentPart(text="Hello"),
                TemplateContentPart(
                    template="{{ greeting }} {{ name }}",
                    context_snapshot={"greeting": "Hi", "name": "Alice"},
                ),
            ]
        )

        rendered = message.render(RenderMode.DISPLAY)
        assert "Hello" in rendered
        assert "Hi Alice" in rendered

    def test_message_composability(self):
        """Test that messages can be composed and rendered."""
        # Create messages with content
        message1 = UserMessage(content_parts=[TextContentPart(text="Inner message")])

        # Messages themselves support the display protocol
        assert hasattr(message1, "__display__")
        assert message1.__display__() == "Inner message"

        # Create a wrapper message that references the first
        message2 = SystemMessage(
            content_parts=[
                TextContentPart(text="System says: " + message1.__display__())
            ]
        )

        result = message2.render(RenderMode.DISPLAY)
        assert "System says: Inner message" in result

    def test_render_caching(self):
        """Test that non-template parts are cached."""
        message = UserMessage(
            content_parts=[
                TextContentPart(text="Static content"),
                TextContentPart(text="More static content"),
            ]
        )

        # First render
        result1 = message.render(RenderMode.LLM)

        # Modify underlying parts (this shouldn't affect cached result in real usage)
        # In v2, content_parts are immutable once set, so caching is safe
        result2 = message.render(RenderMode.LLM)
        assert result1 == result2

    def test_template_parts_not_cached(self):
        """Test that template parts bypass caching when appropriate."""
        # Create agent for template rendering with initial context
        agent = Agent("Test agent", context={"dynamic_value": "initial"})

        # Use agent's append method which will create the message
        agent.append(
            UserMessage(
                content_parts=[
                    TemplateContentPart(
                        template="Value: {{ dynamic_value }}",
                        context_requirements=["dynamic_value"],
                    )
                ]
            )
        )

        # First render (should use agent's context)
        result1 = agent.messages[-1].render(RenderMode.DISPLAY)
        assert "initial" in result1

        # Test that template renders are dynamic (not permanently cached)
        # Create a new agent with different context and similar message
        agent2 = Agent("Test agent", context={"dynamic_value": "updated"})
        agent2.append(
            UserMessage(
                content_parts=[
                    TemplateContentPart(
                        template="Value: {{ dynamic_value }}",
                        context_requirements=["dynamic_value"],
                    )
                ]
            )
        )

        result2 = agent2.messages[-1].render(RenderMode.DISPLAY)
        assert "updated" in result2

        # Verify that the original agent still renders with its context
        result3 = agent.messages[-1].render(RenderMode.DISPLAY)
        assert "initial" in result3


class TestAgentIntegration:
    """Test agent integration with v2 content parts."""

    def test_append_creates_content(self):
        """Test that appending to agent creates appropriate content parts."""
        agent = Agent("Test agent")

        # Append plain text
        agent.append("Plain text message")
        assert len(agent.messages) == 2  # system + user

        user_msg = agent.messages[-1]
        assert len(user_msg.content_parts) == 1
        assert isinstance(user_msg.content_parts[0], TextContentPart)
        assert user_msg.content_parts[0].text == "Plain text message"

    def test_append_detects_templates(self):
        """Test that templates are automatically detected."""
        agent = Agent("Test agent", context={"user_name": "Alice"})

        # Append template string
        agent.append("Hello {{ user_name }}!")

        user_msg = agent.messages[-1]
        assert len(user_msg.content_parts) == 1
        assert isinstance(user_msg.content_parts[0], TemplateContentPart)
        assert user_msg.content_parts[0].template == "Hello {{ user_name }}!"

    def test_append_multiple_content(self):
        """Test appending multiple content types."""
        agent = Agent("Test agent")

        # Append multiple content parts as separate arguments
        agent.append("First part", "Second part", "Third part")

        user_msg = agent.messages[-1]
        # Multiple string arguments create multiple TextContentPart objects
        assert len(user_msg.content_parts) == 3
        assert all(isinstance(part, TextContentPart) for part in user_msg.content_parts)
        assert user_msg.content_parts[0].text == "First part"
        assert user_msg.content_parts[1].text == "Second part"
        assert user_msg.content_parts[2].text == "Third part"

        # When rendered, they are joined with newlines
        rendered = user_msg.render()
        assert "First part\nSecond part\nThird part" in rendered

    def test_append_with_protocol_object(self):
        """Test appending object with display protocol."""
        agent = Agent("Test agent")

        class CustomObject:
            def __display__(self):
                return "Custom display"

            def __llm__(self):
                return "Custom LLM format"

        obj = CustomObject()
        agent.append(obj)

        user_msg = agent.messages[-1]
        # Protocol objects are converted to TextContentPart with their LLM representation
        assert len(user_msg.content_parts) == 1
        assert isinstance(user_msg.content_parts[0], TextContentPart)
        assert user_msg.content_parts[0].text == "Custom LLM format"

    def test_template_detection_behavior(self):
        """Test that template detection works correctly."""
        agent = Agent("Test agent")

        # Append template string - should be auto-detected
        agent.append("Hello {{ name }}")

        user_msg = agent.messages[-1]
        # Should be TemplateContentPart due to template syntax
        assert isinstance(user_msg.content_parts[0], TemplateContentPart)
        assert user_msg.content_parts[0].template == "Hello {{ name }}"

        # Append non-template string
        agent.append("Hello world")

        user_msg2 = agent.messages[-1]
        # Should be TextContentPart
        assert isinstance(user_msg2.content_parts[0], TextContentPart)
        assert user_msg2.content_parts[0].text == "Hello world"


class TestEventIntegration:
    """Test event integration with content rendering."""

    @pytest.mark.asyncio
    async def test_render_events_fired(self):
        """Test that render events are fired during LLM formatting."""
        agent = Agent("Test agent")
        await agent.ready()
        events_fired = []

        def track_event(ctx):
            mode = ctx.parameters.get("mode")
            events_fired.append(("before", mode))

        def track_event_after(ctx):
            # The after event passes mode (not context) in new implementation
            mode = ctx.parameters.get("mode")
            events_fired.append(("after", mode))

        agent.on("message:render:before")(track_event)
        agent.on("message:render:after")(track_event_after)

        # Use agent's append method to properly set agent reference
        agent.append(UserMessage(content_parts=[TextContentPart(text="Test")]))

        # Get the message and render it directly
        msg = agent.messages[-1]
        result = msg.render(RenderMode.LLM)
        assert result == "Test"
        # We now fire both before and after events for LLM mode to support citation transformation
        assert len(events_fired) == 2  # Both before and after events for LLM mode
        assert events_fired[0] == ("before", RenderMode.LLM)
        assert events_fired[1] == ("after", RenderMode.LLM)

        # Clear events for next test
        events_fired.clear()

        # Events fire during LLM formatting
        from good_agent.model.llm import LanguageModel

        lm = LanguageModel()
        # Set up the component properly
        lm._agent = agent
        agent.events.broadcast_to(lm)
        lm.setup(agent)

        await lm.format_message_list_for_llm([msg])

        assert ("before", RenderMode.LLM) in events_fired
        assert ("after", RenderMode.LLM) in events_fired

    @pytest.mark.asyncio
    async def test_content_part_render_events(self):
        """Test events for individual content part rendering - not currently implemented."""
        agent = Agent("Test agent")
        await agent.ready()
        part_events = []

        def track_part_event(ctx):
            # The event passes context=mode
            part = ctx.parameters.get("part")
            context = ctx.parameters.get("context")
            part_events.append((type(part).__name__, context))

        # The actual event is called message:part:render
        agent.on("message:part:render")(track_part_event)

        # Use agent's append method to properly set agent reference
        agent.append(
            UserMessage(
                content_parts=[
                    TextContentPart(text="Text"),
                    TemplateContentPart(template="{{ test }}"),
                ]
            )
        )

        # Get the message and render it directly - no events
        msg = agent.messages[-1]
        msg.render(RenderMode.DISPLAY)
        assert len(part_events) == 0  # No events from direct render

        # Note: Per-part events are not currently implemented in the LanguageModel
        # This test documents the expected behavior if they were implemented


class TestMessageSerialization:
    """Test message serialization with v2 content parts."""

    def test_message_to_dict(self):
        """Test converting message to dictionary."""
        msg = UserMessage(
            content_parts=[
                TextContentPart(text="Hello"),
                ImageContentPart(image_url="https://example.com/img.jpg"),
            ]
        )

        data = msg.model_dump()
        assert data["role"] == "user"
        assert len(data["content_parts"]) == 2
        assert data["content_parts"][0]["type"] == "text"
        assert data["content_parts"][1]["type"] == "image"

    def test_message_from_dict(self):
        """Test creating message from dictionary."""
        data = {
            "role": "user",
            "content_parts": [
                {"type": "text", "text": "Hello"},
                {"type": "image", "image_url": "https://example.com/img.jpg"},
            ],
        }

        msg = UserMessage(**data)
        assert len(msg.content_parts) == 2
        assert isinstance(msg.content_parts[0], TextContentPart)
        assert isinstance(msg.content_parts[1], ImageContentPart)

    @pytest.mark.asyncio
    async def test_message_llm_format(self):
        """Test converting message to LLM API format via LanguageModel."""
        agent = Agent("Test agent")
        await agent.ready()

        msg = UserMessage(
            content_parts=[
                TextContentPart(text="Analyze this:"),
                ImageContentPart(image_url="https://example.com/img.jpg"),
            ]
        )
        msg._set_agent(agent)

        # LLM formatting now happens in LanguageModel
        from good_agent.model.llm import LanguageModel

        lm = LanguageModel()
        # Set up the component properly
        lm._agent = agent
        agent.events.broadcast_to(lm)
        lm.setup(agent)

        formatted = await lm.format_message_list_for_llm([msg])

        # Should have one formatted message
        assert len(formatted) == 1
        user_msg = formatted[0]

        # Check the content is properly formatted
        assert user_msg["role"] == "user"
        assert isinstance(user_msg["content"], list)
        assert len(user_msg["content"]) == 2
        assert user_msg["content"][0]["type"] == "text"
        assert user_msg["content"][1]["type"] == "image_url"

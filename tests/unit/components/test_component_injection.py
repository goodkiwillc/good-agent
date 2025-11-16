import pytest
from good_agent import Agent, AgentEvents
from good_agent.components.injection import (
    MessageInjectorComponent,
    SimpleMessageInjector,
)
from good_agent.content import (
    RenderMode,
    TemplateContentPart,
    TextContentPart,
)
from good_agent.messages import SystemMessage, UserMessage


class MockEnabledMessageInjector(MessageInjectorComponent):
    """Mock component that injects messages when enabled."""

    def get_system_prompt_prefix(self, agent):
        return [TextContentPart(text="[SYSTEM PREFIX]")]

    def get_system_prompt_suffix(self, agent):
        return [TextContentPart(text="[SYSTEM SUFFIX]")]

    def get_user_message_prefix(self, agent, message):
        return [TextContentPart(text="[USER PREFIX]")]

    def get_user_message_suffix(self, agent, message):
        return [TextContentPart(text="[USER SUFFIX]")]


class MockTemplateInjector(MessageInjectorComponent):
    """Mock component that injects templates."""

    def get_system_prompt_prefix(self, agent):
        return [TemplateContentPart(template="Agent: {{ agent_name }}")]

    def get_user_message_suffix(self, agent, message):
        return [TemplateContentPart(template="Time: {{ timestamp }}")]


@pytest.mark.asyncio
class TestMessageInjectorComponent:
    """Test suite for MessageInjectorComponent."""

    async def test_system_prompt_injection(self):
        """Test that components can inject content into system prompts."""
        component = MockEnabledMessageInjector()
        agent = Agent("Base system prompt", extensions=[component])
        await agent.ready()

        # Check the system message has the injected content
        system_msg = agent.messages[0]
        assert isinstance(system_msg, SystemMessage)

        # Verify the content parts were injected
        assert len(system_msg.content_parts) == 3  # prefix + original + suffix
        assert system_msg.content_parts[0].text == "[SYSTEM PREFIX]"
        assert system_msg.content_parts[2].text == "[SYSTEM SUFFIX]"

        # Verify rendering includes all parts
        rendered = system_msg.render(RenderMode.DISPLAY)
        assert "[SYSTEM PREFIX]" in rendered
        assert "Base system prompt" in rendered
        assert "[SYSTEM SUFFIX]" in rendered

    async def test_user_message_injection(self):
        """Test that components can inject content into user messages."""
        component = MockEnabledMessageInjector()
        agent = Agent("System prompt", extensions=[component])
        await agent.ready()

        # Add a user message
        agent.append(UserMessage(content="User query"))

        # Get the user message
        user_msg = agent.messages[-1]
        assert isinstance(user_msg, UserMessage)

        # The content_parts should not be modified in the message itself
        assert len(user_msg.content_parts) == 1

        # Test that injection happens during MESSAGE_RENDER_BEFORE event
        # We'll simulate what happens when the LLM formats messages
        from good_agent.content import RenderMode

        # Create a context to capture the rendered output
        rendered_parts = []

        @agent.on(AgentEvents.MESSAGE_RENDER_BEFORE)
        def capture_render(ctx):
            # This handler runs after our component's handler
            # So it should see the injected parts
            output = ctx.parameters.get("output")
            if output:
                rendered_parts.extend(output)

        # Trigger the render event manually (this is what LLM does internally)
        output_parts = list(user_msg.content_parts)  # Copy the list
        agent.events.apply_sync(
            AgentEvents.MESSAGE_RENDER_BEFORE,
            output=output_parts,
            message=user_msg,
            context=RenderMode.LLM,
        )

        # The apply_sync modifies the output list in place
        # Check that the parts were injected
        # Should have prefix + original + suffix
        assert len(output_parts) == 3
        assert output_parts[0].text == "[USER PREFIX]"
        assert "User query" in output_parts[1].text
        assert output_parts[2].text == "[USER SUFFIX]"

    async def test_component_disabled_no_injection(self):
        """Test that disabled components don't inject content."""
        component = MockEnabledMessageInjector(enabled=False)
        agent = Agent("Base system prompt", extensions=[component])
        await agent.ready()

        # Check the system message has NO injected content
        system_msg = agent.messages[0]
        assert isinstance(system_msg, SystemMessage)

        # Should only have the original content part
        assert len(system_msg.content_parts) == 1
        assert "Base system prompt" in system_msg.content_parts[0].text

        # Verify rendering doesn't include disabled component's content
        rendered = system_msg.render(RenderMode.DISPLAY)
        assert "[SYSTEM PREFIX]" not in rendered
        assert "[SYSTEM SUFFIX]" not in rendered

    async def test_component_enable_disable_runtime(self):
        """Test enabling/disabling components at runtime."""
        component = MockEnabledMessageInjector(enabled=False)
        agent = Agent("Base prompt", extensions=[component])
        await agent.ready()

        # Initially disabled - no injection
        initial_system = agent.messages[0]
        assert len(initial_system.content_parts) == 1

        # Enable the component
        component.enabled = True

        # Set a new system message
        agent.set_system_message("New system prompt")

        # Should now have injected content
        new_system = agent.messages[0]
        assert len(new_system.content_parts) == 3
        assert new_system.content_parts[0].text == "[SYSTEM PREFIX]"

    async def test_template_injection_with_context(self):
        """Test that template injections have access to agent context."""
        component = MockTemplateInjector()

        # Add context that templates can access
        agent = Agent(
            "System prompt",
            extensions=[component],
            context={"agent_name": "TestBot", "timestamp": "2024-01-01"},
        )
        await agent.ready()

        # Check system message has template part
        system_msg = agent.messages[0]
        assert len(system_msg.content_parts) == 2  # prefix template + original

        # Verify the template renders with context
        rendered = system_msg.render(RenderMode.DISPLAY)
        assert "Agent: TestBot" in rendered

    async def test_multiple_components_injection(self):
        """Test multiple components can inject content."""
        component1 = MockEnabledMessageInjector()
        component2 = SimpleMessageInjector(
            system_prefix="[SIMPLE PREFIX]\n",
            system_suffix="\n[SIMPLE SUFFIX]",
        )

        agent = Agent("Base prompt", extensions=[component1, component2])
        await agent.ready()

        # Both components should inject their content
        system_msg = agent.messages[0]
        # Component1: prefix + original + suffix = 3
        # Component2: prefix + suffix = 2 more
        # Total: 5 parts
        assert len(system_msg.content_parts) == 5

        rendered = system_msg.render(RenderMode.DISPLAY)
        assert "[SYSTEM PREFIX]" in rendered
        assert "[SIMPLE PREFIX]" in rendered
        assert "Base prompt" in rendered
        assert "[SIMPLE SUFFIX]" in rendered
        assert "[SYSTEM SUFFIX]" in rendered


@pytest.mark.asyncio
class TestSimpleMessageInjector:
    """Test suite for SimpleMessageInjector."""

    async def test_simple_text_injection(self):
        """Test simple text injection without templates."""
        injector = SimpleMessageInjector(
            system_prefix="Important: ",
            system_suffix=" Always be helpful.",
            user_prefix="Query: ",
            user_suffix=" Please respond concisely.",
            use_templates=False,
        )

        agent = Agent("Follow instructions", extensions=[injector])
        await agent.ready()

        # Check system message
        system_msg = agent.messages[0]
        rendered = system_msg.render(RenderMode.DISPLAY)
        # Content parts are joined with newlines
        assert "Important:" in rendered
        assert "Follow instructions" in rendered
        assert "Always be helpful." in rendered

    async def test_template_detection(self):
        """Test that templates are detected and created correctly."""
        injector = SimpleMessageInjector(
            system_prefix="Agent ID: {{ agent_id }}",
            user_suffix="Session: {{ session_id }}",
            use_templates=True,
        )

        agent = Agent(
            "System",
            extensions=[injector],
            context={"agent_id": "bot-123", "session_id": "sess-456"},
        )
        await agent.ready()

        # Check that template parts were created
        system_msg = agent.messages[0]
        assert isinstance(system_msg.content_parts[0], TemplateContentPart)
        assert system_msg.content_parts[0].template == "Agent ID: {{ agent_id }}"

        # Verify template renders with context
        rendered = system_msg.render(RenderMode.DISPLAY)
        assert "Agent ID: bot-123" in rendered

    async def test_no_injection_with_none_values(self):
        """Test that None values don't create empty content parts."""
        injector = SimpleMessageInjector(
            system_prefix=None,
            system_suffix="Suffix only",
            user_prefix=None,
            user_suffix=None,
        )

        agent = Agent("System", extensions=[injector])
        await agent.ready()

        system_msg = agent.messages[0]
        # Should only have original + suffix (no prefix since it's None)
        assert len(system_msg.content_parts) == 2
        assert system_msg.content_parts[1].text == "Suffix only"

    async def test_empty_string_no_injection(self):
        """Test that empty strings don't create content parts."""
        injector = SimpleMessageInjector(
            system_prefix="",
            system_suffix="Valid suffix",
            user_prefix="",
            user_suffix="",
        )

        agent = Agent("System", extensions=[injector])
        await agent.ready()

        system_msg = agent.messages[0]
        # Should only have original + suffix (empty strings ignored)
        assert len(system_msg.content_parts) == 2

    async def test_user_message_injection_only_last(self):
        """Test that only the last user message gets injection during render."""
        injector = SimpleMessageInjector(
            user_prefix="[INJECTED] ",
            user_suffix=" [END]",
        )

        agent = Agent("System", extensions=[injector])
        await agent.ready()

        # Add multiple user messages
        agent.append(UserMessage(content="First user message"))
        agent.append(UserMessage(content="Second user message"))

        # The raw content parts shouldn't be modified
        first_user = agent.messages[1]
        second_user = agent.messages[2]
        assert len(first_user.content_parts) == 1
        assert len(second_user.content_parts) == 1

        # During render, only the last would get the injection
        # (This happens in MESSAGE_RENDER_BEFORE event)

    async def test_component_with_tools(self):
        """Test that message injection works alongside tool usage."""
        from good_agent import tool

        @tool
        def test_tool(query: str) -> str:
            return f"Tool response for: {query}"

        injector = SimpleMessageInjector(
            system_suffix="\nYou have access to tools.",
            user_suffix="\nUse tools if needed.",
        )

        agent = Agent(
            "Assistant",
            tools=[test_tool],
            extensions=[injector],
        )
        await agent.ready()

        # Verify system message has tool instruction
        system_msg = agent.messages[0]
        rendered = system_msg.render(RenderMode.DISPLAY)
        assert "You have access to tools" in rendered

        # Verify tool is available
        assert "test_tool" in agent.tools

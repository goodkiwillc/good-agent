from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import TYPE_CHECKING

from good_agent.content import ContentPartType, TemplateContentPart, TextContentPart
from good_agent.core.components.component import AgentComponent
from good_agent.events import AgentEvents
from good_agent.messages import SystemMessage, UserMessage

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from good_agent.agent import Agent


class MessageInjectorComponent(AgentComponent):
    """
    Enhanced AgentComponent with message injection capabilities.

    Provides hooks for components to inject content into:
    - System prompts (beginning or end)
    - User messages (beginning or end)

    All injections respect the component's enabled state and support
    the Agent library's templating functionality.

    Example:
        class MyComponent(MessageInjectorComponent):
            def get_system_prompt_prefix(self, agent: Agent) -> Sequence[ContentPartType]:
                # Inject context at the beginning of system prompt
                return [TextContentPart(text="Additional context: ...")]

            def get_user_message_suffix(self, agent: Agent, message: UserMessage) -> Sequence[ContentPartType]:
                # Add context to end of user message
                return [TemplateContentPart(template="Current time: {{ timestamp }}")]
    """

    def setup(self, agent: Agent) -> None:
        """Register event handlers during synchronous setup."""
        super().setup(agent)

        # Register handler for system message modifications
        # We use AFTER event since the message needs to be set first
        @agent.on(AgentEvents.MESSAGE_SET_SYSTEM_AFTER, priority=100)
        def inject_system_content(ctx):
            """Inject content into system messages after they're set."""
            if not self.enabled:
                return

            # The system message should be the first message now
            if agent._messages and isinstance(agent._messages[0], SystemMessage):
                self._inject_system_message(agent, agent._messages[0])  # type: ignore[arg-type]

        # Register handler for user message modifications before sending to LLM
        # This should be registered ONCE during setup, not inside _inject_system_message
        @agent.on(AgentEvents.MESSAGE_RENDER_BEFORE, priority=100)
        def inject_user_content(ctx):
            """Inject content into the last user message before LLM processing."""
            if not self.enabled:
                return

            message = ctx.parameters.get("message")

            # Only process user messages
            if not isinstance(message, UserMessage):
                return

            # Check if this is the last user message
            user_messages = [m for m in agent.messages if isinstance(m, UserMessage)]
            if not user_messages or message != user_messages[-1]:
                return

            # Get the content parts to inject
            output = ctx.parameters.get("output")
            if not isinstance(output, list):
                return

            # Get prefix and suffix content parts
            prefix_parts = self.get_user_message_prefix(agent, message)
            suffix_parts = self.get_user_message_suffix(agent, message)

            # Modify the output list in place (this affects what gets rendered)
            if prefix_parts or suffix_parts:
                original_count = len(output)

                if prefix_parts:
                    # Insert at the beginning
                    for i, part in enumerate(prefix_parts):
                        output.insert(i, part)

                if suffix_parts:
                    # Append to the end
                    output.extend(suffix_parts)

                # Log the modification
                prefix_count = len(prefix_parts) if prefix_parts else 0
                suffix_count = len(suffix_parts) if suffix_parts else 0

                logger.info(
                    f"{self.__class__.__name__}: Modified user message - "
                    f"added {prefix_count} prefix and {suffix_count} suffix parts "
                    f"(original had {original_count} parts)"
                )

                # Log detailed content at trace level
                if prefix_parts:
                    logger.debug(
                        f"User prefix content: {[str(p)[:50] + '...' if len(str(p)) > 50 else str(p) for p in prefix_parts]}"
                    )
                if suffix_parts:
                    logger.debug(
                        f"User suffix content: {[str(p)[:50] + '...' if len(str(p)) > 50 else str(p) for p in suffix_parts]}"
                    )

    def _inject_system_message(self, agent: Agent, message: SystemMessage) -> None:
        """Helper to inject content into a system message."""
        if not self.enabled:
            return

        # Get prefix and suffix content parts
        prefix_parts = self.get_system_prompt_prefix(agent)
        suffix_parts = self.get_system_prompt_suffix(agent)

        # If we have parts to inject, create a new message with modified content
        if prefix_parts or suffix_parts:
            # Combine all content parts
            new_content_parts: list[ContentPartType] = []
            if prefix_parts:
                new_content_parts.extend(prefix_parts)
            new_content_parts.extend(message.content_parts)
            if suffix_parts:
                new_content_parts.extend(suffix_parts)

            # Create new message with updated content parts
            # Since messages are frozen, we need to create a new one
            new_message = SystemMessage(
                content_parts=new_content_parts,
                citations=message.citations,
                id=message.id,
                name=message.name,
                timestamp=message.timestamp,
                metadata=message.metadata,
            )

            # Set the agent reference on the new message
            new_message._set_agent(agent)

            # Replace the message in the agent's message list
            if agent._messages and agent._messages[0] == message:
                agent._messages[0] = new_message

                # Log the injection details
                prefix_count = len(prefix_parts) if prefix_parts else 0
                suffix_count = len(suffix_parts) if suffix_parts else 0

                logger.info(
                    f"{self.__class__.__name__}: Modified system prompt - "
                    f"added {prefix_count} prefix and {suffix_count} suffix parts"
                )

                # If print_messages is enabled and set to 'llm' mode, show the modified system message
                if hasattr(agent, "config") and agent.config.print_messages:
                    if agent.config.print_messages_mode == "llm":
                        from good_agent.content import RenderMode
                        from good_agent.utilities import print_message

                        logger.info(
                            "System prompt as it will appear to LLM (with injected content):"
                        )
                        print_message(
                            new_message,
                            render_mode=RenderMode.LLM,
                            title=f"@system [MODIFIED by {self.__class__.__name__}]",
                        )

                logger.debug(
                    f"Prefix content: {[str(p)[:50] + '...' if len(str(p)) > 50 else str(p) for p in (prefix_parts or [])]}"
                )
                logger.debug(
                    f"Suffix content: {[str(p)[:50] + '...' if len(str(p)) > 50 else str(p) for p in (suffix_parts or [])]}"
                )

    def get_system_prompt_prefix(self, agent: Agent) -> Sequence[ContentPartType]:
        """
        Get content parts to inject at the beginning of the system prompt.

        Override this method to provide content that should appear at the
        start of the system prompt.

        Args:
            agent: The agent instance

        Returns:
            List of content parts to prepend to system prompt, or empty list
        """
        return []

    def get_system_prompt_suffix(self, agent: Agent) -> Sequence[ContentPartType]:
        """
        Get content parts to inject at the end of the system prompt.

        Override this method to provide content that should appear at the
        end of the system prompt.

        Args:
            agent: The agent instance

        Returns:
            List of content parts to append to system prompt, or empty list
        """
        return []

    def get_user_message_prefix(
        self, agent: Agent, message: UserMessage
    ) -> Sequence[ContentPartType]:
        """
        Get content parts to inject at the beginning of a user message.

        Override this method to provide content that should appear at the
        start of the last user message before it's sent to the LLM.

        Args:
            agent: The agent instance
            message: The user message being processed

        Returns:
            List of content parts to prepend to user message, or empty list
        """
        return []

    def get_user_message_suffix(
        self, agent: Agent, message: UserMessage
    ) -> Sequence[ContentPartType]:
        """
        Get content parts to inject at the end of a user message.

        Override this method to provide content that should appear at the
        end of the last user message before it's sent to the LLM.

        Args:
            agent: The agent instance
            message: The user message being processed

        Returns:
            List of content parts to append to user message, or empty list
        """
        return []


class SimpleMessageInjector(MessageInjectorComponent):
    """
    Simple implementation of MessageInjectorComponent for direct text injection.

    This provides a concrete implementation that can be configured with
    static text or templates to inject.

    Example:
        injector = SimpleMessageInjector(
            system_prefix="You must always be helpful.\n",
            user_suffix="\\n\\nPlease be concise."
        )
        agent = Agent("Base prompt", extensions=[injector])
    """

    def __init__(
        self,
        system_prefix: str | None = None,
        system_suffix: str | None = None,
        user_prefix: str | None = None,
        user_suffix: str | None = None,
        use_templates: bool = True,
        **kwargs,
    ):
        """
        Initialize the simple message injector.

        Args:
            system_prefix: Text/template to prepend to system prompt
            system_suffix: Text/template to append to system prompt
            user_prefix: Text/template to prepend to user messages
            user_suffix: Text/template to append to user messages
            use_templates: Whether to detect and use templates (default True)
            **kwargs: Additional arguments for AgentComponent
        """
        super().__init__(**kwargs)
        self.system_prefix = system_prefix
        self.system_suffix = system_suffix
        self.user_prefix = user_prefix
        self.user_suffix = user_suffix
        self.use_templates = use_templates

    def _create_content_part(self, content: str) -> ContentPartType | None:
        """Create appropriate content part based on template detection."""
        if not content:
            return None

        if self.use_templates and "{{" in content and "}}" in content:
            return TemplateContentPart(template=content)
        else:
            return TextContentPart(text=content)

    def get_system_prompt_prefix(self, agent: Agent) -> Sequence[ContentPartType]:
        """Get system prompt prefix content parts."""
        if self.system_prefix:
            part = self._create_content_part(self.system_prefix)
            return [part] if part else []
        return []

    def get_system_prompt_suffix(self, agent: Agent) -> Sequence[ContentPartType]:
        """Get system prompt suffix content parts."""
        if self.system_suffix:
            part = self._create_content_part(self.system_suffix)
            return [part] if part else []
        return []

    def get_user_message_prefix(
        self, agent: Agent, message: UserMessage
    ) -> Sequence[ContentPartType]:
        """Get user message prefix content parts."""
        if self.user_prefix:
            part = self._create_content_part(self.user_prefix)
            return [part] if part else []
        return []

    def get_user_message_suffix(
        self, agent: Agent, message: UserMessage
    ) -> Sequence[ContentPartType]:
        """Get user message suffix content parts."""
        if self.user_suffix:
            part = self._create_content_part(self.user_suffix)
            return [part] if part else []
        return []

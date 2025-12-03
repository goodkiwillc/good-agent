"""Message formatting for LLM API compatibility."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from good_agent.content import (
    ContentPartType,
    FileContentPart,
    ImageContentPart,
    RenderMode,
    TemplateContentPart,
    TextContentPart,
)
from good_agent.core.types import URL
from good_agent.events import AgentEvents
from good_agent.messages import (
    AssistantMessage,
    Message,
    SystemMessage,
    ToolMessage,
    UserMessage,
)
from good_agent.utilities import url_to_base64

if TYPE_CHECKING:
    from litellm.types.completion import ChatCompletionMessageParam

    from good_agent.model.llm import LanguageModel


class MessageFormatter:
    """Handles message formatting for LLM API compatibility.

    Converts internal message objects to LLM API format with proper
    content part handling, event hooks, and tool call validation.
    """

    def __init__(self, language_model: LanguageModel):
        """Initialize formatter.

        Args:
            language_model: Parent LanguageModel instance
        """
        self.llm = language_model

    async def format_message_content(
        self,
        content_parts: list[ContentPartType],
        message: Message,
        mode: RenderMode = RenderMode.LLM,
    ):
        """Format message content parts for LLM API.

        Args:
            content_parts: List of content parts to format
            message: The message being formatted
            mode: Render mode for content

        Returns:
            Formatted content parts ready for LLM API
        """
        # Fire before render event
        ctx = await self.llm.agent.events.apply(
            AgentEvents.MESSAGE_RENDER_BEFORE,
            output=content_parts,
            message=message,
            mode=mode,
        )

        content_parts = ctx.return_value or content_parts

        result = []
        for part in content_parts:
            if isinstance(part, TextContentPart):
                ChatCompletionContentPartTextParam = self.llm._get_litellm_type(
                    "ChatCompletionContentPartTextParam"
                )
                result.append(ChatCompletionContentPartTextParam(text=part.text, type="text"))
            elif isinstance(part, TemplateContentPart):
                # Render template for LLM
                rendered = message._render_part(part, mode)
                ChatCompletionContentPartTextParam = self.llm._get_litellm_type(
                    "ChatCompletionContentPartTextParam"
                )
                result.append(ChatCompletionContentPartTextParam(text=rendered, type="text"))
            elif isinstance(part, ImageContentPart):
                ChatCompletionContentPartImageParam = self.llm._get_litellm_type(
                    "ChatCompletionContentPartImageParam"
                )
                ImageURL = self.llm._get_litellm_type("ImageURL")
                payload = part.to_llm_format().get("image_url", {})
                image_url = payload.get("url")
                detail = payload.get("detail", part.detail)
                if image_url is None:
                    continue
                if part.image_base64 and not image_url.startswith("data:"):
                    mime = part.mime_type or "image/jpeg"
                    image_url = f"data:{mime};base64,{image_url}"
                result.append(
                    ChatCompletionContentPartImageParam(
                        image_url=ImageURL(url=str(image_url), detail=detail),
                        type="image_url",
                    )
                )
            elif isinstance(part, FileContentPart):
                formatted = part.to_llm_format()
                if formatted.get("type") == "file":
                    file_payload = formatted.get("file", {})
                    file_id = file_payload.get("file_id")
                    if not file_id:
                        continue
                    ChatCompletionFileObject = self.llm._get_litellm_type(
                        "ChatCompletionFileObject"
                    )
                    ChatCompletionFileObjectFile = self.llm._get_litellm_type(
                        "ChatCompletionFileObjectFile"
                    )
                    file_kwargs: dict[str, Any] = {"file_id": file_id}
                    if file_payload.get("format"):
                        file_kwargs["format"] = file_payload["format"]
                    if file_payload.get("filename"):
                        file_kwargs["filename"] = file_payload["filename"]
                    try:
                        result.append(
                            ChatCompletionFileObject(
                                file=ChatCompletionFileObjectFile(**file_kwargs),
                                type="file",
                            )
                        )
                    except Exception:
                        # Fallback to raw dict if typed construction fails
                        result.append(formatted)
                elif formatted.get("type") == "text":
                    ChatCompletionContentPartTextParam = self.llm._get_litellm_type(
                        "ChatCompletionContentPartTextParam"
                    )
                    result.append(
                        ChatCompletionContentPartTextParam(
                            text=formatted.get("text", ""), type="text"
                        )
                    )

        # Fire after render event
        ctx = await self.llm.agent.events.apply(
            AgentEvents.MESSAGE_RENDER_AFTER,
            output=result,
            message=message,
            mode=mode,
        )

        return ctx.return_value or result

    async def format_message(
        self,
        message: Message,
        mode: RenderMode = RenderMode.LLM,
    ) -> ChatCompletionMessageParam:
        """Format a single message for LLM API.

        Args:
            message: Message to format
            mode: Render mode for content

        Returns:
            Formatted message in LLM API format
        """
        match message:
            case SystemMessage():
                # Render content for LLM mode
                _content = await self.format_message_content(
                    message.content_parts, message=message, mode=mode
                )
                ChatCompletionSystemMessageParam = self.llm._get_litellm_type(
                    "ChatCompletionSystemMessageParam"
                )
                return ChatCompletionSystemMessageParam(
                    content=_content
                    if isinstance(_content, str)
                    else "".join(
                        part.get("text", "")
                        for part in _content
                        if isinstance(part, dict) and part.get("type") == "text"
                    ),
                    role="system",
                )

            case UserMessage(images=images, image_detail=image_detail):
                # Format content parts with events
                _content = await self.format_message_content(
                    message.content_parts, message=message, mode=mode
                )

                # Add legacy images if present
                if images:
                    if not isinstance(_content, list):
                        _content = [_content] if _content else []

                    for image in images:
                        if isinstance(image, URL):
                            ChatCompletionContentPartImageParam = self.llm._get_litellm_type(
                                "ChatCompletionContentPartImageParam"
                            )
                            ImageURL = self.llm._get_litellm_type("ImageURL")
                            _content.append(
                                ChatCompletionContentPartImageParam(
                                    image_url=ImageURL(url=str(image)),
                                    type="image_url",
                                )
                            )
                        elif isinstance(image, bytes):
                            ChatCompletionContentPartImageParam = self.llm._get_litellm_type(
                                "ChatCompletionContentPartImageParam"
                            )
                            ImageURL = self.llm._get_litellm_type("ImageURL")
                            _content.append(
                                ChatCompletionContentPartImageParam(
                                    image_url=ImageURL(
                                        url=url_to_base64(image), detail=image_detail
                                    ),
                                    type="image_url",
                                )
                            )

                # Return the formatted user message
                ChatCompletionUserMessageParam = self.llm._get_litellm_type(
                    "ChatCompletionUserMessageParam"
                )
                if isinstance(_content, str):
                    return ChatCompletionUserMessageParam(
                        content=_content,
                        role="user",
                    )
                else:
                    return ChatCompletionUserMessageParam(
                        content=_content,
                        role="user",
                    )
            case AssistantMessage(tool_calls=tool_calls):
                # Format content parts with events
                _content = await self.format_message_content(
                    message.content_parts, message=message, mode=mode
                )

                # Convert content to string if it's a list
                if isinstance(_content, list):
                    # Join text parts for assistant messages
                    _content = (
                        "".join(
                            part.get("text", "") if isinstance(part, dict) else str(part)
                            for part in _content
                            if isinstance(part, dict) and part.get("type") == "text"
                        )
                        or ""
                    )

                # Build the assistant message
                ChatCompletionAssistantMessageParam = self.llm._get_litellm_type(
                    "ChatCompletionAssistantMessageParam"
                )
                assistant_msg = ChatCompletionAssistantMessageParam(
                    role="assistant",
                    content=_content,
                )

                # Add tool calls if present
                if tool_calls:
                    # Convert our ToolCall objects to litellm format
                    ChatCompletionMessageToolCallParam = self.llm._get_litellm_type(
                        "ChatCompletionMessageToolCallParam"
                    )
                    Function = self.llm._get_litellm_type("Function")
                    tool_calls_list: list[Any] = []  # Use Any for runtime dynamic types
                    for tc in tool_calls:
                        tool_call_dict = ChatCompletionMessageToolCallParam(
                            id=tc.id,
                            type=tc.type,
                            function=Function(
                                name=tc.function.name,
                                arguments=tc.function.arguments,
                            ),
                        )
                        tool_calls_list.append(tool_call_dict)
                    assistant_msg["tool_calls"] = tool_calls_list

                return assistant_msg

            case ToolMessage(tool_call_id=tool_call_id):
                # Format content parts with events
                _content = await self.format_message_content(
                    message.content_parts, message=message, mode=mode
                )

                # Convert content to string if it's a list
                if isinstance(_content, list):
                    # Join text parts for tool messages
                    _content = (
                        "".join(
                            part.get("text", "") if isinstance(part, dict) else str(part)
                            for part in _content
                            if isinstance(part, dict) and part.get("type") == "text"
                        )
                        or ""
                    )

                ChatCompletionToolMessageParam = self.llm._get_litellm_type(
                    "ChatCompletionToolMessageParam"
                )
                return ChatCompletionToolMessageParam(
                    role="tool",
                    content=_content,
                    tool_call_id=tool_call_id,
                )

            case _:
                # Fallback for any other message type
                raise ValueError(f"Unsupported message type: {type(message)}")

    async def format_message_list_for_llm(
        self, messages: list[Message]
    ) -> list[ChatCompletionMessageParam | dict[str, Any]]:
        """Format a list of messages for LLM consumption with event hooks.

        This method handles all message formatting including:
        - Firing render events for extensions
        - Converting content parts to LLM format
        - Handling templates, images, and files
        - Ensuring tool call/response pairs are valid (injects synthetic tool responses)

        Args:
            messages: List of Message objects to format

        Returns:
            List of formatted messages ready for LLM API, with synthetic tool
            responses injected for any assistant messages with tool_calls that
            don't have corresponding tool responses
        """
        # Process messages in order (not parallel) to maintain sequence
        messages_for_llm: list[ChatCompletionMessageParam | dict[str, Any]] = []
        for msg in messages:
            formatted = await self.format_message(msg, RenderMode.LLM)
            messages_for_llm.append(formatted)

        # Ensure all tool calls have corresponding tool responses
        # This is critical for AssistantMessageStructuredOutput which may have
        # tool_calls in the message history but no actual ToolMessage responses
        messages_for_llm = self.ensure_tool_call_pairs_for_formatted_messages(messages_for_llm)

        return messages_for_llm

    def ensure_tool_call_pairs_for_formatted_messages(
        self, messages: Sequence[ChatCompletionMessageParam | dict[str, Any]]
    ) -> list[ChatCompletionMessageParam | dict[str, Any]]:
        """Ensure assistant messages with tool_calls are immediately followed by
        corresponding tool messages in the payload sent to the API.

        This does NOT modify agent history; it only adjusts the outbound message list.

        Args:
            messages: Sequence of formatted messages

        Returns:
            List of messages with synthetic tool responses injected where needed
        """

        # Helper to access attributes on dict-like or object-like instances
        def _get_attr(obj: Any, key: str, default: Any = None) -> Any:
            try:
                if hasattr(obj, "get"):
                    return obj.get(key, default)  # type: ignore[attr-defined]
            except Exception:
                pass
            try:
                return getattr(obj, key)
            except Exception:
                return default

        ChatCompletionToolMessageParam = self.llm._get_litellm_type(
            "ChatCompletionToolMessageParam"
        )

        result: list[ChatCompletionMessageParam | dict[str, Any]] = []
        i = 0
        n = len(messages)
        while i < n:
            msg = messages[i]
            role = _get_attr(msg, "role", None)

            # If assistant with tool_calls, ensure immediate tool responses exist
            tool_calls = _get_attr(msg, "tool_calls", None) if role == "assistant" else None
            if role == "assistant" and tool_calls:
                # Append the assistant message first
                result.append(msg)

                # Collect IDs from assistant's tool calls
                assistant_call_ids: list[str] = []
                try:
                    for tc in tool_calls:
                        # tc may be dict-like or object-like
                        tc_id = _get_attr(tc, "id", None)
                        if tc_id:
                            assistant_call_ids.append(tc_id)
                except Exception:
                    assistant_call_ids = []

                # Append any immediate tool messages that follow in the source list
                existing_ids: set[str] = set()
                j = i + 1
                while j < n and _get_attr(messages[j], "role", None) == "tool":
                    tm = messages[j]
                    result.append(tm)
                    tcid = _get_attr(tm, "tool_call_id", None)
                    if isinstance(tcid, str):
                        existing_ids.add(tcid)
                    j += 1

                # Inject synthetic tool messages for any missing tool_call IDs
                for tc_id in assistant_call_ids:
                    if tc_id not in existing_ids:
                        result.append(
                            ChatCompletionToolMessageParam(
                                role="tool", content="{}", tool_call_id=tc_id
                            )
                        )

                # Advance pointer past the immediate tool message block
                i = j
                continue

            # Default path: pass-through
            result.append(msg)
            i += 1

        return result


__all__ = ["MessageFormatter"]

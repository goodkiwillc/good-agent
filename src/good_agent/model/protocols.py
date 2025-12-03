"""Type protocols and data structures for the model package."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, TypeAlias, TypedDict, runtime_checkable

if TYPE_CHECKING:
    from litellm.types.utils import Choices, StreamingChoices, Usage
    from pydantic import BaseModel

    from good_agent.agent.config import ModelConfig


class ModelResponseProtocol(Protocol):
    """Protocol for model response objects with usage"""

    @property
    def id(self) -> str: ...

    @property
    def choices(self) -> Choices | StreamingChoices: ...

    @property
    def model(self) -> str | Any: ...

    @property
    def created(self) -> int: ...


@runtime_checkable
class ResponseWithUsage(Protocol):
    @property
    def usage(self) -> Usage | None: ...


@runtime_checkable
class ResponseWithHiddenParams(Protocol):
    @property
    def _hidden_params(self) -> dict[str, Any] | Any: ...


@runtime_checkable
class ResponseWithResponseHeaders(ModelResponseProtocol, Protocol):
    @property
    def _response_headers(self) -> dict[str, Any] | Any: ...


ModelName: TypeAlias = str


class CompletionEvent(TypedDict):
    """Event type for chat completion without response model extraction."""

    messages: list[Any]  # ChatCompletionMessageParam
    config: ModelConfig
    response_model: type[BaseModel] | None
    llm: Any  # LanguageModel


@dataclass
class StreamChunk:
    """Streaming response chunk"""

    content: str | None = None
    finish_reason: str | None = None


# Constants
DEFAULT_MODEL = "gpt-4.1-mini"

FILTER_ARGS = [
    "instructor_mode",
    "context",
    "max_retries",
    "fallback_models",
    "debug",
]

DEFAULT_TEMPERATURE = 1

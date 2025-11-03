# LiteLLM Replacement Plan

## Executive Summary

**DO NOT EXTRACT LITELLM CODE** - it's bloated, poorly designed, and extraction would be counterproductive.

Instead, we'll build a lightweight, fast multi-provider client using native SDKs with a thin abstraction layer inspired by instructor's approach.

## Performance Analysis

### Import Time Benchmarks
```
litellm:     5.470s  (5.5x slower than openai)
openai:      1.084s
instructor:  1.433s
```

### Package Size
```
litellm:     41MB  (5x larger than openai)
openai:      8.1MB
instructor:  1.4MB
```

**Conclusion:** LiteLLM's 5.5-second import time and 41MB size makes it unsuitable for a fast, lightweight library.

## Current LiteLLM Usage in good-agent

### Primary Usage Points

1. **Router Class** (`model/manager.py`)
   - Multi-model routing with fallbacks
   - Retry logic
   - Callback isolation (custom ManagedRouter wrapper)
   
2. **Type Definitions** (throughout)
   - `ModelResponse`, `Choices`, `Usage`, `Message`
   - `ChatCompletionMessageParam` and variants
   - Response types for structured output

3. **Token Counting** (`utilities/tokens.py`)
   - `token_counter()` function
   - Message token counting
   - Cost calculation

4. **Model Capabilities** (`model/llm.py`)
   - `supports_function_calling()`
   - `supports_vision()`
   - Other capability checks via registry

5. **Cost Calculation** (`model/llm.py`)
   - `completion_cost(response)`
   - Token cost tracking

6. **Stream Building** (`model/llm.py`)
   - `stream_chunk_builder(chunks)`

7. **Actual API Calls** (`model/manager.py`)
   - `router.acompletion()`
   - Streaming support

## Why NOT to Extract LiteLLM Code

### 1. Massive Codebase
- **22,143 lines** across just 3 core files (main.py, router.py, utils.py)
- **100 provider implementations** in llms/ directory
- Complex interdependencies and global state
- Would require extracting 10,000+ lines minimum

### 2. Poor Architecture
- Heavy use of global variables and monkey patching
- Complex callback system with hard limits (30 callbacks max)
- Tight coupling between providers
- Massive import tree (5.5 second import time)

### 3. We Only Need 3 Providers
- OpenAI (gpt-4, etc.)
- Anthropic (claude-3.5-sonnet, etc.)
- OpenRouter (unified API)

### 4. Native SDKs Are Better
- OpenAI SDK: Well-maintained, fast, typed
- Anthropic SDK: Official, optimized
- Both support streaming, retries, timeouts natively

## Proposed Architecture

### Design Principles

1. **Lazy Loading** - Import providers only when used
2. **Native SDKs** - Use official provider SDKs, don't reimplement
3. **Thin Abstraction** - Minimal wrapper for unified interface
4. **Fast Imports** - Target <200ms total import time
5. **Type Safety** - Full typing support with minimal overhead

### Directory Structure

```
src/good_agent/llm_client/
├── __init__.py              # Minimal exports, lazy loading
├── types.py                 # Common types (ModelResponse, etc.)
├── base.py                  # Base client protocol/ABC
├── providers/
│   ├── __init__.py         # Provider registry
│   ├── openai.py           # OpenAI client wrapper
│   ├── anthropic.py        # Anthropic client wrapper
│   └── openrouter.py       # OpenRouter (OpenAI-compatible)
├── router.py                # Multi-model router with fallbacks
├── tokens.py                # Token counting utilities
├── costs.py                 # Cost calculation utilities
└── utils.py                 # Shared utilities
```

### Core Components

#### 1. Base Types (`types.py`)

Define minimal, provider-agnostic types:

```python
from typing import Protocol, Literal, Any
from pydantic import BaseModel

class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

class ModelResponse(BaseModel):
    id: str
    model: str
    choices: list[Choice]
    usage: Usage | None = None
    created: int
    
class StreamChunk(BaseModel):
    content: str | None
    finish_reason: str | None
    
# etc.
```

#### 2. Base Client (`base.py`)

```python
from typing import Protocol, AsyncIterator
from .types import ModelResponse, StreamChunk

class LLMClient(Protocol):
    """Base protocol for LLM clients."""
    
    async def complete(
        self,
        messages: list[dict[str, Any]],
        model: str,
        **kwargs: Any
    ) -> ModelResponse:
        ...
    
    async def stream(
        self,
        messages: list[dict[str, Any]],
        model: str,
        **kwargs: Any
    ) -> AsyncIterator[StreamChunk]:
        ...
```

#### 3. OpenAI Provider (`providers/openai.py`)

```python
from openai import AsyncOpenAI
from ..base import LLMClient
from ..types import ModelResponse

class OpenAIClient(LLMClient):
    """Lightweight wrapper around OpenAI SDK."""
    
    def __init__(self, api_key: str | None = None, **kwargs):
        self._client = AsyncOpenAI(api_key=api_key, **kwargs)
    
    async def complete(self, messages, model, **kwargs) -> ModelResponse:
        response = await self._client.chat.completions.create(
            model=model,
            messages=messages,
            **kwargs
        )
        # Convert OpenAI response to our ModelResponse
        return self._convert_response(response)
    
    async def stream(self, messages, model, **kwargs):
        stream = await self._client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
            **kwargs
        )
        async for chunk in stream:
            yield self._convert_chunk(chunk)
```

#### 4. Router with Fallbacks (`router.py`)

```python
from typing import Any
from .providers import get_provider
from .base import LLMClient

class ModelRouter:
    """Lightweight router with fallback support."""
    
    def __init__(
        self,
        primary_model: str,
        fallback_models: list[str] | None = None,
        max_retries: int = 3
    ):
        self.primary_model = primary_model
        self.fallback_models = fallback_models or []
        self.max_retries = max_retries
        self._clients: dict[str, LLMClient] = {}
    
    def _get_client(self, model: str) -> LLMClient:
        """Get or create client for provider (lazy loading)."""
        provider = self._detect_provider(model)
        if provider not in self._clients:
            self._clients[provider] = get_provider(provider)
        return self._clients[provider]
    
    async def complete(self, messages, **kwargs):
        """Try primary model, fallback on failure."""
        models = [self.primary_model] + self.fallback_models
        
        last_error = None
        for model in models:
            client = self._get_client(model)
            try:
                return await client.complete(
                    messages=messages,
                    model=model,
                    **kwargs
                )
            except Exception as e:
                last_error = e
                continue
        
        raise last_error or Exception("All models failed")
```

#### 5. Token Counting (`tokens.py`)

```python
# Lazy import tiktoken only when needed
_tiktoken_cache = {}

def count_tokens(text: str, model: str = "gpt-4o") -> int:
    """Count tokens using tiktoken (lazy loaded)."""
    if model not in _tiktoken_cache:
        import tiktoken
        _tiktoken_cache[model] = tiktoken.encoding_for_model(model)
    
    encoding = _tiktoken_cache[model]
    return len(encoding.encode(text))

# For Anthropic, use different tokenizer
def count_tokens_anthropic(text: str) -> int:
    """Anthropic token counting (approximation or their SDK)."""
    # Can use anthropic SDK's count_tokens if available
    # Or simple approximation: ~4 chars per token
    return len(text) // 4
```

#### 6. Cost Calculation (`costs.py`)

```python
# Simple cost database (can be JSON file loaded lazily)
COSTS = {
    "gpt-4": {"input": 0.00003, "output": 0.00006},
    "gpt-4-turbo": {"input": 0.00001, "output": 0.00003},
    "claude-3.5-sonnet": {"input": 0.000003, "output": 0.000015},
    # etc.
}

def calculate_cost(model: str, usage: Usage) -> float:
    """Calculate cost for a completion."""
    costs = COSTS.get(model, {"input": 0, "output": 0})
    return (
        usage.prompt_tokens * costs["input"] +
        usage.completion_tokens * costs["output"]
    )
```

## Migration Strategy

### Phase 1: Build New Client (Parallel)
1. Implement core types and base protocol
2. Build OpenAI provider wrapper
3. Build Anthropic provider wrapper (if needed)
4. Build OpenRouter support (reuse OpenAI wrapper)
5. Implement router with fallback logic
6. Add token counting utilities
7. Add cost calculation

### Phase 2: Adapter Layer (Compatibility)
Create adapter that mimics litellm interface:

```python
# good_agent/llm_client/compat.py
"""Compatibility layer for gradual migration."""

from .router import ModelRouter as Router
from .types import ModelResponse, Usage, Choices

# Export litellm-compatible names
__all__ = ['Router', 'ModelResponse', 'Usage', 'Choices']
```

Update imports gradually:
```python
# Before
from litellm.router import Router

# After (temporary)
from good_agent.llm_client.compat import Router

# Final
from good_agent.llm_client import Router
```

### Phase 3: Update Code (Incremental)
1. Update `model/manager.py` to use new Router
2. Update `model/llm.py` to use new types
3. Update `utilities/tokens.py` to use new token counter
4. Update tests to mock new client
5. Remove litellm dependency

### Phase 4: Optimize
1. Profile import times (target <200ms)
2. Add lazy loading where needed
3. Optimize hot paths
4. Add caching for token encodings

## Implementation Details

### Lazy Loading Pattern

```python
# good_agent/llm_client/__init__.py
"""Fast-loading LLM client with lazy provider initialization."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .router import ModelRouter
    from .types import ModelResponse, Usage
else:
    # Lazy imports
    ModelRouter = None
    ModelResponse = None
    Usage = None

def __getattr__(name: str):
    """Lazy load modules on first access."""
    global ModelRouter, ModelResponse, Usage
    
    if name == "ModelRouter":
        if ModelRouter is None:
            from .router import ModelRouter as _Router
            ModelRouter = _Router
        return ModelRouter
    
    elif name in ("ModelResponse", "Usage"):
        if ModelResponse is None:
            from .types import ModelResponse as _MR, Usage as _U
            ModelResponse = _MR
            Usage = _U
        return ModelResponse if name == "ModelResponse" else Usage
    
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = ['ModelRouter', 'ModelResponse', 'Usage']
```

### Provider Detection

```python
def detect_provider(model: str) -> str:
    """Detect provider from model string."""
    if "/" in model:
        provider, _ = model.split("/", 1)
        if provider == "openrouter":
            return "openai"  # OpenRouter uses OpenAI API
        return provider
    
    # Default mappings
    if model.startswith("gpt-"):
        return "openai"
    elif model.startswith("claude-"):
        return "anthropic"
    elif model.startswith("o1-"):
        return "openai"
    
    return "openai"  # default
```

### Instructor Integration

Keep instructor but use it with our client:

```python
import instructor
from good_agent.llm_client import ModelRouter

router = ModelRouter(...)
instructor_client = instructor.from_litellm(router.complete)
```

## Benefits of This Approach

### 1. Performance
- **Import time**: <200ms (vs 5.5s for litellm)
- **Package size**: <500KB (vs 41MB for litellm)
- **Runtime speed**: Direct SDK calls, no middleware overhead

### 2. Maintainability
- Small codebase (<1000 lines vs 20,000+)
- Clear separation of concerns
- Easy to understand and debug
- Provider SDKs handle edge cases

### 3. Flexibility
- Easy to add new providers
- Can customize per-provider behavior
- No global state issues
- Better testing isolation

### 4. Type Safety
- Full typing support
- IDE autocomplete works well
- Catches errors at development time

### 5. Future-Proof
- Provider SDKs stay up-to-date
- Easy to adopt new features
- No maintenance burden for 100 providers

## Risk Mitigation

### Risk 1: Missing Features
**Mitigation**: 
- Implement only what we use (YAGNI principle)
- Add features incrementally as needed
- Most litellm features unused

### Risk 2: Breaking Changes
**Mitigation**:
- Use compatibility layer during transition
- Comprehensive test coverage
- Gradual migration path

### Risk 3: Provider SDK Changes
**Mitigation**:
- Version pin SDKs
- Adapter pattern isolates changes
- Much less risky than litellm internals

### Risk 4: Token Counting Accuracy
**Mitigation**:
- Use tiktoken for OpenAI (official)
- Use Anthropic SDK for Claude
- Document any approximations

## Token Counting Strategy

### OpenAI Models
Use `tiktoken` (official tokenizer):
```python
import tiktoken

def count_tokens_openai(text: str, model: str) -> int:
    encoding = tiktoken.encoding_for_model(model)
    return len(encoding.encode(text))
```

### Anthropic Models
Use approximation or Anthropic SDK:
```python
def count_tokens_anthropic(text: str) -> int:
    # Anthropic: ~4 characters per token
    return len(text) // 4

# Or use Anthropic SDK if they provide it:
# from anthropic import Anthropic
# client.count_tokens(text)
```

### OpenRouter Models
Depends on underlying model - detect and route accordingly.

## Cost Calculation Strategy

Maintain simple cost database (JSON):

```json
{
  "gpt-4": {
    "input_cost_per_token": 0.00003,
    "output_cost_per_token": 0.00006
  },
  "gpt-4-turbo": {
    "input_cost_per_token": 0.00001,
    "output_cost_per_token": 0.00003
  },
  "claude-3.5-sonnet": {
    "input_cost_per_token": 0.000003,
    "output_cost_per_token": 0.000015
  }
}
```

Load lazily and cache in memory.

## Testing Strategy

### Unit Tests
- Mock provider SDKs at the boundary
- Test router fallback logic
- Test token counting accuracy
- Test cost calculations

### Integration Tests
- Use VCR.py for recording real API calls
- Test with actual provider SDKs
- Verify response format compatibility

### Performance Tests
- Measure import time (<200ms target)
- Measure first-call latency
- Compare with litellm baseline

## Timeline Estimate

- **Phase 1** (Build): 2-3 days
- **Phase 2** (Adapter): 0.5 days
- **Phase 3** (Migration): 1-2 days
- **Phase 4** (Optimize): 0.5 days

**Total**: 4-6 days for complete migration

## Success Criteria

1. ✅ Import time <200ms (vs 5.5s)
2. ✅ Package size <1MB (vs 41MB)
3. ✅ All existing tests pass
4. ✅ Token counting within 5% of litellm
5. ✅ Cost calculation accurate
6. ✅ Support OpenAI, Anthropic, OpenRouter
7. ✅ Streaming works correctly
8. ✅ Fallback logic functions
9. ✅ No performance regression in API calls
10. ✅ Full type safety maintained

## Conclusion

**DO NOT extract litellm code.** Instead, build a lightweight client using:
- Native provider SDKs (openai, anthropic)
- Thin abstraction layer
- Lazy loading for fast imports
- Simple, maintainable codebase

This approach will be:
- **27x faster to import** (0.2s vs 5.5s)
- **80x smaller** (0.5MB vs 41MB)
- **Much more maintainable** (1K LOC vs 20K LOC)
- **Better typed** (direct SDK types)
- **More reliable** (official SDKs)

The migration can be done incrementally with minimal risk using a compatibility adapter layer.

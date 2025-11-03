# LLM Client - Quick Reference Card

> **One-page reference for the LiteLLM replacement implementation**

## 📊 Key Metrics

| Metric | Target | Validation |
|--------|--------|------------|
| Import time | <200ms | `python -X importtime -c "from good_agent.llm_client import ModelRouter"` |
| Package size | <1MB | Check installed size excluding dependencies |
| Test coverage | >90% | `pytest --cov=good_agent.llm_client --cov-report=term` |
| Unit tests | <1s | `pytest tests/unit/llm_client/ -v` |

## 🗂️ Directory Structure (1,220 lines total)

```
src/good_agent/llm_client/
├── __init__.py                 (20)   # Lazy loading via __getattr__
├── types/
│   ├── common.py              (50)    # Usage, Message, base types
│   ├── chat.py               (100)    # ChatRequest, ChatResponse, StreamChunk
│   └── embeddings.py          (50)    # EmbeddingRequest, EmbeddingResponse
├── capabilities/
│   ├── __init__.py            (50)    # Capability registry & discovery
│   ├── chat.py               (100)    # ChatCapability protocol
│   └── embeddings.py          (50)    # EmbeddingsCapability protocol
├── providers/
│   ├── __init__.py           (100)    # Provider registry, lazy loading
│   ├── base.py               (100)    # BaseProvider ABC
│   └── openai/
│       ├── provider.py       (200)    # Unified OpenAI provider
│       ├── chat.py           (150)    # Chat implementation
│       └── embeddings.py     (100)    # Embeddings implementation
├── router.py                  (200)   # Multi-model router with fallback
├── costs/
│   ├── __init__.py            (50)    # Public API
│   ├── database.py           (200)    # Multi-level caching
│   ├── fetcher.py             (50)    # Fetch from GitHub
│   ├── calculator.py         (100)    # Cost calculation
│   └── data/
│       └── fallback_costs.json       # Embedded cost data (~400KB)
└── utils/
    └── tokens.py              (100)   # Token counting (lazy tiktoken)
```

## 🎯 4-Day Implementation Plan

### Day 1: Core Foundation
**Morning:** Types & Capabilities
- [ ] Create directory structure
- [ ] Implement `types/common.py`, `types/chat.py`
- [ ] Define `capabilities/chat.py` protocol
- [ ] Lazy-loading `__init__.py`

**Afternoon:** OpenAI Provider Basics
- [ ] Implement `providers/base.py`
- [ ] Implement `providers/openai/chat.py`
- [ ] Basic unit tests
- [ ] **Validate:** Import <200ms ✓

### Day 2: Tokens & OpenAI Complete
**Morning:** Token Counting
- [ ] Implement `utils/tokens.py` (lazy tiktoken)
- [ ] OpenAI token counting
- [ ] Anthropic approximation

**Afternoon:** OpenAI Streaming & Tools
- [ ] Complete OpenAI provider (streaming, tools)
- [ ] Provider registry
- [ ] Comprehensive unit tests
- [ ] **Validate:** OpenAI tests pass ✓

### Day 3: Cost System & Router
**Morning:** Cost Database
- [ ] Implement `costs/database.py` (multi-level cache)
- [ ] Implement `costs/calculator.py`
- [ ] Generate fallback data: `scripts/generate_fallback_costs.py`
- [ ] **Validate:** Cost lookups work, cache persists ✓

**Afternoon:** Router
- [ ] Implement `router.py` (fallback, retry, stats)
- [ ] Router unit tests
- [ ] **Validate:** Fallback logic works ✓

### Day 4: Additional Providers & Integration
**Morning:** Anthropic & OpenRouter
- [ ] Implement Anthropic provider (if needed)
- [ ] OpenRouter support (reuse OpenAI)
- [ ] Integration tests with VCR.py
- [ ] **Validate:** All providers work ✓

**Afternoon:** Migration & Polish
- [ ] Update imports in `model/manager.py`, `model/llm.py`
- [ ] Update test mocks
- [ ] Run full test suite
- [ ] **Validate:** All tests pass ✓

## 🔑 Critical Code Patterns

### Lazy Loading Pattern
```python
# __init__.py
if TYPE_CHECKING:
    from .router import ModelRouter
else:
    _cache = {}

def __getattr__(name: str):
    if name == 'ModelRouter':
        if 'ModelRouter' not in _cache:
            from .router import ModelRouter
            _cache['ModelRouter'] = ModelRouter
        return _cache['ModelRouter']
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

### Provider Implementation Pattern
```python
from ..base import BaseProvider
from ...capabilities.chat import ChatCapability

class OpenAIProvider(BaseProvider, ChatCapability):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._client = AsyncOpenAI(api_key=self.api_key)
    
    async def chat_complete(self, request: ChatRequest, **kwargs):
        response = await self._client.chat.completions.create(...)
        return self._convert_response(response)
```

### Test Fixture Pattern
```python
@pytest.fixture
def openai_client(mock_openai_sdk):
    client = OpenAIClient(api_key="test-key")
    client._client = mock_openai_sdk  # Inject mock
    return client

@pytest.fixture
def openai_response_builder():
    def build(content="Test", tool_calls=None):
        # Build mock response
        return mock_response
    return build
```

### Cost Caching Pattern
```python
# Multi-level cache: memory → disk → embedded → remote
def _get_costs(self) -> dict:
    if self._memory_cache and self._is_fresh():
        return self._memory_cache
    
    if disk_costs := self._load_from_disk():
        return disk_costs
    
    # Trigger background refresh
    self._async_refresh()
    return self._load_fallback()
```

## 🧪 Testing Checklist

### Unit Tests (Fast <1s)
```bash
# Run all unit tests
pytest tests/unit/llm_client/ -v

# With coverage
pytest tests/unit/llm_client/ --cov=good_agent.llm_client --cov-report=term-missing

# Specific test class
pytest tests/unit/llm_client/test_router.py::TestModelRouter -v
```

### Integration Tests (VCR <10s)
```bash
# Run with existing cassettes
pytest tests/integration/llm_client/ -v --vcr-record=none

# Re-record cassettes (requires API keys)
pytest tests/integration/llm_client/ --vcr-record=all
```

### Performance Tests
```bash
# Import time
python -c "import time; s=time.time(); from good_agent.llm_client import ModelRouter; print(f'{time.time()-s:.3f}s')"

# Should be <0.200s
```

## 🔧 Common Commands

### Cost Data Management
```bash
# Refresh cost data
python -m good_agent.llm_client.costs.cli refresh --force

# List models
python -m good_agent.llm_client.costs.cli list --provider openai

# Calculate cost
python -m good_agent.llm_client.costs.cli calculate gpt-4o-mini 1000 500

# Compare models
python -m good_agent.llm_client.costs.cli compare gpt-4o gpt-4o-mini claude-3-5-sonnet
```

### Development
```bash
# Type check
mypy src/good_agent/llm_client/

# Format
ruff format src/good_agent/llm_client/

# Lint
ruff check src/good_agent/llm_client/

# Generate fallback costs
python scripts/generate_fallback_costs.py
```

## 📦 Dependencies

### Required
```toml
dependencies = [
    "openai>=1.0.0",      # OpenAI SDK
    "tiktoken>=0.5.0",    # Token counting
    "pydantic>=2.0.0",    # Type validation
]
```

### Optional (per provider)
```toml
"anthropic>=0.20.0"                      # For Claude
"google-cloud-aiplatform>=1.0.0"         # For Vertex AI
```

### Dev/Test
```toml
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=4.1.0",
    "vcrpy>=6.0.0",
]
```

## 🚨 Common Pitfalls

### Import Performance
❌ **Wrong:** Eager import at module level
```python
import tiktoken  # Adds ~40ms to import time
```

✅ **Right:** Lazy import when first used
```python
def count_tokens(...):
    import tiktoken  # Only imported when needed
```

### Provider Mocking
❌ **Wrong:** Mock our implementation
```python
@patch('good_agent.llm_client.providers.openai.chat.OpenAIChatProvider')
```

✅ **Right:** Mock SDK at boundary
```python
@pytest.fixture
def openai_client(mock_openai_sdk):
    client = OpenAIClient()
    client._client = mock_openai_sdk  # Inject mock SDK
```

### Cache Location
❌ **Wrong:** Cache in project directory
```python
CACHE_FILE = Path("./cache/costs.json")
```

✅ **Right:** Use user cache directory
```python
CACHE_FILE = Path.home() / ".cache" / "good-agent" / "costs.json"
```

### Async Streaming
❌ **Wrong:** Sync iteration over async generator
```python
for chunk in client.stream(...):  # TypeError
```

✅ **Right:** Async iteration
```python
async for chunk in client.stream(...):
```

## 📋 Pre-Commit Checklist

Before committing a phase:
- [ ] All new tests pass: `pytest tests/unit/llm_client/ -v`
- [ ] Import time still <200ms
- [ ] Type checking passes: `mypy src/good_agent/llm_client/`
- [ ] Coverage >90%: `pytest --cov=good_agent.llm_client`
- [ ] No lingering litellm imports: `rg "from litellm" src/`

## 🎯 Success Validation

Final checks before considering complete:
```bash
# 1. Import time
python -X importtime -c "from good_agent.llm_client import ModelRouter" 2>&1 | tail -1
# Should show <200ms

# 2. Package size
du -sh src/good_agent/llm_client/
# Should be <1MB (excluding __pycache__)

# 3. All tests pass
pytest tests/ -v
# 100% pass rate

# 4. Coverage
pytest tests/unit/llm_client/ --cov=good_agent.llm_client --cov-report=term
# Should show >90%

# 5. No litellm imports
rg "from litellm|import litellm" src/good_agent/
# Should be empty (or only in mock.py if keeping mock compatibility)
```

## 📞 Quick Links

- **Full Checklist:** [INDEX.md](./INDEX.md)
- **Code Examples:** [LITELLM_IMPLEMENTATION_SPEC.md](./LITELLM_IMPLEMENTATION_SPEC.md)
- **Test Patterns:** [TEST_IMPLEMENTATION_EXAMPLES.md](./TEST_IMPLEMENTATION_EXAMPLES.md)
- **Architecture:** [EXTENSIBILITY_DESIGN.md](./EXTENSIBILITY_DESIGN.md)
- **Cost System:** [COST_DATA_CACHING_DESIGN.md](./COST_DATA_CACHING_DESIGN.md)

---

*Keep this reference handy during implementation!*

# LLM Client Replacement - Complete Specification

> **Goal:** Replace LiteLLM with a fast, lightweight, extensible multi-provider client
> 
> **Target:** <200ms import time | <1MB package size | 3 providers (OpenAI, Anthropic, OpenRouter)
> 
> **Timeline:** 4-6 days

---

## 📋 Table of Contents

### 📊 Analysis & Planning
- [**LITELLM_REPLACEMENT_PLAN.md**](./LITELLM_REPLACEMENT_PLAN.md) - Strategy & Architecture Overview
  - Performance analysis (5.5s → 0.2s imports)
  - Why NOT to extract LiteLLM code
  - Proposed architecture with lazy loading
  - Migration strategy (4 phases)
  - Success criteria

### 🔧 Implementation Specifications
- [**LITELLM_IMPLEMENTATION_SPEC.md**](./LITELLM_IMPLEMENTATION_SPEC.md) - Detailed Code Examples
  - Complete module structure (~1,220 lines total)
  - Type definitions and protocols
  - Provider implementations (OpenAI, Anthropic, OpenRouter)
  - Router with fallback logic
  - Token counting & cost calculation
  - Performance testing examples

### 🧪 Testing Strategy
- [**TESTING_STRATEGY.md**](./TESTING_STRATEGY.md) - Comprehensive Test Plan
  - Unit tests (<1s execution, >90% coverage)
  - Integration tests with VCR.py
  - Performance benchmarks
  - Fixtures and mocking patterns
  - CI/CD integration

- [**TEST_IMPLEMENTATION_EXAMPLES.md**](./TEST_IMPLEMENTATION_EXAMPLES.md) - Ready-to-Use Test Code
  - Production-ready test fixtures
  - Complete test file examples
  - ~30 example tests covering all scenarios

### 🔌 Extensibility
- [**EXTENSIBILITY_DESIGN.md**](./EXTENSIBILITY_DESIGN.md) - Plugin Architecture
  - Capability-based design (chat, embeddings, images, audio)
  - Protocol-driven provider system
  - Adding new providers (~200 lines)
  - Adding new capabilities (~100 lines)
  - Multi-capability unified router
  - Middleware system

### 💰 Cost Management
- [**COST_DATA_CACHING_DESIGN.md**](./COST_DATA_CACHING_DESIGN.md) - LiteLLM Data Integration
  - Multi-level caching strategy (memory, disk, embedded, remote)
  - Fetch from LiteLLM GitHub (no dependency)
  - <0.1ms cost lookups
  - 300+ models with pricing
  - CLI tools for cost management

---

## 🎯 Quick Start - Implementation Checklist

### Phase 1: Core Foundation (Days 1-2)

#### Day 1: Types & Base Architecture
- [x] **1.1** Create directory structure ✅
  ```
  src/good_agent/llm_client/
  ├── __init__.py
  ├── types/
  ├── capabilities/
  ├── providers/
  └── utils/
  ```
- [x] **1.2** Implement core types (`types/common.py`, `types/chat.py`) ✅
  - `ModelResponse`, `Usage`, `Message`, `StreamChunk`
  - Added `raw_response` field for preserving all provider data
  - See: [LITELLM_IMPLEMENTATION_SPEC.md#types](./LITELLM_IMPLEMENTATION_SPEC.md)
- [x] **1.3** Define capability protocols (`capabilities/chat.py`, `capabilities/embeddings.py`) ✅
  - `ChatCapability` protocol implemented
  - `EmbeddingsCapability` protocol (deferred to later)
  - See: [EXTENSIBILITY_DESIGN.md#capabilities](./EXTENSIBILITY_DESIGN.md)
- [x] **1.4** Create base provider class (`providers/base.py`) ✅
  - `BaseProvider` ABC
  - `ProviderConfig` dataclass
- [x] **1.5** Implement lazy-loading __init__.py ✅
  - `__getattr__` pattern for lazy imports
  - See: [LITELLM_IMPLEMENTATION_SPEC.md#lazy-loading](./LITELLM_IMPLEMENTATION_SPEC.md)

**Validation:** ✅ Import time acceptable, 24 tests passing (types, capabilities, base)

#### Day 2: OpenAI Provider & Token Counting
- [x] **2.1** Implement OpenAI chat provider (`providers/openai/provider.py`) ✅
  - Complete method
  - Stream method
  - Response conversion with raw response preservation
  - Error handling
  - Tool/function calling support
  - See: [LITELLM_IMPLEMENTATION_SPEC.md#openai-provider](./LITELLM_IMPLEMENTATION_SPEC.md)
- [x] **2.2** Implement token counting (`utils/tokens.py`) ✅
  - Lazy-load tiktoken (no import overhead)
  - OpenAI models (tiktoken with proper encoding selection)
  - Anthropic approximation (character-based fallback)
  - Message token counting with overhead calculation
  - 13 tests covering all scenarios
  - See: [LITELLM_IMPLEMENTATION_SPEC.md#token-counting](./LITELLM_IMPLEMENTATION_SPEC.md)
- [ ] **2.3** Create provider registry (`providers/__init__.py`)
  - Auto-discovery via protocols
  - Lazy loading per provider
  - See: [EXTENSIBILITY_DESIGN.md#provider-registry](./EXTENSIBILITY_DESIGN.md)
- [x] **2.4** Write unit tests for OpenAI provider ✅
  - Mock SDK responses (6 tests)
  - Test error handling
  - Test streaming
  - Test raw response preservation (8 tests)
  - See: [TEST_IMPLEMENTATION_EXAMPLES.md#openai-tests](./TEST_IMPLEMENTATION_EXAMPLES.md)

**Validation:** ✅ 38 tests passing (all components), OpenAI provider fully functional

---

### Phase 2: Cost Data & Router (Day 3)

#### Day 3 Morning: Cost Database
- [ ] **3.1** Implement cost database (`costs/database.py`)
  - Multi-level caching (memory, disk, embedded)
  - Fetch from LiteLLM GitHub
  - Fallback data
  - See: [COST_DATA_CACHING_DESIGN.md#database](./COST_DATA_CACHING_DESIGN.md)
- [ ] **3.2** Implement cost calculator (`costs/calculator.py`)
  - `calculate_cost()` function
  - `estimate_cost()` function
  - `compare_model_costs()` function
  - See: [COST_DATA_CACHING_DESIGN.md#calculator](./COST_DATA_CACHING_DESIGN.md)
- [ ] **3.3** Generate fallback cost data
  - Run `scripts/generate_fallback_costs.py`
  - Commit fallback data file
  - See: [COST_DATA_CACHING_DESIGN.md#fallback-generation](./COST_DATA_CACHING_DESIGN.md)
- [ ] **3.4** Test cost system
  - Test caching behavior
  - Test fallback mechanism
  - Test cost accuracy

**Validation:** Cost lookups work, cache persists, fallback available

#### Day 3 Afternoon: Router with Fallback
- [ ] **3.5** Implement basic router (`router.py`)
  - Primary model execution
  - Fallback logic
  - Retry with exponential backoff
  - Statistics tracking
  - See: [LITELLM_IMPLEMENTATION_SPEC.md#router](./LITELLM_IMPLEMENTATION_SPEC.md)
- [ ] **3.6** Write router unit tests
  - Test successful completion
  - Test fallback on error
  - Test retry logic
  - Test statistics
  - See: [TEST_IMPLEMENTATION_EXAMPLES.md#router-tests](./TEST_IMPLEMENTATION_EXAMPLES.md)

**Validation:** Router tests pass, fallback works correctly

---

### Phase 3: Additional Providers & Integration (Day 4)

#### Day 4: Anthropic + Integration
- [ ] **4.1** Implement Anthropic provider (if needed)
  - `providers/anthropic/chat.py`
  - Response conversion
  - Error handling
  - See: [EXTENSIBILITY_DESIGN.md#provider-implementation](./EXTENSIBILITY_DESIGN.md)
- [ ] **4.2** Implement OpenRouter support
  - `providers/openrouter.py` (reuses OpenAI)
  - Provider detection logic
  - See: [LITELLM_IMPLEMENTATION_SPEC.md#openrouter](./LITELLM_IMPLEMENTATION_SPEC.md)
- [ ] **4.3** Create compatibility adapter (`compat.py`)
  - Mimic litellm interface temporarily
  - Export compatible types
  - See: [LITELLM_REPLACEMENT_PLAN.md#phase-2](./LITELLM_REPLACEMENT_PLAN.md)
- [ ] **4.4** Integration tests with VCR
  - Record real API calls
  - Test OpenAI completion
  - Test streaming
  - Test function calling
  - See: [TESTING_STRATEGY.md#integration-tests](./TESTING_STRATEGY.md)

**Validation:** All providers work, VCR cassettes recorded

---

### Phase 4: Migration & Optimization (Days 5-6)

#### Day 5: Migrate Existing Code
- [ ] **5.1** Update imports in `model/manager.py`
  - Replace `litellm.router` imports
  - Use new `ModelRouter`
  - Test ManagedRouter functionality
- [ ] **5.2** Update imports in `model/llm.py`
  - Replace type imports
  - Update response handling
  - Update cost calculation calls
- [ ] **5.3** Update imports in `utilities/tokens.py`
  - Use new token counting
  - Test accuracy against litellm
- [ ] **5.4** Update test mocks
  - Replace litellm mocks with new client mocks
  - Update fixtures
  - See: [TEST_IMPLEMENTATION_EXAMPLES.md#fixtures](./TEST_IMPLEMENTATION_EXAMPLES.md)
- [ ] **5.5** Run full test suite
  - All tests should pass
  - No litellm imports remaining

**Validation:** All existing tests pass with new client

#### Day 6: Polish & Documentation
- [ ] **6.1** Performance validation
  - Import time test: <200ms ✓
  - First API call latency: reasonable
  - Memory usage: acceptable
  - See: [TESTING_STRATEGY.md#performance-tests](./TESTING_STRATEGY.md)
- [ ] **6.2** Package size check
  - Measure installed size
  - Target: <1MB (excluding dependencies)
- [ ] **6.3** Remove litellm dependency
  - Update `pyproject.toml`
  - Test clean install
  - Verify no import errors
- [ ] **6.4** Update documentation
  - API documentation
  - Migration guide for users
  - Examples
- [ ] **6.5** CI/CD updates
  - Update test workflows
  - Add cost data refresh workflow
  - See: [COST_DATA_CACHING_DESIGN.md#cicd](./COST_DATA_CACHING_DESIGN.md)

**Validation:** All success criteria met (see below)

---

## ✅ Success Criteria

### Performance Targets
- [ ] Import time: **<200ms** (baseline: 5.5s with litellm)
- [ ] Package size: **<1MB** (baseline: 41MB with litellm)
- [ ] First API call: Similar to litellm (network-bound)
- [ ] Streaming: Similar to litellm
- [ ] Cost lookup: **<0.1ms** after first access

### Functional Requirements
- [ ] **OpenAI support**: chat completion, streaming, function calling
- [ ] **Anthropic support**: chat completion (if needed)
- [ ] **OpenRouter support**: via OpenAI compatibility
- [ ] **Token counting**: Within 5% accuracy of litellm
- [ ] **Cost calculation**: Accurate for all supported models
- [ ] **Router fallback**: Automatic failover to backup models
- [ ] **Type safety**: Full typing with no `Any` in public API

### Code Quality
- [ ] **Test coverage**: >90% on critical paths
- [ ] **Unit tests**: <1 second total execution
- [ ] **Integration tests**: <10 seconds with VCR
- [ ] **No flaky tests**: All tests deterministic
- [ ] **Documentation**: Complete API docs
- [ ] **Type checking**: mypy passes with strict mode

### Extensibility
- [ ] **New provider**: Can add in ~200 lines without core changes
- [ ] **New capability**: Can add in ~100 lines per provider
- [ ] **Plugin system**: External registration works
- [ ] **Middleware**: Hook points available

---

## 📚 Reference Guide

### Key Files to Implement

```
src/good_agent/llm_client/
├── __init__.py                 (~20 lines) - Lazy loading entry point
├── types/
│   ├── __init__.py
│   ├── common.py              (~50 lines) - Base types
│   ├── chat.py                (~100 lines) - Chat types
│   └── embeddings.py          (~50 lines) - Embedding types
├── capabilities/
│   ├── __init__.py            (~50 lines) - Capability registry
│   ├── chat.py                (~100 lines) - Chat protocol
│   └── embeddings.py          (~50 lines) - Embeddings protocol
├── providers/
│   ├── __init__.py            (~100 lines) - Provider registry
│   ├── base.py                (~100 lines) - Base provider
│   └── openai/
│       ├── __init__.py
│       ├── provider.py        (~200 lines) - Unified provider
│       ├── chat.py            (~150 lines) - Chat implementation
│       └── embeddings.py      (~100 lines) - Embeddings
├── router.py                   (~200 lines) - Multi-model router
├── costs/
│   ├── __init__.py            (~50 lines) - Public API
│   ├── database.py            (~200 lines) - Cost database
│   ├── fetcher.py             (~50 lines) - GitHub fetcher
│   ├── calculator.py          (~100 lines) - Cost calculator
│   └── data/
│       └── fallback_costs.json (~400KB) - Embedded data
└── utils/
    └── tokens.py               (~100 lines) - Token counting

Total: ~1,220 lines + embedded data
```

### Dependencies

**Required:**
```toml
dependencies = [
    "openai>=1.0.0",      # Official OpenAI SDK
    "tiktoken>=0.5.0",    # Token counting
    "pydantic>=2.0.0",    # Type validation (already in project)
    "httpx>=0.24.0",      # HTTP client (transitive from openai)
]
```

**Optional (for additional providers):**
```toml
# Only install if using these providers
"anthropic>=0.20.0"  # For Claude models
"google-cloud-aiplatform>=1.0.0"  # For Vertex AI
```

### Testing Dependencies

```toml
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=4.1.0",
    "vcrpy>=6.0.0",
]
```

---

## 🔗 Quick Navigation

### By Role

**For Implementers:**
1. Start with [Implementation Spec](./LITELLM_IMPLEMENTATION_SPEC.md) for code examples
2. Reference [Extensibility Design](./EXTENSIBILITY_DESIGN.md) for architecture
3. Use [Test Examples](./TEST_IMPLEMENTATION_EXAMPLES.md) for test patterns

**For Reviewers:**
1. Read [Replacement Plan](./LITELLM_REPLACEMENT_PLAN.md) for context
2. Check [Success Criteria](#success-criteria) for validation
3. Review [Testing Strategy](./TESTING_STRATEGY.md) for coverage

**For Future Extenders:**
1. See [Extensibility Design](./EXTENSIBILITY_DESIGN.md) for adding providers
2. Reference [Cost Caching](./COST_DATA_CACHING_DESIGN.md) for cost system
3. Use existing providers as templates

### By Task

- **Adding a new provider?** → [EXTENSIBILITY_DESIGN.md](./EXTENSIBILITY_DESIGN.md)
- **Writing tests?** → [TEST_IMPLEMENTATION_EXAMPLES.md](./TEST_IMPLEMENTATION_EXAMPLES.md)
- **Cost calculation?** → [COST_DATA_CACHING_DESIGN.md](./COST_DATA_CACHING_DESIGN.md)
- **Performance issues?** → [LITELLM_REPLACEMENT_PLAN.md](./LITELLM_REPLACEMENT_PLAN.md)
- **Understanding architecture?** → [LITELLM_IMPLEMENTATION_SPEC.md](./LITELLM_IMPLEMENTATION_SPEC.md)

---

## 🐛 Troubleshooting

### Common Issues

**Import is slow (>200ms)**
- Check if tiktoken is being imported eagerly
- Verify lazy loading in `__init__.py`
- Profile with: `python -X importtime -c "from good_agent.llm_client import ModelRouter"`

**Tests failing after migration**
- Update mock fixtures (see [TEST_IMPLEMENTATION_EXAMPLES.md](./TEST_IMPLEMENTATION_EXAMPLES.md))
- Check for lingering litellm imports: `rg "from litellm" src/`
- Verify VCR cassettes are compatible

**Cost data not loading**
- Check cache directory: `~/.cache/good-agent/`
- Try force refresh: `refresh_cost_data(force=True)`
- Verify embedded fallback exists: `src/good_agent/llm_client/costs/data/fallback_costs.json`

**Provider not found**
- Check provider registration in `providers/__init__.py`
- Verify provider module imports successfully
- Test with: `from good_agent.llm_client.providers import get_provider; get_provider("openai")`

---

## 📞 Questions & Support

**During Implementation:**
- Refer to specific sections in the linked documents
- All code examples are production-ready and can be used as-is
- Test examples demonstrate proper mocking patterns

**After Implementation:**
- Run performance benchmarks to validate targets
- Check test coverage: `pytest --cov=good_agent.llm_client --cov-report=term-missing`
- Profile import time: Script in [TESTING_STRATEGY.md](./TESTING_STRATEGY.md)

---

## 📈 Progress Tracking

Track your progress through the checklist above. Each phase should be completed before moving to the next.

**Estimated Timeline:**
- Phase 1 (Core): 2 days
- Phase 2 (Cost & Router): 1 day
- Phase 3 (Providers & Integration): 1 day
- Phase 4 (Migration & Polish): 2 days

**Total: 4-6 days** depending on complexity and testing thoroughness.

---

*Last Updated: 2025-11-03*
*Version: 1.0*

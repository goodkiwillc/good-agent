# LLM Client Specification

> Complete specification for replacing LiteLLM with a fast, lightweight, extensible multi-provider client.

## 🎯 Overview

This directory contains the complete design and implementation specifications for building a new LLM client that replaces the bloated LiteLLM library with a focused, high-performance alternative.

**Key Goals:**
- **27x faster imports** (200ms vs 5.5s)
- **80x smaller package** (1MB vs 41MB)
- **95% less code** (1,200 lines vs 20,000+)
- **Full extensibility** for new providers and capabilities

## 🚀 Quick Start

**New to this project?** Start here:

1. Read [**INDEX.md**](./INDEX.md) - Complete implementation checklist with links to all specs
2. Review [**LITELLM_REPLACEMENT_PLAN.md**](./LITELLM_REPLACEMENT_PLAN.md) - Understand the "why" and high-level strategy
3. Follow the [Phase 1 checklist in INDEX.md](./INDEX.md#phase-1-core-foundation-days-1-2) to begin implementation

**Ready to implement?** Jump to:
- [Implementation Checklist](./INDEX.md#quick-start---implementation-checklist) - Day-by-day todo list
- [Code Examples](./LITELLM_IMPLEMENTATION_SPEC.md) - Production-ready code snippets
- [Test Patterns](./TEST_IMPLEMENTATION_EXAMPLES.md) - Copy-paste test fixtures

## 📁 Document Structure

### Core Planning Documents

| Document | Purpose | Audience |
|----------|---------|----------|
| [**INDEX.md**](./INDEX.md) | Master checklist & navigation | Everyone - **start here** |
| [**LITELLM_REPLACEMENT_PLAN.md**](./LITELLM_REPLACEMENT_PLAN.md) | Strategy & rationale | Reviewers, decision makers |

### Implementation Specifications

| Document | Purpose | Lines of Code | Time to Implement |
|----------|---------|---------------|-------------------|
| [**LITELLM_IMPLEMENTATION_SPEC.md**](./LITELLM_IMPLEMENTATION_SPEC.md) | Core client implementation | ~600 lines | 2 days |
| [**EXTENSIBILITY_DESIGN.md**](./EXTENSIBILITY_DESIGN.md) | Plugin architecture | ~400 lines | 1 day |
| [**COST_DATA_CACHING_DESIGN.md**](./COST_DATA_CACHING_DESIGN.md) | Cost database system | ~220 lines | 0.5 days |

### Testing Documentation

| Document | Purpose | Test Count | Coverage Target |
|----------|---------|------------|-----------------|
| [**TESTING_STRATEGY.md**](./TESTING_STRATEGY.md) | Test approach & patterns | - | >90% |
| [**TEST_IMPLEMENTATION_EXAMPLES.md**](./TEST_IMPLEMENTATION_EXAMPLES.md) | Ready-to-use tests | ~30 tests | Critical paths |

## 📊 Key Metrics

### Performance Comparison

| Metric | LiteLLM | Our Target | Improvement |
|--------|---------|------------|-------------|
| Import time | 5.470s | <0.200s | **27x faster** |
| Package size | 41MB | <1MB | **80x smaller** |
| Lines of code | ~20,000 | ~1,200 | **95% reduction** |
| Providers needed | 100+ | 3 | Focused scope |

### Timeline

- **Total: 4-6 days**
- Phase 1 (Core): 2 days
- Phase 2 (Cost & Router): 1 day
- Phase 3 (Providers): 1 day
- Phase 4 (Migration): 2 days

## 🎓 Learning Path

### For Implementers

**Day 1 Morning:**
1. Read [LITELLM_REPLACEMENT_PLAN.md](./LITELLM_REPLACEMENT_PLAN.md) (30 min)
2. Review [LITELLM_IMPLEMENTATION_SPEC.md](./LITELLM_IMPLEMENTATION_SPEC.md) - Types section (30 min)
3. Start Phase 1.1-1.3 from [INDEX.md checklist](./INDEX.md#phase-1-core-foundation-days-1-2)

**Day 1 Afternoon:**
1. Continue Phase 1.4-1.5 implementation
2. Reference [TEST_IMPLEMENTATION_EXAMPLES.md](./TEST_IMPLEMENTATION_EXAMPLES.md) for test patterns
3. Validate import time <200ms

**Day 2 onwards:**
- Follow [INDEX.md checklist](./INDEX.md#quick-start---implementation-checklist) sequentially
- Reference specs as needed for implementation details
- Run tests after each phase

### For Reviewers

1. **Context** → [LITELLM_REPLACEMENT_PLAN.md](./LITELLM_REPLACEMENT_PLAN.md) - Why we're doing this
2. **Architecture** → [EXTENSIBILITY_DESIGN.md](./EXTENSIBILITY_DESIGN.md) - How it's designed
3. **Quality** → [TESTING_STRATEGY.md](./TESTING_STRATEGY.md) - How we validate
4. **Checklist** → [INDEX.md](./INDEX.md) - What needs to be done

### For Future Maintainers

**Adding a new provider?**
- See [EXTENSIBILITY_DESIGN.md - Adding a New Provider](./EXTENSIBILITY_DESIGN.md#6-adding-a-new-provider-google-vertex-ai)
- ~200 lines, no core changes needed

**Adding a new capability (e.g., audio)?**
- See [EXTENSIBILITY_DESIGN.md - Capability Protocols](./EXTENSIBILITY_DESIGN.md#1-capability-based-architecture)
- Define protocol (~50 lines)
- Implement in providers (~100 lines each)

**Updating cost data?**
- See [COST_DATA_CACHING_DESIGN.md](./COST_DATA_CACHING_DESIGN.md)
- Automatic: Background refresh every 24h
- Manual: `refresh_cost_data(force=True)`

## 🔧 Architecture at a Glance

```
good_agent.llm_client/
├── Core (~370 lines)
│   ├── __init__.py          # Lazy loading
│   ├── types/               # Type definitions
│   └── capabilities/        # Protocol definitions
│
├── Providers (~450 lines)
│   ├── base.py             # Base provider class
│   ├── openai/             # OpenAI implementation
│   ├── anthropic/          # Anthropic implementation
│   └── openrouter/         # OpenRouter (reuses OpenAI)
│
├── Router (~200 lines)
│   └── router.py           # Multi-model fallback
│
└── Utils (~200 lines)
    ├── tokens.py           # Token counting
    └── costs/              # Cost calculation + caching
```

**Design Principles:**
1. **Lazy Loading** - Import only what's used
2. **Native SDKs** - Wrap official libraries, don't reimplement
3. **Protocol-Driven** - Capability-based composition
4. **Plugin-Friendly** - Add providers without touching core

## ✅ Success Criteria

Before considering this complete, verify:

- [ ] Import time: <200ms (test with `python -X importtime`)
- [ ] Package size: <1MB (excluding dependencies)
- [ ] All 3 providers work: OpenAI, Anthropic, OpenRouter
- [ ] Token counting: Within 5% of LiteLLM accuracy
- [ ] Cost calculation: Accurate for all models
- [ ] Test coverage: >90% on critical paths
- [ ] All existing tests pass with new client
- [ ] No performance regression vs LiteLLM in API calls

Full criteria in [INDEX.md - Success Criteria](./INDEX.md#success-criteria)

## 🐛 Common Questions

**Q: Why not extract parts of LiteLLM?**
A: LiteLLM is 20,000+ lines with deep coupling, global state, and poor architecture. Building from scratch with native SDKs is faster and cleaner. See [LITELLM_REPLACEMENT_PLAN.md](./LITELLM_REPLACEMENT_PLAN.md#why-not-to-extract-litellm-code).

**Q: How do we maintain cost data without LiteLLM?**
A: Fetch from LiteLLM's public GitHub JSON, cache aggressively (memory + disk + embedded fallback). See [COST_DATA_CACHING_DESIGN.md](./COST_DATA_CACHING_DESIGN.md).

**Q: Can we add more providers later?**
A: Yes! The capability-based architecture makes it easy. ~200 lines per provider. See [EXTENSIBILITY_DESIGN.md](./EXTENSIBILITY_DESIGN.md).

**Q: What if our needs change?**
A: The design supports new capabilities (embeddings, images, audio) without core changes. See [EXTENSIBILITY_DESIGN.md - Capability Protocols](./EXTENSIBILITY_DESIGN.md#1-capability-based-architecture).

**Q: Is this production-ready code?**
A: Yes! All code examples are production-quality with proper error handling, typing, and tests.

## 📞 Getting Help

**During implementation:**
- Check [INDEX.md](./INDEX.md) for the complete checklist
- Reference specific sections in the linked documents
- All code examples are copy-paste ready

**Stuck on a specific task?**
- Testing? → [TEST_IMPLEMENTATION_EXAMPLES.md](./TEST_IMPLEMENTATION_EXAMPLES.md)
- Architecture? → [EXTENSIBILITY_DESIGN.md](./EXTENSIBILITY_DESIGN.md)
- Performance? → [LITELLM_REPLACEMENT_PLAN.md](./LITELLM_REPLACEMENT_PLAN.md)

**After implementation:**
- Validate against [Success Criteria](./INDEX.md#success-criteria)
- Run performance benchmarks
- Check test coverage

## 🎉 Benefits

Once complete, you'll have:

✅ **Fast** - 27x faster imports, instant token/cost lookups
✅ **Small** - 80x smaller package, minimal dependencies  
✅ **Maintainable** - 95% less code, clear architecture
✅ **Extensible** - Easy to add providers/capabilities
✅ **Tested** - >90% coverage, deterministic tests
✅ **Cost-Aware** - 300+ models with automatic price updates

All while maintaining feature parity with LiteLLM for the 3 providers we care about.

---

**Ready to begin?** → [Start with INDEX.md](./INDEX.md)

*Last Updated: 2025-11-03*
*Version: 1.0*

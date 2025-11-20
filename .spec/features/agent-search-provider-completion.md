# Feature Spec: Productionize AgentSearch Providers

**Status**: Draft  
**Created**: 2025-11-20  
**Owner**: Droid  
**Related**: `tests/integration/search/test_search_providers.py`, `tests/integration/search/test_search_query_handling.py`

## Overview

`AgentSearch` already wires together the `SearchProviderRegistry`, exposes `search` / `search_entities` / `trending_topics` tools, parallelises provider calls, and performs light result deduplication. The registry can ingest manually supplied providers and even has entry-point discovery plus constraint-based routing, and we have extensive mocked integration tests covering query building, error handling, concurrency, and performance. What is missing is the actual provider ecosystem and production-grade plumbing: there are no built-in providers, the auto-discovery path has no entry points or configuration flow, entity + trend support reuse generic search calls, advanced `SearchQuery` fields are unreachable from the tool interface, and real-world concerns (timeouts, retries, instrumentation, and documentation for plugin authors) are absent. This spec defines the remaining work required to ship a usable, configurable search provider system.

## Requirements

1. **Provider packaging & configuration**: Define a concrete provider configuration contract (e.g., `SearchProviderConfig`) that can load API credentials and per-provider settings from agent configs/env vars, register providers via entry points declared in `pyproject.toml`, and allow users to enable/disable providers explicitly.
2. **First-party provider implementations**: Ship at least one built-in web/news provider (ValueSerp or Tavily) and one social/entity provider (Twitter/X or Reddit), backed by typed API clients, respecting rate limits, and registering `ProviderCapability` metadata on instantiation.
3. **Extended tool surface**: Expose the richer `SearchQuery` fields (hashtags, language, country, author filters, media flags, engagement thresholds) as parameters on the `search` tool, and ensure entity searches accept structured filters without string concatenation.
4. **Specialised operations**: Evolve the `SearchProvider` protocol so providers can implement dedicated `search_entities` and `fetch_trends`/`analyze` coroutines (instead of piggybacking on `search`), update `ProviderCapability` to describe these operations, and adapt `AgentSearch` to dispatch accordingly.
5. **Resilience & selection improvements**: Introduce provider-level timeouts, retries with exponential backoff, structured error reporting, and richer scoring in `_score_provider` (e.g., consider historical latency + success rate). Upgrade deduplication to combine same-URL results across providers and support optional cross-provider ranking by `relevance_score`.
6. **Testability & developer ergonomics**: Unskip the current entry-point discovery tests by supplying deterministic stub providers, add VCR-backed integration tests for the real providers (behind an opt-in marker), and produce author guidance (docstrings + `.spec` notes) for building third-party providers without editing core files.

## Implementation Notes

- **Configuration & discovery** (`src/good_agent/extensions/search/providers.py`, `pyproject.toml`): add an explicit `SearchProviderConfig` dataclass, loadable from `Agent` settings, and hand it into providers via factory methods. Register built-in providers under the `good_agent.search_providers` entry-point group and teach `discover_providers` to merge manual registrations with config-driven overrides while logging redacted configuration issues.
- **API client layering** (`src/good_agent/extensions/search/providers/`): implement typed clients (using `httpx` under `uv run`) with response models validated by Pydantic, encapsulate rate-limit headers, and surface provider capability metrics (freshness, completeness, cost) from configuration.
- **Tool signature expansion** (`src/good_agent/extensions/search/component.py`): add optional parameters for the remaining `SearchQuery` fields with validation, convert entity filters into structured attributes instead of string concatenation, and ensure defaults remain backwards compatible.
- **Provider protocol updates** (`src/good_agent/extensions/search/providers.py`): extend the `SearchProvider` Protocol with optional `async def search_entities(...)` and `async def fetch_trends(...)` hooks (fallback to raising `NotImplementedError`), update `BaseSearchProvider` to provide safe defaults, and teach `AgentSearch.search_entities` / `.trending_topics` to call the specialised hooks when available.
- **Resilience utilities** (`src/good_agent/extensions/search/component.py`): wrap provider calls with `asyncio.timeout`, exponential retry helpers, and structured error payloads (e.g., `SearchError` dataclass) so the agent can surface partial failures. Replace `_deduplicate_results` with a helper that canonicalises by URL + normalised content hash and optionally merges metrics.
- **Testing**: create stub providers under `tests/support/providers.py` for deterministic discovery, unskip the integration tests, add new tests covering configuration loading, scoring logic, and specialised operations, and gate external API calls behind markers/env checks so CI remains deterministic.

## Todo List

1. Introduce `SearchProviderConfig` + config loading helpers and wire them through `SearchProviderRegistry.discover_providers`.
2. Define entry points in `pyproject.toml` and implement built-in provider modules (`valueserp.py`, `twitter.py` or equivalent) with typed API layers.
3. Extend `AgentSearch.search` and `SearchQuery` usage to accept full filter surface, and refactor entity query construction to avoid string munging.
4. Update the `SearchProvider` protocol/Base class for specialised entity & trend hooks; adjust `AgentSearch` to use them.
5. Implement timeout/retry handling, enhanced deduplication, and improved provider scoring (including persistence of recent latency/error metrics).
6. Add deterministic stub providers + unskip discovery tests; create VCR-backed tests for real providers behind `-m external` marker.
7. Document provider authoring guidelines via docstrings and a short `.spec` note referenced from `DECISIONS.md`.

## Testing Strategy

- `uv run pytest tests/integration/search -m 'not external'`
- `uv run pytest tests/integration/search -m external` (requires provider API keys)
- `uv run pytest tests/unit --maxfail=1`
- `uv run ruff check src/good_agent/extensions/search`

# Technical Debt & Future Improvements

> **Format**: `[PRIORITY] - [AREA] - Description (Proposed Solution)`

## Future Features (Backlog)

- [LOW] - [EventRouter] - **Partial Event Matching**: The current `EventRouter` supports exact matches and global wildcards (`*`). It does not support glob-style partial matching (e.g., `message:*` or `system:*:error`).
  - *Proposal*: Implement a Trie or specialized lookup structure in `HandlerRegistry` if performance-critical pattern matching is needed. Current O(1) dict lookup is preferred for performance until a concrete use case demands regex/glob routing.

- [MEDIUM] - [Testing] - **Unified Mocking Strategy for Docs**: Documentation examples currently use `pytest-vcr` (`llm_vcr` fixture) to transparently mock LLM calls. While this keeps example code clean ("Record & Forget"), it bypasses the library's native `agent.mock` system, creating two separate mocking patterns.
  - *Proposal*: Investigate transparent injection of `agent.mock` handlers via pytest fixtures to unify on a single mocking primitive, ensuring doc tests validate the library's own mocking capabilities while maintaining zero-change requirements for example code.

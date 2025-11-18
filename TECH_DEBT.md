# Technical Debt & Future Improvements

> **Format**: `[PRIORITY] - [AREA] - Description (Proposed Solution)`

## Future Features (Backlog)

- [LOW] - [EventRouter] - **Partial Event Matching**: The current `EventRouter` supports exact matches and global wildcards (`*`). It does not support glob-style partial matching (e.g., `message:*` or `system:*:error`).
  - *Proposal*: Implement a Trie or specialized lookup structure in `HandlerRegistry` if performance-critical pattern matching is needed. Current O(1) dict lookup is preferred for performance until a concrete use case demands regex/glob routing.

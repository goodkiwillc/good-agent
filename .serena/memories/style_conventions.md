# Style & Conventions
- **Typing:** Use full type hints, prefer `ParamSpec`, `TypeVar`, and Pydantic models; ensure compatibility with static checkers (mypy, pyright).
- **Docstrings:** Public functions/classes need descriptive docstrings; keep inline comments minimal.
- **Structure:** Modify existing code instead of duplicating; follow established patterns in each module.
- **Imports:** Group by stdlib, third-party, local; avoid unused imports.
- **Python Standards:** Async for I/O, explicit exception types, avoid logging secrets.

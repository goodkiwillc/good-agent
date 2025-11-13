# good_agent Test Organization

## Recommended Structure

The test directory should follow a clear separation between unit and integration tests, with each mirroring the source code structure:

```
tests/
├── unit/               # Fast, isolated tests with no external dependencies
│   ├── agent/         # Core Agent class tests
│   ├── components/    # AgentComponent tests  
│   ├── content/       # Content parts tests
│   ├── events/        # Event system tests
│   ├── extensions/    # Built-in extension tests
│   ├── mcp/          # MCP integration tests
│   ├── messages/      # Message system tests
│   ├── mock/         # Mock implementation tests
│   ├── model/        # Language model tests
│   ├── resources/    # Resource management tests
│   ├── templating/   # Template engine tests
│   └── tools/        # Tool framework tests
│
├── integration/       # Tests requiring external services or multiple components
│   ├── agent/        # End-to-end agent tests
│   ├── components/   # Component integration tests
│   ├── extensions/   # Extension integration tests
│   ├── llm/         # LLM API integration tests
│   ├── templating/  # Template workflow tests
│   └── tools/       # Tool execution tests
│
├── fixtures/         # Shared test utilities and helpers
│   ├── cassettes/   # VCR recordings for HTTP interactions
│   └── pytest_plugins/ # Custom pytest plugins
│
└── pytest.ini       # Pytest configuration and markers
```

## Running Tests

### Run all tests
```bash
uv run pytest
```

### Run only unit tests (fast)
```bash
uv run pytest tests/unit -m unit
```

### Run only integration tests
```bash
uv run pytest tests/integration -m integration
```

### Run tests for a specific module
```bash
uv run pytest tests/unit/agent  # Just agent unit tests
uv run pytest tests/integration/llm  # Just LLM integration tests
```

### Run with specific markers
```bash
uv run pytest -m "not slow"  # Skip slow tests
uv run pytest -m "not llm"   # Skip tests requiring LLM API
uv run pytest -m vcr         # Only VCR-based tests
```

## Test Markers

Tests are marked with the following pytest markers:

- `@pytest.mark.unit` - Fast, isolated unit tests
- `@pytest.mark.integration` - Tests requiring external dependencies
- `@pytest.mark.slow` - Tests that take significant time
- `@pytest.mark.llm` - Tests requiring real LLM API calls
- `@pytest.mark.vcr` - Tests using VCR cassettes

## Test Guidelines

### Unit Tests
- Should be fast (<1 second per test)
- Use mocks for external dependencies
- Test single units of functionality
- Located in `tests/unit/`
- Mirror the source structure

### Integration Tests  
- Can be slower
- Test interactions between components
- May use real external services
- Located in `tests/integration/`
- Focus on workflows and scenarios

### Writing New Tests

1. **Determine test type**: Is it testing a single unit or multiple components?
2. **Choose location**: Place in appropriate directory mirroring source structure
3. **Add markers**: Mark with `@pytest.mark.unit` or `@pytest.mark.integration`
4. **Use fixtures**: Leverage shared fixtures from `fixtures/`
5. **Follow naming**: Use `test_*.py` for test files

## CI/CD Integration

The separated structure enables efficient CI/CD:

```yaml
# Example GitHub Actions workflow
- name: Run unit tests
  run: uv run pytest tests/unit --cov

- name: Run integration tests
  if: github.event_name == 'push' && github.ref == 'refs/heads/main'
  run: uv run pytest tests/integration
```

## Current State & Migration Plan

### Current Structure
Tests are currently organized as:
- `good_agent/unit/*` - Unit tests
- `good_agent/integration/*` - Integration tests  
- `good_agent/templating/unit/*` - Templating unit tests
- `good_agent/templating/integration/*` - Templating integration tests
- `good_agent/extensions/*` - Extension tests
- Root level test files - Mixed unit/integration tests

### Migration Strategy
To implement the recommended structure:

1. **Create new directories** matching source structure
2. **Move tests** while preserving functionality:
   - `good_agent/unit/*` → `unit/{module}/`
   - `good_agent/integration/*` → `integration/{module}/`
   - Root tests → Categorize and move appropriately
3. **Update imports** if necessary
4. **Add pytest markers** for test categorization
5. **Verify tests** still pass after reorganization

### Benefits of Migration
- Clear separation of test types
- Faster CI/CD with selective test runs
- Better test discovery and navigation
- Easier to maintain and scale
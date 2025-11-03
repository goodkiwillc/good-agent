# VCR.py Usage for LLM Testing

This document explains how to use VCR.py to record and replay LLM API responses in tests.

## Overview

VCR.py records HTTP interactions to "cassette" files (YAML format) during the first test run. Subsequent test runs replay these recorded responses instead of making real API calls.

### Benefits
- **Faster tests**: No network latency
- **Deterministic**: Same response every time
- **Cost-effective**: No API usage charges after recording
- **Offline testing**: Tests work without internet
- **Debugging**: Inspect exact API responses in cassette files

## Quick Start

### 1. Mark tests to use VCR

```python
@pytest.mark.asyncio
@pytest.mark.vcr  # Use VCR to record/replay API calls
async def test_with_llm(llm_vcr):
    async with Agent("You are helpful") as agent:
        response = await agent.call("Hello")
        assert response.content
```

### 2. Record cassettes (first run)

```bash
# Record new interactions
VCR_RECORD_MODE=new_episodes pytest path/to/test.py

# This creates cassette files in tests/cassettes/
```

### 3. Replay cassettes (subsequent runs)

```bash
# Just run normally - uses recorded cassettes
pytest path/to/test.py
```

## VCR Recording Modes

Set via `VCR_RECORD_MODE` environment variable:

- **`once`** (default): Record if cassette doesn't exist, otherwise replay
- **`new_episodes`**: Record new interactions, replay existing ones
- **`none`**: Never record, only replay (fails if cassette missing)
- **`all`**: Always record, overwrites existing cassettes

## File Structure

Cassettes are stored in:
```
tests/
  cassettes/
    llm_TestClassName_test_method_name.yaml  # LLM test cassettes
    TestClassName_test_method_name.yaml      # Regular VCR cassettes
```

## Configuration

The VCR configuration is in `tests/conftest.py`:

- **Sensitive data scrubbing**: API keys are automatically removed
- **Response compression**: Handles gzip/brotli compressed responses
- **Match criteria**: Matches requests by method, host, path (not body)
- **Ignored hosts**: localhost/127.0.0.1 are never recorded

## Manual VCR Usage

For more control, use the `vcr_cassette` fixture directly:

```python
@pytest.mark.asyncio
async def test_with_manual_vcr(vcr_cassette):
    # vcr_cassette fixture provides the cassette
    async with Agent("Assistant") as agent:
        response = await agent.call("Test")
```

## Troubleshooting

### Issue: Compressed response errors
**Solution**: The VCR config handles compression automatically. If issues persist, check the cassette file for binary data.

### Issue: Cassette not found
**Solution**: Record it first with `VCR_RECORD_MODE=new_episodes pytest test_file.py`

### Issue: API changes breaking tests
**Solution**: Re-record cassettes with `VCR_RECORD_MODE=all pytest test_file.py`

### Issue: Different responses each run
**Solution**: Check if test is using VCR. Add `@pytest.mark.vcr` decorator.

## Best Practices

1. **Commit cassettes**: Include cassette files in version control
2. **Minimal prompts**: Use simple, deterministic prompts in tests
3. **Review cassettes**: Check cassettes don't contain sensitive data
4. **Refresh periodically**: Re-record cassettes when API behavior changes
5. **Use mocks for logic**: Use MockAgent for testing business logic, VCR for integration

## Example Test File

See `test_vcr_example.py` for complete examples of:
- Using the `@pytest.mark.vcr` marker
- Manual VCR configuration
- Different recording modes
- Combining VCR with mocks

## CI/CD Usage

In CI/CD pipelines, use strict replay mode:

```yaml
# GitHub Actions example
- name: Run tests
  env:
    VCR_RECORD_MODE: none  # Fail if cassettes missing
  run: pytest tests/
```

This ensures tests never make real API calls in CI.

## Viewing Cassette Contents

Cassettes are YAML files you can inspect:

```bash
# View a cassette
cat tests/cassettes/llm_TestAgent_test_call.yaml

# Check all cassettes
ls -la tests/cassettes/

# Search cassettes for specific content
grep -r "gpt-4" tests/cassettes/
```

## Updating This Setup

To modify VCR configuration:
1. Edit `tests/conftest.py` - see `llm_vcr` and `vcr_cassette` fixtures
2. Update scrubbing functions for new sensitive headers
3. Adjust match criteria if needed

## Related Files

- `tests/conftest.py` - VCR configuration and fixtures
- `tests/cassettes/` - Recorded cassettes
- `test_vcr_example.py` - Example usage
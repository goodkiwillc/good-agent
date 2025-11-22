# LLM VCR + CI Stability

## Overview
Recorded LLM cassettes currently fail to replay in CI because LiteLLM refuses to
construct HTTP clients when `OPENAI_API_KEY` (or other provider keys) are
missing, triggering 25 `AuthenticationError` failures despite having valid VCR
fixtures. We need a way to run the default `pytest -m "not llm"` job without
real keys, keep cassette recordings deterministic, and make sure truly live LLM
tests are explicitly opt-in via the existing `llm` marker.

## Requirements
- Allow every VCR-backed LLM test to replay without any provider API keys set.
- Preserve the ability to record new cassettes with real keys when
  `VCR_RECORD_MODE` requires network access, failing fast with a helpful error
  if keys are absent.
- Ensure sensitive headers/query params stay scrubbed so recorded fixtures never
  leak secrets, and playback requests don’t attempt to include them.
- Guarantee that tests making genuine network calls are either decorated with
  `@pytest.mark.llm` (and therefore skipped by default) or are rewritten to use
  VCR/mocks.
- Fix existing suites (e.g., `tests/unit/agent/test_agent_interruption.py`) so
  they do not touch real LLMs unintentionally.

## Implementation Notes
- Add a helper in `tests/conftest.py` (or a dedicated tests/fixtures module) that
  defines a canonical `LLM_ENV_PLACEHOLDERS` mapping covering every provider we
  touch (`OPENAI_API_KEY`, `OPENROUTER_API_KEY`, `ANTHROPIC_API_KEY`,
  `GOOGLE_API_KEY`, etc.). When `llm_vcr` spins up and record mode is *not*
  `new_episodes`/`all`, temporarily set any missing env vars to deterministic
  dummy values and restore them afterwards so LiteLLM/OpenAI clients initialize
  happily.
- If record mode demands new HTTP recordings and no real key is configured,
  raise a descriptive `pytest.Skip`/`RuntimeError` before the test starts so
  contributors immediately know to export the appropriate key.
- While touching the fixture, also verify the cassette exists in playback mode;
  when missing, bubble up a clear error pointing at the cassette path.
- Double-check `scrub_sensitive_data` already nukes Authorization headers and
  add any missing header/query names encountered during re-recording (e.g.,
  `x-openai-client-user-agent`, provider-specific ratelimit headers) so that a
  dummy key during playback never creeps back into YAML.
- Update `tests/unit/agent/test_vcr_simple.py` so the “without agent” test is
  marked `@pytest.mark.llm` (it intentionally exercises a live call) and gate it
  behind the existing `RUN_AGENT_SPEC` style opt-in if needed.
- Audit interruption/signal tests that currently issue `agent.call()` without a
  mock. Replace their dependencies with `AsyncMock`/`with_mock_llm()` so they no
  longer hit LiteLLM, or add `llm_vcr` where recording makes sense.
- Re-run a focused subset of LLM/VCR suites to regenerate cassettes if the
  scrubber changes impact them; ensure updated YAML lands under
  `tests/fixtures/cassettes` with sanitized headers.

## Todo List
1. Introduce the LLM placeholder helper + context manager in `tests/conftest.py`
   and wire it into `llm_vcr`, including record-mode validation and cassette
   existence checks.
2. Extend the scrubber filters if new sensitive headers emerge during testing.
3. Mark or refactor tests that truly require live LLMs:
   - `tests/unit/agent/test_vcr_simple.py::test_simple_vcr_without_agent` → `llm`.
   - Patch `test_agent_interruption.py` (and any similar modules) to rely on
     mocks so they stay in the default suite.
4. Re-run the affected suites, regenerate cassettes when necessary, and commit
   sanitized fixtures.

## Testing Strategy
- `uv run pytest tests/unit/agent/test_agent_message_store_integration.py`
  (exercise llm_vcr playback)
- `uv run pytest tests/unit/agent/test_agent_interruption.py`
  (ensure mocked paths don’t poke real LLMs)
- `uv run pytest tests/unit/agent/test_vcr_simple.py -k "not llm"`
  (replay-only coverage)
- `uv run pytest tests/integration/agent/test_editable_yaml_vcr.py`
- `uv run pytest tests/docs/test_doc_examples.py`
- Final gate: `uv run pytest -m "not slow and not llm"`

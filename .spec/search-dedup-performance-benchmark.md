## Overview
`tests/integration/search/test_search_performance.py::TestPerformance::test_deduplication_performance` currently compares single-shot wall-clock durations of deduped vs non-deduped searches. Under concurrent suite load it often exceeds the strict 1.5× threshold even though functionality is correct. We need a deterministic micro-benchmark harness that averages multiple invocations so scheduler jitter does not cause flakes while still flagging regressions where deduplication becomes materially slower.

## Requirements
- Maintain the existing behavioral assertions (deduped result count strictly less than non-deduped).
- Replace the single timing comparison with a multi-iteration benchmark:
  - Warm up both agents once before measurement.
  - Alternate dedup/non-dedup invocations to keep cache effects even.
  - Run at least 5 measured iterations per variant.
  - Compare a robust statistic (median or trimmed mean) instead of raw single run.
  - Keep the acceptable overhead generous enough (e.g., <= 1.75×) yet still meaningful.
- Fail fast with clear diagnostics showing the collected timings on assertion failure for debugging.

## Implementation Notes
- Introduce a small helper inside the test (or module-level) to `measure_runs(agent, iterations)` returning a list of elapsed seconds while invoking the tool.
- Use `statistics.median` to summarize elapsed times; median is resilient to outliers but cheap to compute without additional deps.
- After warm-up, collect alternating timings, e.g., `[dedup_i, no_dedup_i]` loops, storing them separately to maintain ordering.
- Consider inserting a tiny `asyncio.sleep(0)` between runs to yield control without adding real delay.
- Keep the multiplier threshold configurable via a constant defined near the test for easy tuning.

## Todo List
1. Add helper(s) for repeated timing measurement with median aggregation and debug output.
2. Update `test_deduplication_performance` to use the helper, including warm-up and alternating execution order.
3. Adjust the performance assertion to compare medians with a looser multiplier (≤ 1.75×) and emit timings when it fails.
4. Ensure existing dedup/no-dedup result-count assertion still passes.
5. Update/extend any fixtures or utilities if necessary to support the helper.

## Testing Strategy
- Run the updated test module via `uv run pytest tests/integration/search/test_search_performance.py -k deduplication` to confirm determinism locally.
- Execute the full suite (or at least all integration tests touching search) to ensure no new flakes and acceptable runtime impact.

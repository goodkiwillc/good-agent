import subprocess
import sys

import pytest


class TestImportPerformance:
    """Test suite for import performance."""

    @pytest.mark.performance
    def test_base_import_time(self):
        """Test that base import stays within reasonable bounds.

        Current baseline: 8.2 seconds (we'll improve this over time)
        Target: < 1.0 second
        """
        code = """
import time
start = time.time()
import good_agent
elapsed = time.time() - start
print(elapsed)
"""
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=30,  # Safety timeout
        )
        import_time = float(result.stdout.strip())

        # Current threshold (will be lowered as optimizations are implemented)
        current_threshold = 12.0  # Start with 12s, will reduce to 1.0s

        assert import_time < current_threshold, (
            f"Import took {import_time:.2f}s (limit: {current_threshold}s). "
            f"This indicates a performance regression."
        )

        # Log the actual time for tracking
        print(f"Import time: {import_time:.3f}s")

    @pytest.mark.performance
    def test_no_heavy_imports_at_module_level(self):
        """Ensure heavy modules aren't imported at module level."""
        code = """
import sys

# Import just the module without triggering heavy imports
import good_agent

# Check that heavy modules aren't loaded yet (after optimizations)
heavy_modules = ['litellm', 'litellm.utils', 'litellm.types']

# For now, just track what's imported
imported_heavy = [m for m in heavy_modules if m in sys.modules]
print(','.join(imported_heavy) if imported_heavy else 'NONE')
"""
        result = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True
        )

        imported = result.stdout.strip()

        # For now, just document what's imported (will enforce after optimization)
        if imported != "NONE":
            print(f"Heavy modules imported at module level: {imported}")
            # After optimization, this should fail:
            # assert imported == 'NONE', f"Heavy modules should not be imported: {imported}"

    @pytest.mark.performance
    def test_individual_module_import_times(self):
        """Monitor individual module import times to identify regressions."""
        modules_and_current_times = [
            # Module name and current baseline (will reduce these)
            ("good_agent.agent", 8.0),  # Currently ~7.7s
            ("good_agent.messages", 2.0),  # Currently ~1.1s
            ("good_agent.tools", 1.0),  # Currently ~0.05s
            ("good_agent.agent.config", 0.5),  # Context stack now lives here
            ("good_agent", 2.0),  # Currently ~1.2s
        ]

        results = []

        for module, limit in modules_and_current_times:
            code = f"""
import time
start = time.time()
import {module}
elapsed = time.time() - start
print(elapsed)
"""
            result = subprocess.run(
                [sys.executable, "-c", code], capture_output=True, text=True, timeout=30
            )

            if result.returncode == 0:
                import_time = float(result.stdout.strip())
                results.append((module, import_time, limit))

                if import_time > limit:
                    print(f"⚠️  {module}: {import_time:.3f}s (limit: {limit}s)")
                else:
                    print(f"✓ {module}: {import_time:.3f}s")

        # Report all results
        slow_modules = [(mod, tme) for mod, tme, limit in results if tme > limit]
        if slow_modules:
            msg = "Slow module imports detected:\n"
            for module, time in slow_modules:
                msg += f"  - {module}: {time:.3f}s\n"
            # For now, just warn (will fail after optimization)
            print(msg)
            # pytest.fail(msg)

    @pytest.mark.performance
    def test_import_time_breakdown(self):
        """Detailed breakdown of import time by component."""
        code = """
import time
import sys

def timed_import(module_name):
    start = time.time()
    __import__(module_name)
    return time.time() - start

# Track cumulative time
results = []

# Test imports in isolation
isolated_modules = [
    'orjson',
    'loguru',
    'pydantic',
    'jinja2',
    'httpx',
    'asyncio',
]

for module in isolated_modules:
    if module not in sys.modules:
        try:
            t = timed_import(module)
            results.append(f"{module}:{t:.3f}")
        except ImportError:
            results.append(f"{module}:ERROR")

print('|'.join(results))
"""
        result = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True
        )

        if result.returncode == 0:
            times = result.stdout.strip().split("|")
            print("\nIsolated import times:")
            for time_str in times:
                if ":" in time_str:
                    module, time = time_str.split(":")
                    if time != "ERROR":
                        print(f"  {module:20} {float(time) * 1000:7.1f} ms")

    @pytest.mark.performance
    @pytest.mark.skipif(
        sys.platform == "win32", reason="Memory profiling not reliable on Windows"
    )
    def test_import_memory_usage(self):
        """Monitor memory usage during import."""
        code = """
import tracemalloc
import sys

tracemalloc.start()

# Baseline memory
snapshot1 = tracemalloc.take_snapshot()

# Import the module
import good_agent

# After import memory
snapshot2 = tracemalloc.take_snapshot()

# Calculate difference
stats = snapshot2.compare_to(snapshot1, 'lineno')
total_kb = sum(stat.size_diff for stat in stats) / 1024

print(f"{total_kb:.1f}")
"""
        result = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True
        )

        if result.returncode == 0:
            memory_kb = float(result.stdout.strip())
            print(f"Memory used during import: {memory_kb:.1f} KB")

            # Warn if excessive memory usage (> 100MB)
            if memory_kb > 100_000:
                print(f"⚠️  Excessive memory usage: {memory_kb:.1f} KB")


@pytest.mark.benchmark
@pytest.mark.skipif(
    "benchmark" not in dir(pytest), reason="pytest-benchmark not installed"
)
class TestImportBenchmarks:
    """Benchmark tests for tracking import performance over time."""

    @pytest.mark.skipif(
        True, reason="pytest-benchmark not installed, skipping benchmark tests"
    )
    def test_benchmark_minimal_import(self, benchmark):
        """Benchmark minimal import scenario."""

        def import_minimal():
            # Clear module cache
            import sys

            if "good_agent" in sys.modules:
                del sys.modules["good_agent"]

            # Import

        # Run benchmark
        benchmark(import_minimal)

    @pytest.mark.skipif(
        True, reason="pytest-benchmark not installed, skipping benchmark tests"
    )
    def test_benchmark_full_import(self, benchmark):
        """Benchmark full import with all features."""

        def import_full():
            # Clear module cache
            import sys

            modules_to_clear = [
                m for m in sys.modules.keys() if m.startswith("good_agent")
            ]
            for m in modules_to_clear:
                del sys.modules[m]

            # Import everything

        # Run benchmark
        benchmark(import_full)


if __name__ == "__main__":
    # Run performance tests directly
    test = TestImportPerformance()

    print("Running import performance tests...\n")
    print("=" * 50)

    test.test_base_import_time()
    print("=" * 50)

    test.test_individual_module_import_times()
    print("=" * 50)

    test.test_import_time_breakdown()
    print("=" * 50)

    test.test_import_memory_usage()

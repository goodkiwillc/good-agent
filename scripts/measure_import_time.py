#!/usr/bin/env python3
"""
Measure LiteLLM import time.
Run this script in any directory to measure the import performance.
"""

import subprocess
import sys
from statistics import mean, stdev


def test_import_time(runs=10):
    """Test import time by running in subprocess to ensure clean imports."""
    print(f"Running {runs} import tests...")
    print()

    times = []

    for i in range(runs):
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                """
import time
start = time.time()
import litellm
end = time.time()
print(end - start)
""",
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            print(f"❌ Error in run {i + 1}:")
            print(result.stderr)
            sys.exit(1)

        import_time = float(result.stdout.strip())
        times.append(import_time)
        print(f"  Run {i + 1:2d}: {import_time:.3f}s")

    avg = mean(times)
    std = stdev(times) if len(times) > 1 else 0
    min_time = min(times)
    max_time = max(times)

    print()
    print("=" * 50)
    print("Results:")
    print("=" * 50)
    print(f"  Average:  {avg:.3f}s")
    print(f"  Std Dev:  ±{std:.3f}s")
    print(f"  Min:      {min_time:.3f}s")
    print(f"  Max:      {max_time:.3f}s")
    print("=" * 50)

    return avg


if __name__ == "__main__":
    import os

    print("=" * 50)
    print("LiteLLM Import Speed Test")
    print("=" * 50)
    print(f"Working directory: {os.getcwd()}")
    print()

    avg = test_import_time(runs=10)

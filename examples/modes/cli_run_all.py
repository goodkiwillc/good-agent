#!/usr/bin/env python
"""Run all CLI mode example scripts sequentially.

Usage:
    python examples/modes/cli_run_all.py           # Rich output (default)
    python examples/modes/cli_run_all.py --plain   # Plain text output
    python examples/modes/cli_run_all.py --json    # JSON output
"""

import argparse
import subprocess
import sys
from pathlib import Path

SCRIPTS = [
    "cli_interactive_modes.py",
    "cli_workflow_modes.py",
    "cli_generator_modes.py",
    "cli_stacked_modes.py",
    "cli_isolation_modes.py",
    "cli_standalone_modes.py",
]


def main():
    parser = argparse.ArgumentParser(description="Run all CLI mode example scripts")
    parser.add_argument(
        "--plain",
        action="store_true",
        help="Plain text output without styling",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Machine-readable JSON output",
    )
    args = parser.parse_args()

    # Build extra args to pass to each script
    extra_args = []
    if args.json:
        extra_args.append("--json")
    elif args.plain:
        extra_args.append("--plain")

    script_dir = Path(__file__).parent
    failed = []

    for i, script in enumerate(SCRIPTS, 1):
        script_path = script_dir / script
        print(f"\n{'=' * 60}")
        print(f"[{i}/{len(SCRIPTS)}] Running: {script}")
        print("=" * 60)

        result = subprocess.run(
            [sys.executable, str(script_path), *extra_args],
            cwd=script_dir,
        )

        if result.returncode != 0:
            failed.append(script)
            print(f"\n[FAILED] {script} exited with code {result.returncode}")
        else:
            print(f"\n[OK] {script} completed")

    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print("=" * 60)
    print(
        f"Total: {len(SCRIPTS)}, Passed: {len(SCRIPTS) - len(failed)}, Failed: {len(failed)}"
    )

    if failed:
        print(f"Failed scripts: {', '.join(failed)}")
        sys.exit(1)


if __name__ == "__main__":
    main()

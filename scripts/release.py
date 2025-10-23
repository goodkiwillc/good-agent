#!/usr/bin/env python

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"


def run(command: str, *, check: bool = True, capture_output: bool = False) -> subprocess.CompletedProcess[str]:
    print(f"Running: {command}")
    result = subprocess.run(
        command,
        shell=True,
        cwd=ROOT,
        text=True,
        capture_output=capture_output,
    )
    if check and result.returncode != 0:
        if capture_output and result.stderr:
            print(result.stderr, file=sys.stderr)
        sys.exit(result.returncode)
    return result


def get_current_version() -> str:
    result = run("git describe --tags --abbrev=0", check=False, capture_output=True)
    if result.returncode != 0:
        return "0.1.0"
    tag = result.stdout.strip()
    return tag.lstrip("v") or "0.1.0"


def get_next_version(current: str, bump: str) -> str:
    parts = [int(p) for p in current.split(".")[:3]]
    while len(parts) < 3:
        parts.append(0)
    major, minor, patch = parts
    if bump == "major":
        major += 1
        minor = 0
        patch = 0
    elif bump == "minor":
        minor += 1
        patch = 0
    else:
        patch += 1
    return f"{major}.{minor}.{patch}"


def update_pyproject_version(version: str) -> None:
    content = PYPROJECT.read_text()
    new_content = re.sub(r'version\s*=\s*"[^"]+"', f'version = "{version}"', content, count=1)
    if new_content == content:
        print("version key not found in pyproject.toml", file=sys.stderr)
        sys.exit(1)
    PYPROJECT.write_text(new_content)


def ensure_clean_worktree(dry_run: bool) -> None:
    status = run("git status --porcelain", capture_output=True)
    if status.stdout.strip() and not dry_run:
        print("Working tree is not clean", file=sys.stderr)
        sys.exit(1)


def build_package() -> None:
    dist_dir = ROOT / "dist"
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    run("uv run python -m build --wheel --sdist")
    if dist_dir.exists():
        shutil.rmtree(dist_dir)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a tagged release")
    parser.add_argument("bump", choices=["patch", "minor", "major"], help="Version bump type")
    parser.add_argument("--dry-run", action="store_true", help="Show actions without executing")
    parser.add_argument("--skip-tests", action="store_true", help="Skip pytest before release")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")
    args = parser.parse_args()

    if not PYPROJECT.exists():
        print("pyproject.toml not found", file=sys.stderr)
        sys.exit(1)

    ensure_clean_worktree(args.dry_run)

    current_version = get_current_version()
    next_version = get_next_version(current_version, args.bump)

    print(f"Current version: {current_version}")
    print(f"Next version: {next_version}")

    if args.dry_run:
        print("Dry run complete")
        return

    if not args.yes:
        confirm = input(f"Create release v{next_version}? [y/N]: ").strip().lower()
        if confirm != "y":
            print("Cancelled")
            return

    update_pyproject_version(next_version)

    run("uv sync")
    if not args.skip_tests:
        run("uv pip install pytest", check=False)
        run("uv run pytest -q")

    build_package()

    run("git add pyproject.toml")
    run(f'git commit -m "Prepare release v{next_version}"', check=False)

    run(f'git tag -a v{next_version} -m "Release v{next_version}"')
    run("git push origin HEAD")
    run(f"git push origin v{next_version}")

    print(f"Release v{next_version} created")


if __name__ == "__main__":
    main()

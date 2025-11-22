#!/usr/bin/env python3
"""Automated release helper for good-agent."""

from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
import sys
from pathlib import Path

import tomllib


ROOT = Path(__file__).resolve().parents[1]
PYPROJECT_PATH = ROOT / "pyproject.toml"
INIT_PATH = ROOT / "src" / "good_agent" / "__init__.py"
CHANGELOG_PATH = ROOT / "CHANGELOG.md"


def run_command(
    command: str, *, check: bool = True, capture_output: bool = False
) -> subprocess.CompletedProcess[str]:
    """Run a shell command relative to the repo root."""

    print(f"$ {command}")
    result = subprocess.run(
        command,
        shell=True,
        cwd=ROOT,
        text=True,
        capture_output=capture_output,
    )
    if check and result.returncode != 0:
        if capture_output:
            if result.stdout:
                print(result.stdout)
            if result.stderr:
                print(result.stderr, file=sys.stderr)
        raise SystemExit(result.returncode)
    return result


def ensure_repo_root() -> None:
    if not PYPROJECT_PATH.exists():
        raise SystemExit("Run this script from the repository root.")


def ensure_clean_worktree() -> None:
    status = run_command("git status --porcelain", capture_output=True)
    if status.stdout.strip():
        raise SystemExit(
            "Working tree is dirty. Commit or stash changes before releasing."
        )


def read_pyproject_version() -> str:
    data = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))
    try:
        return data["project"]["version"]
    except KeyError as exc:
        raise SystemExit("Unable to find [project].version in pyproject.toml") from exc


def bump_version(current: str, bump_type: str) -> str:
    major, minor, patch = (int(part) for part in current.split("."))
    if bump_type == "major":
        major += 1
        minor = 0
        patch = 0
    elif bump_type == "minor":
        minor += 1
        patch = 0
    else:
        patch += 1
    return f"{major}.{minor}.{patch}"


def replace_line(path: Path, pattern: re.Pattern[str], replacement: str) -> None:
    content = path.read_text()
    new_content, count = pattern.subn(replacement, content, count=1)
    if count == 0:
        raise SystemExit(f"Failed to update version in {path}")
    path.write_text(new_content)


def update_versions(new_version: str) -> None:
    pyproject_pattern = re.compile(r'(?m)^(version\s*=\s*")([^\"]+)(")')
    init_pattern = re.compile(r'(?m)^(__version__\s*=\s*")([^\"]+)(")')
    replace_line(PYPROJECT_PATH, pyproject_pattern, rf"\g<1>{new_version}\g<3>")
    replace_line(INIT_PATH, init_pattern, rf"\g<1>{new_version}\g<3>")


def update_changelog(version: str) -> None:
    if not CHANGELOG_PATH.exists():
        return
    today = dt.date.today().strftime("%Y-%m-%d")
    insertion = f"\n\n## [{version}] - {today}\n\n- TODO: Document release notes.\n"
    content = CHANGELOG_PATH.read_text().rstrip()
    marker = "## [Unreleased]"
    if marker in content:
        parts = content.split(marker, 1)
        content = f"{parts[0]}{marker}{insertion}{parts[1]}"
    else:
        content = f"{content}{insertion}"
    CHANGELOG_PATH.write_text(content + "\n")


def run_validations() -> None:
    commands = [
        "uv sync --group dev",
        "uv run ruff check src scripts tests",
        "uv run python -m compileall src",
        "uv run mkdocs build --clean --site-dir site",
    ]
    for cmd in commands:
        run_command(cmd)


def create_tag(version: str) -> None:
    run_command(f'git tag -a v{version} -m "Release v{version}"')


def push_release(version: str) -> None:
    run_command("git push origin main")
    run_command(f"git push origin v{version}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a new good-agent release")
    parser.add_argument(
        "bump_type", choices=["patch", "minor", "major"], help="Version segment to bump"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show actions without mutating anything"
    )
    parser.add_argument(
        "--skip-tests", action="store_true", help="Skip validation commands"
    )
    parser.add_argument(
        "--yes", "-y", action="store_true", help="Skip confirmation prompt"
    )
    return parser.parse_args()


def main() -> None:
    ensure_repo_root()
    args = parse_args()
    ensure_clean_worktree()

    current_version = read_pyproject_version()
    next_version = bump_version(current_version, args.bump_type)

    print("Current version:", current_version)
    print("Next version:", next_version)

    if args.dry_run:
        print("Dry run complete. No changes applied.")
        return

    if not args.yes:
        confirm = input(f"Create release v{next_version}? [y/N]: ")
        if confirm.lower() != "y":
            print("Release cancelled.")
            return

    if not args.skip_tests:
        run_validations()
    else:
        print("Skipping validation commands per --skip-tests")

    update_versions(next_version)
    update_changelog(next_version)

    files_to_add = [PYPROJECT_PATH, INIT_PATH]
    if CHANGELOG_PATH.exists():
        files_to_add.append(CHANGELOG_PATH)
    paths = " ".join(str(path.relative_to(ROOT)) for path in files_to_add)
    run_command(f"git add {paths}")
    run_command(f'git commit -m "Prepare release v{next_version}"', check=False)

    create_tag(next_version)
    push_release(next_version)

    release_url = (
        f"https://github.com/goodkiwillc/good-agent/releases/new?tag=v{next_version}"
    )
    print("\nRelease tag created. Create a GitHub release at:")
    print(release_url)


if __name__ == "__main__":
    main()

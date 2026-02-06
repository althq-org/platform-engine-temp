"""Runnable scripts for common dev tasks. Use: uv run <script-name> (see README)."""

import subprocess
import sys


def _run(args: list[str]) -> None:
    """Run a command; exit with its code."""
    sys.exit(subprocess.run(args).returncode)


def lint() -> None:
    """Run ruff check on devops and tests."""
    _run([sys.executable, "-m", "ruff", "check", "devops", "tests"])


def lint_fix() -> None:
    """Run ruff check --fix on devops and tests."""
    _run([sys.executable, "-m", "ruff", "check", "--fix", "devops", "tests"])


def format() -> None:
    """Run ruff format on devops and tests."""
    _run([sys.executable, "-m", "ruff", "format", "devops", "tests"])


def type_check() -> None:
    """Run pyright on devops."""
    _run([sys.executable, "-m", "pyright", "devops"])


def test() -> None:
    """Run pytest."""
    _run([sys.executable, "-m", "pytest", "tests/", "-v"])


def test_cov() -> None:
    """Run pytest with coverage report."""
    _run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/",
            "--cov=devops",
            "--cov-report=term-missing",
            "-v",
        ]
    )

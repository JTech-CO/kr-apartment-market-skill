#!/usr/bin/env python3
"""Convenience entry point for package validation."""

from __future__ import annotations

import subprocess
import sys


def main() -> int:
    commands = [
        [sys.executable, "scripts/validate_package.py", ".", "--write-manifest"],
        [sys.executable, "-m", "pytest", "tests/runtime", "-q"],
    ]
    for command in commands:
        completed = subprocess.run(command, check=False)
        if completed.returncode:
            return completed.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

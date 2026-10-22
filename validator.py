#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main() -> int:
    print("=== GREMLIN assurance validator ===")
    results: list[tuple[str, bool, str]] = []

    def record(name: str, ok: bool, detail: str = "") -> None:
        results.append((name, ok, detail))
        suffix = f" -- {detail}" if detail else ""
        print(f"[{'PASS' if ok else 'FAIL'}] {name}{suffix}")

    record("python >= 3.9", sys.version_info >= (3, 9), sys.version.split()[0])
    record(".env present", (ROOT / ".env").exists(), "run: cp .env.example .env")

    gen_files = ("GremlinCLexer.py", "GremlinCParser.py", "GremlinCVisitor.py")
    gen_ok = all((ROOT / "src" / "gen" / f).exists() for f in gen_files)
    record("ANTLR parser generated (src/gen)", gen_ok, "run: bash setup.sh (needs Java)")

    env = dict(os.environ)

    def run_cmd(cmd: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
        return subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True,
                              text=True, timeout=timeout)

    try:
        r = run_cmd([sys.executable, "-m", "mypy", "--strict", "src", "config.py", "driver.py"], 300)
        record("mypy strict type check", r.returncode == 0,
               "no type errors" if r.returncode == 0 else "see mypy output below")
        if r.returncode != 0:
            print(r.stdout)
            print(r.stderr)
    except FileNotFoundError:
        record("mypy strict type check", False, "mypy missing: pip install -r requirements.txt")

    try:
        r = run_cmd([sys.executable, "-m", "pytest", "tests", "-q"], 600)
        last = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
        record("pytest suite", r.returncode == 0, last if r.returncode == 0 else "see pytest output below")
        if r.returncode != 0:
            print(r.stdout)
            print(r.stderr)
    except FileNotFoundError:
        record("pytest suite", False, "pytest missing: pip install -r requirements.txt")

    failed = [name for name, ok, _ in results if not ok]
    if failed:
        print(f"\n{len(failed)} check(s) failed: {', '.join(failed)}")
        return 1
    print("\nALL CHECKS PASSED - safe to demo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
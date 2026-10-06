import os
import shutil
import sys
import tempfile
import tomllib
from pathlib import Path

from cpp_bug_bench.sandbox import run

# Run with problem ids (check_proof.py p0001 p0002), or with none to check every problem.
ids = sys.argv[1:] or sorted(p.name for p in Path("problems").iterdir() if p.is_dir())

for pid in ids:
    problem = Path("problems") / pid
    meta = tomllib.loads((problem / "problem.toml").read_text())
    if not meta["has_bug"]:
        print(f"{pid}: no bug, nothing to prove")
        continue

    for version in ["buggy", "fixed"]:
        with tempfile.TemporaryDirectory() as tmp:
            os.chmod(tmp, 0o755)
            shutil.copy(problem / version / "code.hpp", tmp)
            shutil.copy(problem / "proof" / "test.cpp", tmp)
            r = run(Path(tmp), "test.cpp", meta["sanitizer"])

        summary = [line for line in r.output.splitlines() if "SUMMARY" in line]
        print(f"{pid} {version}: exit {r.exit_code}  {summary or 'no sanitizer report'}")

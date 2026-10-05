import os
import shutil
import sys
import tempfile
import tomllib
from pathlib import Path

from cpp_bug_bench.sandbox import run

problem = Path("problems") / sys.argv[1]
sanitizer = tomllib.loads((problem / "problem.toml").read_text())["sanitizer"]

for version in ["buggy", "fixed"]:
    with tempfile.TemporaryDirectory() as tmp:
        os.chmod(tmp, 0o755)
        shutil.copy(problem / version / "code.hpp", tmp)
        shutil.copy(problem / "proof" / "test.cpp", tmp)
        r = run(Path(tmp), "test.cpp", sanitizer)

    summary = [line for line in r.output.splitlines() if "SUMMARY" in line]
    print(f"{version}: exit {r.exit_code}  {summary or 'no sanitizer report'}")

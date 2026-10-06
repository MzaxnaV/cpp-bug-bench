import os
import shutil
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path

from cpp_bug_bench.answer import ParsedAnswer
from cpp_bug_bench.sandbox import SAN_ENV, RunResult, run

SANITIZER_EXIT = 77
MARKERS = {
    "address": ["ERROR: AddressSanitizer"],
    "undefined": ["runtime error:"],
    "thread": ["WARNING: ThreadSanitizer"],
    "address,undefined": ["ERROR: AddressSanitizer", "runtime error:"],
}


@dataclass(frozen=True)
class Problem:
    id: str
    dir: Path
    sanitizer: str
    has_bug: bool


@dataclass(frozen=True)
class Grade:
    outcome: str  # found | missed | test_invalid | infra_error
    reason: str
    buggy: RunResult | None  # None if it never ran
    fixed: RunResult | None


def load_problem(dir: Path) -> Problem:
    meta = tomllib.loads((dir / "problem.toml").read_text())
    return Problem(
        id=meta["id"], dir=dir, sanitizer=meta["sanitizer"], has_bug=meta["has_bug"]
    )


def fired(r: RunResult, sanitizer: str) -> bool:
    if not r.compiled or r.exit_code != SANITIZER_EXIT:
        # either it didn't compile, or exited without the sanitizer's exit code
        return False
    return any(m in r.output for m in MARKERS[sanitizer])


def _run_version(problem: Problem, version: str, test: str) -> RunResult:
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        os.chmod(work, 0o755)  # allow Docker's user to read this folder
        for f in (problem.dir / version).iterdir():
            shutil.copy(f, work)
        (work / "test.cpp").write_text(test)
        os.chmod(work / "test.cpp", 0o644)
        return run(work, "test.cpp", problem.sanitizer, env=SAN_ENV)


def grade(problem: Problem, answer: ParsedAnswer) -> Grade:
    if not problem.has_bug:
        raise NotImplementedError("problems without a bug are not graded yet")

    if answer.error:
        return Grade("test_invalid", answer.error, None, None)
    if answer.verdict == "none":
        return Grade("missed", "verdict none", None, None)

    buggy = _run_version(problem, "buggy", answer.test)
    if buggy.sandbox_failed:
        return Grade("infra_error", "sandbox failed on buggy", buggy, None)
    if not buggy.compiled:
        return Grade("test_invalid", "does not compile", buggy, None)
    if not fired(buggy, problem.sanitizer):
        # no need to run fixed: nothing was proven
        return Grade("missed", "did not fire on buggy", buggy, None)

    fixed = _run_version(problem, "fixed", answer.test)
    if fixed.sandbox_failed:
        return Grade("infra_error", "sandbox failed on fixed", buggy, fixed)
    if not fixed.compiled:
        return Grade("test_invalid", "does not compile on fixed", buggy, fixed)
    if fixed.timed_out or fixed.out_of_memory:
        # can't tell whether fixed would have stayed quiet
        return Grade("test_invalid", "fixed timed out or ran out of memory", buggy, fixed)
    if fired(fixed, problem.sanitizer):
        return Grade("test_invalid", "fires on both", buggy, fixed)
    return Grade("found", "fires on buggy only", buggy, fixed)

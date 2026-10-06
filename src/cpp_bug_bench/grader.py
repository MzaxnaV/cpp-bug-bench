import math
import os
import shutil
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path

from cpp_bug_bench.answer import ParsedAnswer
from cpp_bug_bench.sandbox import SAN_ENV, BuildResult, RunResult, build, execute

SANITIZER_EXIT = 77
MARKERS = {
    "address": ["ERROR: AddressSanitizer"],
    "undefined": ["runtime error:"],
    "thread": ["WARNING: ThreadSanitizer"],
    "address,undefined": ["ERROR: AddressSanitizer", "runtime error:"],
}
# every answer is tried under each build, starting with ASan+UBSan (same result every run)
BUILDS = ["address,undefined", "thread"]
# TSan can catch a race on one run and miss it on the next, so it gets repeat runs
THREAD_RUNS = 10
ALPHA = 0.01  # Fisher's test. With 10 runs, buggy must fire at least 6 times and fixed never.


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
    sanitizer: str | None  # the build that decided the outcome, or None if nothing ran
    buggy: RunResult | None  # one run to show (a firing one if any), or None
    fixed: RunResult | None
    buggy_fired: int = 0  # how many runs fired, out of `runs`
    fixed_fired: int = 0
    runs: int = 0  # runs per version under the deciding build


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


def fisher_p(buggy_fired: int, fixed_fired: int, runs: int) -> float:
    # One-sided Fisher's exact test. It gives the chance that buggy gets at least this many
    # of the fires if both versions really fire equally often.
    total = buggy_fired + fixed_fired
    hits = sum(
        math.comb(runs, x) * math.comb(runs, total - x)
        for x in range(buggy_fired, min(runs, total) + 1)
    )
    return hits / math.comb(2 * runs, total)


def decide_counts(buggy_fired: int, fixed_fired: int, runs: int) -> tuple[str, str]:
    if buggy_fired == 0:
        return "missed", "did not fire on buggy"
    if fixed_fired > 0:
        return "test_invalid", "fires on both"
    if runs == 1:
        # this build gives the same result every run, so one run is enough
        return "found", "fires on buggy only"
    if fisher_p(buggy_fired, fixed_fired, runs) < ALPHA:
        return "found", "fires on buggy only"
    return "test_invalid", "too flaky"


def _build_version(
    problem: Problem, version: str, test: str, sanitizer: str, out_dir: Path
) -> BuildResult:
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        os.chmod(work, 0o755)  # allow Docker's user to read this folder
        for f in (problem.dir / version).iterdir():
            shutil.copy(f, work)
        (work / "test.cpp").write_text(test)
        os.chmod(work / "test.cpp", 0o644)
        return build(work, "test.cpp", sanitizer, out_dir)


def _not_built(b: BuildResult) -> RunResult:
    # a failed build as a RunResult, so Grade keeps the compiler output for the logs
    return RunResult(
        compiled=False,
        exit_code=None,
        output=b.output,
        timed_out=False,
        out_of_memory=False,
        seconds=b.seconds,
        sandbox_failed=b.sandbox_failed,
    )


def _execute(out_dir: Path, runs: int) -> list[RunResult]:
    results = []
    for _ in range(runs):
        r = execute(out_dir, env=SAN_ENV)
        results.append(r)
        if r.sandbox_failed:
            break
    return results


def grade(problem: Problem, answer: ParsedAnswer) -> Grade:
    if not problem.has_bug:
        raise NotImplementedError("problems without a bug are not graded yet")

    if answer.error:
        return Grade("test_invalid", answer.error, None, None, None)
    if answer.verdict == "none":
        return Grade("missed", "verdict none", None, None, None)

    invalid = None  # a build that fired on buggy but couldn't separate it from fixed
    last = None
    for sanitizer in BUILDS:
        runs = THREAD_RUNS if sanitizer == "thread" else 1
        with (
            tempfile.TemporaryDirectory() as buggy_out,
            tempfile.TemporaryDirectory() as fixed_out,
        ):
            b = _build_version(problem, "buggy", answer.test, sanitizer, Path(buggy_out))
            if b.sandbox_failed or not b.compiled:
                outcome = "infra_error" if b.sandbox_failed else "test_invalid"
                reason = "sandbox failed on buggy" if b.sandbox_failed else "does not compile"
                return Grade(outcome, reason, sanitizer, _not_built(b), None)

            buggy_runs = _execute(Path(buggy_out), runs)
            last = buggy_runs[-1]
            if last.sandbox_failed:
                return Grade("infra_error", "sandbox failed on buggy", sanitizer, last, None)
            buggy_fires = [r for r in buggy_runs if fired(r, sanitizer)]
            if not buggy_fires:
                continue
            shown = buggy_fires[0]

            f = _build_version(problem, "fixed", answer.test, sanitizer, Path(fixed_out))
            if f.sandbox_failed:
                reason = "sandbox failed on fixed"
                return Grade("infra_error", reason, sanitizer, shown, _not_built(f))
            if not f.compiled:
                reason = "does not compile on fixed"
                return Grade("test_invalid", reason, sanitizer, shown, _not_built(f))

            fixed_runs = _execute(Path(fixed_out), runs)
            if fixed_runs[-1].sandbox_failed:
                reason = "sandbox failed on fixed"
                return Grade("infra_error", reason, sanitizer, shown, fixed_runs[-1])
            fixed_fires = [r for r in fixed_runs if fired(r, sanitizer)]
            counts = (len(buggy_fires), len(fixed_fires), runs)

            stuck = [r for r in fixed_runs if r.timed_out or r.out_of_memory]
            if stuck:
                # can't tell whether fixed would have stayed quiet
                reason = "fixed timed out or ran out of memory"
                invalid = Grade("test_invalid", reason, sanitizer, shown, stuck[0], *counts)
                continue

            outcome, reason = decide_counts(*counts)
            fixed_shown = fixed_fires[0] if fixed_fires else fixed_runs[0]
            g = Grade(outcome, reason, sanitizer, shown, fixed_shown, *counts)
            if outcome == "found":
                return g
            invalid = g

    if invalid:
        return invalid
    # nothing fired on buggy, so fixed never ran. Keep the last buggy run for the logs.
    return Grade("missed", "did not fire on buggy", BUILDS[-1], last, None, 0, 0, THREAD_RUNS)

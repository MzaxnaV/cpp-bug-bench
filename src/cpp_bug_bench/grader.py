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
ALPHA = 0.01  # Fisher's test. With 10 runs, buggy must report at least 6 times and fixed never.


@dataclass(frozen=True)
class Problem:
    id: str
    dir: Path
    sanitizer: str
    has_bug: bool


@dataclass(frozen=True)
class Proof:
    # what running the test showed. One of proven, no_report, reports_on_fixed_too,
    # unreliable, fixed_did_not_finish, does_not_compile, reports_on_correct_code,
    # docker_failed or no_test.
    status: str
    sanitizer: str | None  # the build that decided, or None if nothing ran
    buggy: RunResult | None  # one run to show (a reporting one if any), or None
    fixed: RunResult | None
    buggy_reports: int = 0  # how many runs reported, out of `runs`
    fixed_reports: int = 0
    runs: int = 0


NO_TEST = Proof("no_test", None, None, None)


@dataclass(frozen=True)
class Grade:
    claim: str | None  # bug, none, or None if the answer was broken
    has_bug: bool
    proof: Proof
    outcome: str  # found, missed, bad_test, not_graded, correct_none, false_alarm, needs_review


def load_problem(dir: Path) -> Problem:
    meta = tomllib.loads((dir / "problem.toml").read_text())
    return Problem(
        id=meta["id"], dir=dir, sanitizer=meta["sanitizer"], has_bug=meta["has_bug"]
    )


def reported(r: RunResult, sanitizer: str) -> bool:
    if not r.compiled or r.exit_code != SANITIZER_EXIT:
        # either it didn't compile, or exited without the sanitizer's exit code
        return False
    return any(m in r.output for m in MARKERS[sanitizer])


def fisher_p(buggy_reports: int, fixed_reports: int, runs: int) -> float:
    # One-sided Fisher's exact test. It gives the chance that buggy gets at least this many
    # of the reports if both versions really report equally often.
    total = buggy_reports + fixed_reports
    hits = sum(
        math.comb(runs, x) * math.comb(runs, total - x)
        for x in range(buggy_reports, min(runs, total) + 1)
    )
    return hits / math.comb(2 * runs, total)


def decide_counts(buggy_reports: int, fixed_reports: int, runs: int) -> str:
    if buggy_reports == 0:
        return "no_report"
    if fixed_reports > 0:
        return "reports_on_fixed_too"
    if runs == 1:
        # this build gives the same result every run, so one run is enough
        return "proven"
    if fisher_p(buggy_reports, fixed_reports, runs) < ALPHA:
        return "proven"
    return "unreliable"


def label(claim: str | None, has_bug: bool, status: str) -> str:
    # the one-word outcome, worked out from what the model said, the truth and the proof
    if claim is None or claim == "none":
        if status != "no_test":
            _impossible(claim, has_bug, status)
        if claim is None:
            return "bad_test"  # the answer was broken
        return "missed" if has_bug else "correct_none"

    if status == "docker_failed":
        return "not_graded"
    if has_bug:
        if status == "proven":
            return "found"
        if status == "no_report":
            return "missed"
        if status in (
            "does_not_compile",
            "reports_on_fixed_too",
            "unreliable",
            "fixed_did_not_finish",
        ):
            return "bad_test"
    else:
        if status in ("no_report", "does_not_compile"):
            return "false_alarm"
        if status == "reports_on_correct_code":
            return "needs_review"
    _impossible(claim, has_bug, status)


def _impossible(claim: str | None, has_bug: bool, status: str):
    # a combination the grader should never produce, so fail loudly
    raise ValueError(f"no outcome for claim={claim!r}, has_bug={has_bug}, proof={status!r}")


def grade(problem: Problem, answer: ParsedAnswer) -> Grade:
    claim = None if answer.error else answer.verdict
    proof = prove(problem, answer.test) if claim == "bug" else NO_TEST
    return Grade(claim, problem.has_bug, proof, label(claim, problem.has_bug, proof.status))


def prove(problem: Problem, test: str) -> Proof:
    # Runs the test and says what it showed. Knows nothing about verdicts.
    if problem.has_bug:
        return _prove_against_fixed(problem, test)
    return _prove_on_correct_code(problem, test)


def _prove_against_fixed(problem: Problem, test: str) -> Proof:
    bad = None  # a build that reported on buggy but couldn't separate it from fixed
    last = None
    for sanitizer in BUILDS:
        runs = THREAD_RUNS if sanitizer == "thread" else 1
        with (
            tempfile.TemporaryDirectory() as buggy_out,
            tempfile.TemporaryDirectory() as fixed_out,
        ):
            b = _build_version(problem, "buggy", test, sanitizer, Path(buggy_out))
            if b.sandbox_failed or not b.compiled:
                return _failed_build(b, sanitizer, None)

            buggy_runs = _execute(Path(buggy_out), runs)
            last = buggy_runs[-1]
            if last.sandbox_failed:
                return Proof("docker_failed", sanitizer, last, None)
            buggy_hits = [r for r in buggy_runs if reported(r, sanitizer)]
            if not buggy_hits:
                continue
            shown = buggy_hits[0]

            f = _build_version(problem, "fixed", test, sanitizer, Path(fixed_out))
            if f.sandbox_failed or not f.compiled:
                return _failed_build(f, sanitizer, shown)

            fixed_runs = _execute(Path(fixed_out), runs)
            if fixed_runs[-1].sandbox_failed:
                return Proof("docker_failed", sanitizer, shown, fixed_runs[-1])
            fixed_hits = [r for r in fixed_runs if reported(r, sanitizer)]
            counts = (len(buggy_hits), len(fixed_hits), runs)

            stuck = [r for r in fixed_runs if r.timed_out or r.out_of_memory]
            if stuck:
                # can't tell whether fixed would have stayed quiet
                bad = Proof("fixed_did_not_finish", sanitizer, shown, stuck[0], *counts)
                continue

            status = decide_counts(*counts)
            fixed_shown = fixed_hits[0] if fixed_hits else fixed_runs[0]
            p = Proof(status, sanitizer, shown, fixed_shown, *counts)
            if status == "proven":
                return p
            bad = p

    if bad:
        return bad
    # nothing reported on buggy, so fixed never ran. Keep the last buggy run for the logs.
    return Proof("no_report", BUILDS[-1], last, None, 0, 0, THREAD_RUNS)


def _prove_on_correct_code(problem: Problem, test: str) -> Proof:
    # A problem without a bug has one version (in buggy/). Any report there needs a person.
    last = None
    for sanitizer in BUILDS:
        runs = THREAD_RUNS if sanitizer == "thread" else 1
        with tempfile.TemporaryDirectory() as out:
            b = _build_version(problem, "buggy", test, sanitizer, Path(out))
            if b.sandbox_failed or not b.compiled:
                return _failed_build(b, sanitizer, None)

            results = _execute(Path(out), runs)
            last = results[-1]
            if last.sandbox_failed:
                return Proof("docker_failed", sanitizer, last, None)
            hits = [r for r in results if reported(r, sanitizer)]
            if hits:
                status = "reports_on_correct_code"
                return Proof(status, sanitizer, hits[0], None, len(hits), 0, runs)

    return Proof("no_report", BUILDS[-1], last, None, 0, 0, THREAD_RUNS)


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


def _failed_build(b: BuildResult, sanitizer: str, shown: RunResult | None) -> Proof:
    status = "docker_failed" if b.sandbox_failed else "does_not_compile"
    # keep the compiler output, as a RunResult, so it ends up in the logs
    failed = RunResult(
        compiled=False,
        exit_code=None,
        output=b.output,
        timed_out=False,
        out_of_memory=False,
        seconds=b.seconds,
        sandbox_failed=b.sandbox_failed,
    )
    if shown is None:
        return Proof(status, sanitizer, failed, None)
    return Proof(status, sanitizer, shown, failed)


def _execute(out_dir: Path, runs: int) -> list[RunResult]:
    results = []
    for _ in range(runs):
        r = execute(out_dir, env=SAN_ENV)
        results.append(r)
        if r.sandbox_failed:
            break
    return results

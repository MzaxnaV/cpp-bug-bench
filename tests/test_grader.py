from pathlib import Path

from cpp_bug_bench.answer import ParsedAnswer
from cpp_bug_bench.grader import (
    SANITIZER_EXIT,
    _build_version,
    decide_counts,
    fired,
    fisher_p,
    grade,
    load_problem,
)
from cpp_bug_bench.sandbox import SAN_ENV, RunResult, execute

PROBLEMS = Path(__file__).parents[1] / "problems"
ASAN_REPORT = "==1==ERROR: AddressSanitizer: heap-use-after-free on address 0x1"


def result(exit_code: int | None, output: str, compiled: bool = True) -> RunResult:
    return RunResult(
        compiled=compiled,
        exit_code=exit_code,
        output=output,
        timed_out=False,
        out_of_memory=False,
        seconds=0.0,
        sandbox_failed=False,
    )


def bug_answer(test: str) -> ParsedAnswer:
    return ParsedAnswer(verdict="bug", review="", test=test, fence_stripped=False, error=None)


def test_load_problem_reads_toml():
    p = load_problem(PROBLEMS / "p0001")
    assert p.id == "p0001"
    assert p.sanitizer == "address"
    assert p.has_bug is True


def test_fired_needs_exit_code_and_marker():
    assert fired(result(SANITIZER_EXIT, ASAN_REPORT), "address")


def test_exit_code_alone_is_not_fired():
    # e.g. the test calls exit(77) itself
    assert not fired(result(SANITIZER_EXIT, "nothing here"), "address")


def test_marker_alone_is_not_fired():
    # e.g. the test prints the marker text, or an assert fails after it
    assert not fired(result(1, ASAN_REPORT), "address")


def test_marker_of_other_sanitizer_is_not_fired():
    assert not fired(result(SANITIZER_EXIT, ASAN_REPORT), "thread")


def test_combined_sanitizer_accepts_either_marker():
    ubsan = "code.hpp:3:5: runtime error: signed integer overflow"
    assert fired(result(SANITIZER_EXIT, ASAN_REPORT), "address,undefined")
    assert fired(result(SANITIZER_EXIT, ubsan), "address,undefined")


def test_compile_failure_is_not_fired():
    assert not fired(result(None, ASAN_REPORT, compiled=False), "address")


def test_malformed_answer_is_invalid():
    error = "missing verdict"
    bad = ParsedAnswer(verdict=None, review="", test="", fence_stripped=False, error=error)
    g = grade(load_problem(PROBLEMS / "p0001"), bad)
    assert g.outcome == "test_invalid" and g.reason == "missing verdict"


def test_verdict_none_is_missed():
    none = ParsedAnswer(verdict="none", review="", test="", fence_stripped=False, error=None)
    assert grade(load_problem(PROBLEMS / "p0001"), none).outcome == "missed"


def test_fisher_p_matches_hand_computed_values():
    assert abs(fisher_p(6, 0, 10) - 210 / 38760) < 1e-12  # C(10,6) / C(20,6)
    assert abs(fisher_p(5, 0, 10) - 252 / 15504) < 1e-12  # C(10,5) / C(20,5)
    assert abs(fisher_p(10, 0, 10) - 1 / 184756) < 1e-12  # 1 / C(20,10)


def test_decide_counts():
    assert decide_counts(6, 0, 10) == ("found", "fires on buggy only")
    assert decide_counts(5, 0, 10) == ("test_invalid", "too flaky")
    assert decide_counts(3, 0, 10) == ("test_invalid", "too flaky")
    assert decide_counts(10, 1, 10) == ("test_invalid", "fires on both")
    assert decide_counts(0, 0, 10) == ("missed", "did not fire on buggy")
    assert decide_counts(1, 0, 1) == ("found", "fires on buggy only")  # deterministic build


# The tests below run Docker.


def test_proof_fires_on_buggy_only(tmp_path):
    p = load_problem(PROBLEMS / "p0001")
    proof = (p.dir / "proof" / "test.cpp").read_text()
    for version, should_fire in [("buggy", True), ("fixed", False)]:
        out = tmp_path / version
        out.mkdir()
        assert _build_version(p, version, proof, p.sanitizer, out).compiled
        assert fired(execute(out, env=SAN_ENV), p.sanitizer) is should_fire


def test_grade_proof_is_found():
    p = load_problem(PROBLEMS / "p0001")
    g = grade(p, bug_answer((p.dir / "proof" / "test.cpp").read_text()))
    assert g.outcome == "found", g.reason
    assert g.sanitizer == "address,undefined"


def test_grade_quiet_test_is_missed():
    g = grade(load_problem(PROBLEMS / "p0001"), bug_answer('#include "code.hpp"\nint main() {}\n'))
    assert g.outcome == "missed" and g.fixed is None


def test_grade_compile_error_is_invalid():
    g = grade(load_problem(PROBLEMS / "p0001"), bug_answer("int main() { return x; }\n"))
    assert g.outcome == "test_invalid" and g.reason == "does not compile"


def test_grade_fires_on_both_is_invalid():
    # a use-after-free of its own, unrelated to the problem's code
    test = '#include "code.hpp"\nint main() { int* p = new int(1); delete p; return *p; }\n'
    g = grade(load_problem(PROBLEMS / "p0001"), bug_answer(test))
    assert g.outcome == "test_invalid" and g.reason == "fires on both"


def test_grade_race_proof_is_found_by_thread_build():
    # ASan+UBSan sees nothing here. Only the TSan build separates buggy from fixed.
    p = load_problem(PROBLEMS / "p0006")
    g = grade(p, bug_answer((p.dir / "proof" / "test.cpp").read_text()))
    assert g.outcome == "found", g.reason
    assert g.sanitizer == "thread"
    assert g.runs == 10 and g.buggy_fired >= 6 and g.fixed_fired == 0

from pathlib import Path

import pytest

from cpp_bug_bench.answer import ParsedAnswer
from cpp_bug_bench.grader import (
    SANITIZER_EXIT,
    _build_version,
    decide_counts,
    fisher_p,
    grade,
    label,
    load_problem,
    reported,
)
from cpp_bug_bench.sandbox import SAN_ENV, RunResult, execute

PROBLEMS = Path(__file__).parents[1] / "problems"
ASAN_REPORT = "==1==ERROR: AddressSanitizer: heap-use-after-free on address 0x1"
QUIET_TEST = '#include "code.hpp"\nint main() {}\n'
# a use-after-free of its own, unrelated to the problem's code
OWN_UAF_TEST = '#include "code.hpp"\nint main() { int* p = new int(1); delete p; return *p; }\n'


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


def answer(verdict: str | None, test: str = "", error: str | None = None) -> ParsedAnswer:
    return ParsedAnswer(verdict=verdict, review="", test=test, fence_stripped=False, error=error)


def test_load_problem_reads_toml():
    p = load_problem(PROBLEMS / "p0001")
    assert p.id == "p0001"
    assert p.sanitizer == "address"
    assert p.has_bug is True


def test_reported_needs_exit_code_and_marker():
    assert reported(result(SANITIZER_EXIT, ASAN_REPORT), "address")


def test_exit_code_alone_is_not_a_report():
    # e.g. the test calls exit(77) itself
    assert not reported(result(SANITIZER_EXIT, "nothing here"), "address")


def test_marker_alone_is_not_a_report():
    # e.g. the test prints the marker text, or an assert fails after it
    assert not reported(result(1, ASAN_REPORT), "address")


def test_marker_of_other_sanitizer_is_not_a_report():
    assert not reported(result(SANITIZER_EXIT, ASAN_REPORT), "thread")


def test_combined_sanitizer_accepts_either_marker():
    ubsan = "code.hpp:3:5: runtime error: signed integer overflow"
    assert reported(result(SANITIZER_EXIT, ASAN_REPORT), "address,undefined")
    assert reported(result(SANITIZER_EXIT, ubsan), "address,undefined")


def test_compile_failure_is_not_a_report():
    assert not reported(result(None, ASAN_REPORT, compiled=False), "address")


def test_fisher_p_matches_hand_computed_values():
    assert abs(fisher_p(6, 0, 10) - 210 / 38760) < 1e-12  # C(10,6) / C(20,6)
    assert abs(fisher_p(5, 0, 10) - 252 / 15504) < 1e-12  # C(10,5) / C(20,5)
    assert abs(fisher_p(10, 0, 10) - 1 / 184756) < 1e-12  # 1 / C(20,10)


def test_decide_counts():
    assert decide_counts(6, 0, 10) == "proven"
    assert decide_counts(5, 0, 10) == "unreliable"
    assert decide_counts(3, 0, 10) == "unreliable"
    assert decide_counts(10, 1, 10) == "reports_on_fixed_too"
    assert decide_counts(0, 0, 10) == "no_report"
    assert decide_counts(1, 0, 1) == "proven"  # the build that gives the same result every run


@pytest.mark.parametrize(
    "claim, has_bug, status, outcome",
    [
        (None, True, "no_test", "bad_test"),
        (None, False, "no_test", "bad_test"),
        ("none", True, "no_test", "missed"),
        ("none", False, "no_test", "correct_none"),
        ("bug", True, "proven", "found"),
        ("bug", True, "no_report", "missed"),
        ("bug", True, "does_not_compile", "bad_test"),
        ("bug", True, "reports_on_fixed_too", "bad_test"),
        ("bug", True, "unreliable", "bad_test"),
        ("bug", True, "fixed_did_not_finish", "bad_test"),
        ("bug", True, "docker_failed", "not_graded"),
        ("bug", False, "no_report", "false_alarm"),
        ("bug", False, "does_not_compile", "false_alarm"),
        ("bug", False, "reports_on_correct_code", "needs_review"),
        ("bug", False, "docker_failed", "not_graded"),
    ],
)
def test_label(claim, has_bug, status, outcome):
    assert label(claim, has_bug, status) == outcome


@pytest.mark.parametrize(
    "claim, has_bug, status",
    [
        ("bug", False, "proven"),
        ("bug", False, "unreliable"),
        ("bug", True, "reports_on_correct_code"),
        ("none", True, "proven"),
    ],
)
def test_label_rejects_combinations_that_cannot_happen(claim, has_bug, status):
    with pytest.raises(ValueError):
        label(claim, has_bug, status)


def test_broken_answer_is_bad_test():
    g = grade(load_problem(PROBLEMS / "p0001"), answer(None, error="missing verdict"))
    assert g.claim is None and g.outcome == "bad_test" and g.proof.status == "no_test"


def test_verdict_none_on_bug_problem_is_missed():
    g = grade(load_problem(PROBLEMS / "p0001"), answer("none"))
    assert g.outcome == "missed" and g.proof.status == "no_test"


def test_verdict_none_on_no_bug_problem_is_correct_none():
    g = grade(load_problem(PROBLEMS / "p0009"), answer("none"))
    assert g.outcome == "correct_none" and g.proof.status == "no_test"


# The tests below run Docker.


def test_proof_reports_on_buggy_only(tmp_path):
    p = load_problem(PROBLEMS / "p0001")
    proof = (p.dir / "proof" / "test.cpp").read_text()
    for version, should_report in [("buggy", True), ("fixed", False)]:
        out = tmp_path / version
        out.mkdir()
        assert _build_version(p, version, proof, p.sanitizer, out).compiled
        assert reported(execute(out, env=SAN_ENV), p.sanitizer) is should_report


def test_grade_proof_is_found():
    p = load_problem(PROBLEMS / "p0001")
    g = grade(p, answer("bug", (p.dir / "proof" / "test.cpp").read_text()))
    assert g.outcome == "found" and g.proof.status == "proven"
    assert g.proof.sanitizer == "address,undefined"


def test_grade_quiet_test_is_missed():
    g = grade(load_problem(PROBLEMS / "p0001"), answer("bug", QUIET_TEST))
    assert g.outcome == "missed" and g.proof.status == "no_report"
    assert g.proof.fixed is None


def test_grade_compile_error_is_bad_test():
    g = grade(load_problem(PROBLEMS / "p0001"), answer("bug", "int main() { return x; }\n"))
    assert g.outcome == "bad_test" and g.proof.status == "does_not_compile"


def test_grade_reports_on_fixed_too_is_bad_test():
    g = grade(load_problem(PROBLEMS / "p0001"), answer("bug", OWN_UAF_TEST))
    assert g.outcome == "bad_test" and g.proof.status == "reports_on_fixed_too"


def test_grade_race_proof_is_found_by_thread_build():
    # ASan+UBSan sees nothing here. Only the TSan build separates buggy from fixed.
    p = load_problem(PROBLEMS / "p0006")
    g = grade(p, answer("bug", (p.dir / "proof" / "test.cpp").read_text()))
    assert g.outcome == "found" and g.proof.status == "proven"
    assert g.proof.sanitizer == "thread"
    assert g.proof.runs == 10 and g.proof.buggy_reports >= 6 and g.proof.fixed_reports == 0


def test_no_bug_problem_quiet_test_is_false_alarm():
    # uses the queue as documented, so nothing should report
    test = (
        '#include "code.hpp"\n'
        "int main() { BlockingQueue<int> q; q.push(1); return q.pop() - 1; }\n"
    )
    g = grade(load_problem(PROBLEMS / "p0009"), answer("bug", test))
    assert g.outcome == "false_alarm" and g.proof.status == "no_report"


def test_no_bug_problem_report_needs_review():
    g = grade(load_problem(PROBLEMS / "p0009"), answer("bug", OWN_UAF_TEST))
    assert g.outcome == "needs_review" and g.proof.status == "reports_on_correct_code"


def test_no_bug_problem_compile_error_is_false_alarm():
    # items_ is private, so this doesn't compile
    test = '#include "code.hpp"\nint main() { BlockingQueue<int> q; return q.items_.size(); }\n'
    g = grade(load_problem(PROBLEMS / "p0009"), answer("bug", test))
    assert g.outcome == "false_alarm" and g.proof.status == "does_not_compile"

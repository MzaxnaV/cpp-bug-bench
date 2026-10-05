"""Tests for the sandbox runner. Needs Docker and the cbb-grader image.

Each test compiles and runs one program from tests/cpp/ in a fresh container.
"""

from pathlib import Path

import pytest

from cpp_bug_bench.sandbox import run

CHECK_DIR = Path(__file__).parent / "cpp"


def test_asan_reports_heap_overflow():
    r = run(CHECK_DIR, "bug.cpp", "address")
    assert r.compiled and r.exit_code == 1
    assert "AddressSanitizer: heap-buffer-overflow" in r.output


def test_ubsan_reports_signed_overflow():
    r = run(CHECK_DIR, "ub.cpp", "undefined")
    assert r.compiled and r.exit_code == 1
    assert "runtime error: signed integer overflow" in r.output


def test_tsan_reports_data_race():
    r = run(CHECK_DIR, "race.cpp", "thread")
    assert r.compiled and r.exit_code == 66
    assert "ThreadSanitizer: data race" in r.output


def test_clean_code_stays_quiet():
    r = run(CHECK_DIR, "clean.cpp", "address,undefined")
    assert r.compiled and r.exit_code == 0
    assert "Sanitizer" not in r.output


def test_endless_loop_times_out():
    r = run(CHECK_DIR, "loop.cpp", "address", timeout_s=2)
    assert r.compiled and r.timed_out
    assert not r.out_of_memory


def test_memory_hog_runs_out_of_memory():
    r = run(CHECK_DIR, "hog.cpp", "address")
    assert r.compiled and r.out_of_memory
    assert not r.timed_out


def test_compile_error_is_not_a_run():
    r = run(CHECK_DIR, "broken.cpp", "address")
    assert not r.compiled
    assert r.exit_code is None
    assert "error:" in r.output  # clang's message is kept for the log


def test_unknown_sanitizer_is_rejected():
    with pytest.raises(ValueError):
        run(CHECK_DIR, "bug.cpp", "adress")


def test_nothing_fails_the_sandbox_on_normal_runs():
    r = run(CHECK_DIR, "clean.cpp", "address")
    assert not r.sandbox_failed


# TODO: compile timeout: needs a program that reliably compiles slowly
# TODO: sandbox_failed=True: needs Docker itself to hang

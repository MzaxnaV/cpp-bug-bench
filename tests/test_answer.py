"""Tests for the answer parser. Plain strings, no Docker."""

from cpp_bug_bench.answer import parse

TEST_CODE = "int main() { return 0; }"


def test_bug_with_test_is_valid():
    a = parse(
        f"<review>\noff by one\n</review>\n<verdict>bug</verdict>\n<test>\n{TEST_CODE}\n</test>"
    )
    assert a.error is None
    assert a.verdict == "bug"
    assert a.review == "off by one"
    assert a.test == TEST_CODE
    assert not a.fence_stripped


def test_none_is_valid_and_ignores_any_test():
    a = parse(f"<verdict>none</verdict>\n<test>\n{TEST_CODE}\n</test>")
    assert a.error is None
    assert a.verdict == "none"
    assert a.test == ""


def test_review_is_optional():
    a = parse(f"<verdict>bug</verdict>\n<test>\n{TEST_CODE}\n</test>")
    assert a.error is None
    assert a.review == ""


def test_verdict_ignores_case_and_spaces():
    assert parse("<verdict> None </verdict>").verdict == "none"
    assert parse(f"<verdict>BUG</verdict>\n<test>{TEST_CODE}</test>").verdict == "bug"


def test_missing_verdict_is_invalid():
    a = parse(f"<review>looks fine</review>\n<test>\n{TEST_CODE}\n</test>")
    assert a.error == "missing verdict"
    assert a.verdict is None


def test_bad_verdict_is_invalid():
    a = parse("<verdict>maybe</verdict>")
    assert a.error == "bad verdict: 'maybe'"


def test_bug_without_test_is_invalid():
    assert parse("<verdict>bug</verdict>").error == "verdict bug but no test"


def test_bug_with_empty_test_is_invalid():
    assert parse("<verdict>bug</verdict>\n<test>\n   \n</test>").error == "verdict bug but no test"


def test_duplicate_tag_is_invalid():
    test = f"<test>\n{TEST_CODE}\n</test>"
    a = parse(f"<verdict>bug</verdict>\n{test}\n{test}")
    assert a.error == "duplicate <test>"


def test_tag_mentioned_mid_sentence_is_ignored():
    reply = (
        "<review>\nMy <test> below overflows the buffer.\n</review>\n"
        f"<verdict>bug</verdict>\n<test>\n{TEST_CODE}\n</test>"
    )
    a = parse(reply)
    assert a.error is None
    assert a.test == TEST_CODE


def test_fence_is_stripped_and_recorded():
    a = parse(f"<verdict>bug</verdict>\n<test>\n```cpp\n{TEST_CODE}\n```\n</test>")
    assert a.error is None
    assert a.test == TEST_CODE
    assert a.fence_stripped


def test_fence_without_language_is_stripped():
    a = parse(f"<verdict>bug</verdict>\n<test>\n```\n{TEST_CODE}\n```\n</test>")
    assert a.test == TEST_CODE
    assert a.fence_stripped


def test_fence_inside_code_is_left_alone():
    # Only a fence wrapping the whole test is removed.
    code = f"{TEST_CODE}\n// ```not a fence```"
    a = parse(f"<verdict>bug</verdict>\n<test>\n{code}\n</test>")
    assert a.test == code
    assert not a.fence_stripped

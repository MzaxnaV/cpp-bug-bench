from pathlib import Path

from cpp_bug_bench.answer import parse
from cpp_bug_bench.grader import load_problem
from cpp_bug_bench.prompt import TEMPLATE, build_prompt

PROBLEMS = Path(__file__).parents[1] / "problems"


def test_prompt_contains_the_buggy_code():
    p = load_problem(PROBLEMS / "p0001")
    code = (p.dir / "buggy" / "code.hpp").read_text().strip()
    assert code in build_prompt(p)


def test_prompt_leaks_nothing_about_the_answer():
    p = load_problem(PROBLEMS / "p0001")
    prompt = build_prompt(p)
    fixed = (p.dir / "fixed" / "code.hpp").read_text()
    assert "p0001" not in prompt
    assert "iterator-invalidation" not in prompt  # category
    assert "reallocates" not in prompt  # from the summary
    assert "canary" not in prompt.lower()
    assert "std::size_t n = v.size()" in fixed and "std::size_t n = v.size()" not in prompt


def test_template_has_one_code_slot():
    assert TEMPLATE.count("{code}") == 1


def test_example_in_the_prompt_parses():
    # if the prompt's example format and the parser ever disagree, this fails
    start = TEMPLATE.index("<review>")
    end = TEMPLATE.index("</test>") + len("</test>")
    a = parse(TEMPLATE[start:end])
    assert a.error is None and a.verdict == "bug"

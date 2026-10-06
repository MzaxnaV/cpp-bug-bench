import sys
from pathlib import Path

from cpp_bug_bench.grader import load_problem
from cpp_bug_bench.prompt import build_prompt

print(build_prompt(load_problem(Path("problems") / sys.argv[1])))

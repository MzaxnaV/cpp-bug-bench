import sys
from pathlib import Path

from cpp_bug_bench.answer import parse
from cpp_bug_bench.grader import grade, load_problem

# usage: grade_reply.py p0001 results/scratch/reply.txt
problem = load_problem(Path("problems") / sys.argv[1])
answer = parse(Path(sys.argv[2]).read_text())
print(f"verdict: {answer.verdict}  error: {answer.error}  fence_stripped: {answer.fence_stripped}")

if not problem.has_bug:
    # grading problems without a bug isn't built yet
    print("no bug in this problem: 'none' is correct, 'bug' is a false alarm")
    sys.exit()

g = grade(problem, answer)
print(f"outcome: {g.outcome} ({g.reason})")
for name, r in [("buggy", g.buggy), ("fixed", g.fixed)]:
    if r is None:
        continue
    summary = [line for line in r.output.splitlines() if "SUMMARY" in line]
    print(f"{name}: exit {r.exit_code}  {summary or 'no sanitizer report'}")
    if not r.compiled:
        print("\n".join(r.output.splitlines()[:15]))  # first compiler errors

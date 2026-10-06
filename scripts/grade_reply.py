import sys
from pathlib import Path

from cpp_bug_bench.answer import parse
from cpp_bug_bench.grader import grade, load_problem

# Run as grade_reply.py p0001 results/scratch/reply.txt
problem = load_problem(Path("problems") / sys.argv[1])
answer = parse(Path(sys.argv[2]).read_text())
print(f"verdict: {answer.verdict}  error: {answer.error}  fence_stripped: {answer.fence_stripped}")

g = grade(problem, answer)
p = g.proof
print(f"outcome: {g.outcome}  claim: {g.claim}  has_bug: {g.has_bug}")
print(f"proof: {p.status}  build: {p.sanitizer}  expected: {problem.sanitizer}")
if p.runs > 1:
    print(f"reports: buggy {p.buggy_reports}/{p.runs}, fixed {p.fixed_reports}/{p.runs}")

# a problem without a bug has one version, kept in the "buggy" slot
first = "buggy" if problem.has_bug else "code"
for name, r in [(first, p.buggy), ("fixed", p.fixed)]:
    if r is None:
        continue
    summary = [line for line in r.output.splitlines() if "SUMMARY" in line]
    print(f"{name}: exit {r.exit_code}  {summary or 'no sanitizer report'}")
    if not r.compiled:
        print("\n".join(r.output.splitlines()[:15]))  # first compiler errors

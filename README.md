# cpp-bug-bench

A benchmark that tests whether language models can find real bugs in C++ code **and prove them**.

> **Work in progress.**

Each problem is a piece of C++ code. The model is asked to review it and either report a bug it can prove with a test, or say it found none. The prompt never says whether a bug exists.

A claimed bug only counts if the model's test proves it:

- The problem ships two versions of the code, `buggy` and `fixed`.
- The model's test is compiled against both, with a clang sanitizer turned on (AddressSanitizer, UndefinedBehaviorSanitizer or ThreadSanitizer).
- **Found** means the sanitizer reports an error on the buggy version and stays quiet on the fixed one.

The model's own asserts or explanations are never taken as proof. Only a sanitizer report counts. A run counts as "fired" only when the program exits with the sanitizer's exit code (set to 77) **and** the sanitizer's report is in the output. Either one alone can be faked by the test.

The benchmark only covers bugs a sanitizer can detect, such as memory errors, undefined behaviour and data races. Logic bugs (wrong results without undefined behaviour) are out of scope for now.

Some problems contain no bug at all. On those the correct answer is "no bug", and a test that fails to fire shows the claimed bug was a false alarm.

## Outcomes

Every grade keeps three facts. The **claim** is what the model said (`bug` or `none`). **Has bug** is whether the problem really has one. The **proof** is what happened when we ran the model's test. One summary outcome is worked out from these three.

| Outcome | Meaning |
|---|---|
| `found` | Claimed the bug and proved it |
| `missed` | Said "no bug" on a problem that has one, or claimed a bug but the test showed nothing |
| `bad_test` | The answer was broken, or the test didn't compile, also reported on the corrected code, reported too rarely to count, or didn't finish |
| `not_graded` | Something on our side failed (Docker, rate limit, provider). Retried, and never counted for or against the model |
| `correct_none` | Said "no bug" on code that has none |
| `false_alarm` | Claimed a bug in code that has none |
| `needs_review` | Claimed a bug in code that has none, and the sanitizer did report. A person checks whether the test caused it or the code really has a bug |

Proof statuses are `proven`, `no_report`, `reports_on_fixed_too`, `unreliable`, `fixed_did_not_finish`, `does_not_compile`, `reports_on_correct_code`, `docker_failed` and `no_test`.

## Problems

Each problem is a folder in `problems/`:

```
problems/p0001/
  problem.toml      # id, sanitizer, has_bug, plus hidden notes (category, summary, source, added)
  buggy/code.hpp    # the code the model sees
  fixed/code.hpp    # the smallest change that removes the bug
  proof/test.cpp    # a known-good test that fires on buggy and stays quiet on fixed
```

- IDs are neutral (`p0001`), so the name gives nothing away.
- One bug per problem.
- The model's test must `#include "code.hpp"` and define `main()`.
- `problem.toml` and `proof/test.cpp` carry a canary GUID, so leaks into training data can be detected. `code.hpp` doesn't, because the model sees it.

Check that a problem's proof works:

```bash
uv run python scripts/check_proof.py p0001
```

## How it runs

- **Harness** in Python, managed with [uv](https://docs.astral.sh/uv/).
- **Models** called through [OpenRouter](https://openrouter.ai/).
- **Grading** runs inside Docker, with a pinned Ubuntu and clang version. Each test runs in a fresh container with no network and with CPU, memory and time limits, so model-written code is sandboxed and results are reproducible.
- **Logs** have one JSON line per attempt, recording the model, the provider that served it, tokens, cost, outcome, the Docker image digest and the kernel version.

## Setup

You need Linux (or WSL2), Docker, Python 3.13+ and uv.

1. Clone the repo.
2. Create a `.env` file in the repo root containing your OpenRouter key:
   ```
   OPENROUTER_API_KEY=sk-or-...
   ```
   `.env` is git-ignored and is never committed.

# Roadmap
- [x] Sanitizer-verified grading in a locked-down Docker sandbox
- [x] Tests run under every sanitizer, so the prompt never hints at the bug type
- [ ] Repeat runs for data races, decided statistically
- [ ] False-alarm measurement on bug-free code
- [ ] Model runs through OpenRouter, logged and cost-capped
- [ ] v0 with 10 hand-written problems
- [ ] v1 with harder problems from real repositories

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

Every attempt ends in exactly one bucket:

| Outcome | Meaning |
|---|---|
| `found` | The test fires the sanitizer on the buggy version only |
| `missed` | No proven bug |
| `test_invalid` | The test doesn't compile, the answer is malformed, the test fires on both versions, or the result is flaky |
| `infra_error` | Something outside the model failed (rate limit, timeout, provider error, Docker failure). Retried and reported separately, never counted as a miss |

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

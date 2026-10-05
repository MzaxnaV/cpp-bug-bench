# cpp-bug-bench

A benchmark that tests whether language models can find real bugs in C++ code **and prove them**.

> **Status:** work in progress.

Each problem is a piece of C++ code. The model is asked to review it and either report a bug it can prove with a test, or say it found none. The prompt never says whether a bug exists.

A claimed bug only counts if the model's test proves it:

- The problem ships two versions of the code: `buggy` and `fixed`.
- The model's test is compiled against both, with a clang sanitizer turned on (AddressSanitizer, UndefinedBehaviorSanitizer or ThreadSanitizer).
- **Found** means the sanitizer reports an error on the buggy version and stays quiet on the fixed one.

The model's own asserts or explanations are never taken as proof. Only a sanitizer report counts.

Some problems contain no bug at all. On those the correct answer is "no bug", and a test that fails to fire shows the claimed bug was a false alarm.

## Outcomes

Every attempt ends in exactly one bucket:

| Outcome | Meaning |
|---|---|
| `found` | The test fires the sanitizer on the buggy version only |
| `missed` | No proven bug |
| `test_invalid` | The test doesn't compile, the answer is malformed, the test fires on both versions, or the result is flaky |
| `infra_error` | Something outside the model failed (rate limit, timeout, provider error, Docker failure). Retried and reported separately, never counted as a miss |

## How it runs

- **Harness:** Python, managed with [uv](https://docs.astral.sh/uv/).
- **Models:** called through [OpenRouter](https://openrouter.ai/).
- **Grading:** inside Docker, with a pinned Ubuntu and clang version. Each test runs in a fresh container with no network and with CPU, memory and time limits, so model-written code is sandboxed and results are reproducible.
- **Logs:** one JSON line per attempt, recording the model, the provider that served it, tokens, cost, outcome, the Docker image digest and the kernel version.

## Setup

Requirements: Linux (or WSL2), Docker, Python 3.12+ and uv.

1. Clone the repo.
2. Create a `.env` file in the repo root containing your OpenRouter key:
   ```
   OPENROUTER_API_KEY=sk-or-...
   ```
   `.env` is git-ignored and is never committed.

# ToDo
- [ ] Docker grading sandbox
- [ ] Grader
- [ ] Model client (OpenRouter)
- [ ] First 10 problems
- [ ] Run instructions

from cpp_bug_bench.grader import Problem

# Bump when the text changes: results from different versions aren't comparable.
PROMPT_VERSION = "v1"

TEMPLATE = """\
Review the C++ code in code.hpp below. If you find a bug, prove it with a test. \
If you can't prove any bug, say so.

Look for bugs that AddressSanitizer, UndefinedBehaviorSanitizer or ThreadSanitizer can detect, \
such as memory errors, undefined behaviour and data races.

## Rules for your test

- Your test is a complete C++20 program. It must `#include "code.hpp"` and define `main()`. \
Only the C++ standard library is available.
- It is compiled with clang 21 (`-std=c++20 -g`) twice, and run after each build:
  1. with AddressSanitizer and UndefinedBehaviorSanitizer (`-fsanitize=address,undefined`)
  2. with ThreadSanitizer (`-fsanitize=thread`)
- Each run has a 10 second time limit, 1 GB of memory, one CPU and no network.
- Your test proves a bug only if a sanitizer reports an error while it runs. \
Asserts, printed output and exit codes don't count.
- Use the code as documented, through what code.hpp declares. A report caused by breaking \
the code's stated requirements is not a bug in the code.

## Answer format

Answer with these tags, each starting at the beginning of a line:

<review>
Your reasoning (optional).
</review>
<verdict>bug</verdict>
<test>
The complete test program.
</test>

Use <verdict>bug</verdict> only together with a test. If you can't prove a bug, \
answer <verdict>none</verdict> and leave out the test.

## code.hpp

```cpp
{code}
```
"""


def build_prompt(problem: Problem) -> str:
    code = (problem.dir / "buggy" / "code.hpp").read_text().strip()
    return TEMPLATE.replace("{code}", code)

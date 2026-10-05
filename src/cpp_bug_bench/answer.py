import re
from dataclasses import dataclass

FENCE = re.compile(r"^```[\w+-]*\n(.*?)\n?```$", re.DOTALL)


def _find(reply: str, tag: str) -> tuple[int, str | None]:
    """Returns no of times <tag> opens at a line start, and the content of the first one."""
    t = re.escape(tag)
    count = len(re.findall(f"^<{t}>", reply, re.MULTILINE))
    m = re.search(f"^<{t}>(.*?)</{t}>", reply, re.MULTILINE | re.DOTALL)

    return count, (m.group(1) if m else None)


@dataclass(frozen=True)
class ParsedAnswer:
    verdict: str | None  # "bug" or "none"; None if the answer is invalid
    review: str
    test: str  # "" when verdict is none
    fence_stripped: bool  # a ``` fence was removed from the test
    error: str | None  # why it's invalid; None if valid


def parse(reply: str) -> ParsedAnswer:
    found = {tag: _find(reply, tag) for tag in ("review", "verdict", "test")}

    review = (found["review"][1] or "").strip()

    def invalid(why: str) -> ParsedAnswer:
        return ParsedAnswer(verdict=None, review=review, test="", fence_stripped=False, error=why)

    for tag, (count, _) in found.items():
        if count > 1:
            return invalid(f"duplicate <{tag}>")

    verdict = found["verdict"][1]
    if verdict is None:
        return invalid("missing verdict")

    verdict = verdict.strip().lower()

    if verdict not in ("bug", "none"):
        return invalid(f"bad verdict: {verdict!r}")

    if verdict == "none":
        return ParsedAnswer(
            verdict="none", review=review, test="", fence_stripped=False, error=None
        )

    test = (found["test"][1] or "").strip()
    if not test:
        return invalid("verdict bug but no test")

    m = FENCE.match(test)
    fence_stripped = m is not None
    if fence_stripped:
        test = m.group(1).strip()

    return ParsedAnswer(
        verdict="bug", review=review, test=test, fence_stripped=fence_stripped, error=None
    )

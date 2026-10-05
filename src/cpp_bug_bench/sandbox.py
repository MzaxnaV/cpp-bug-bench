import shlex
import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

IMAGE = "cbb-grader"
REPO_ROOT = Path(__file__).resolve().parents[2]
SECCOMP_PROFILE = REPO_ROOT / "docker" / "seccomp.json"
COMPILE_FAILED = 100  # TODO: a test that itself exits with 100 is misread as a compile failure
KILLED = 137
TIMEOUT_MARKER = "sending signal KILL"

SANITIZER_FLAGS = {
    "address": ["-fsanitize=address"],
    "undefined": ["-fsanitize=undefined", "-fno-sanitize-recover=all"],
    "thread": ["-fsanitize=thread"],
    "address,undefined": ["-fsanitize=address,undefined", "-fno-sanitize-recover=all"],
}


@dataclass(frozen=True)
class RunResult:
    compiled: bool  # False -> test_invalid, (meaningless if sandbox_failed)
    exit_code: int | None  # None if it never ran
    output: str  # compiler errors, or the program's output + sanitizer report
    timed_out: bool  # 137 + "sending signal KILL"
    out_of_memory: bool  # 137 without it
    seconds: float
    sandbox_failed: bool  # container never answered -> infra_error


def run(
    source_dir: Path,
    main_file: str,
    sanitizer: str,
    timeout_s: int = 10,
    compile_timeout_s: int = 300,
) -> RunResult:
    if sanitizer not in SANITIZER_FLAGS:
        raise ValueError(
            f"unknown sanitizer {sanitizer!r}; expected one of {list(SANITIZER_FLAGS)}"
        )

    name = f"cbb-{uuid.uuid4().hex[:12]}"
    flags = " ".join(SANITIZER_FLAGS[sanitizer])
    script = (
        f"timeout --verbose -s KILL {compile_timeout_s} "
        f"clang++-21 -std=c++20 -g {flags} /src/{shlex.quote(main_file)} -o /tmp/t "
        f"|| exit {COMPILE_FAILED}\n"
        f"timeout --verbose -s KILL {timeout_s} /tmp/t"
    )
    # fmt: off
    cmd = [
        "docker", "run", "--rm", "--name", name,
        "--network", "none",
        "--cpus=1", "--memory", "1g", "--memory-swap", "1g", "--pids-limit", "256",
        "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
        "--read-only", "--tmpfs", "/tmp:exec,size=256m",
        "--security-opt", f"seccomp={SECCOMP_PROFILE}",
        "-v", f"{source_dir.resolve()}:/src:ro",
        IMAGE,
        "bash", "-c", script,
    ]
    # fmt: on

    start = time.monotonic()
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=compile_timeout_s + timeout_s + 60
        )
    except subprocess.TimeoutExpired as e:
        subprocess.run(["docker", "kill", name], capture_output=True)
        return RunResult(
            compiled=False,  # compiled not known, False chosen as safe bet
            exit_code=None,
            output=_text(e.stdout) + _text(e.stderr),
            timed_out=False,
            out_of_memory=False,
            seconds=time.monotonic() - start,
            sandbox_failed=True,
        )
    seconds = time.monotonic() - start
    output = proc.stdout + proc.stderr

    code = proc.returncode
    compiled = code != COMPILE_FAILED
    killed = compiled and code == KILLED
    timed_out = killed and TIMEOUT_MARKER in output

    return RunResult(
        compiled=compiled,
        exit_code=code if compiled else None,
        output=output,
        timed_out=timed_out,
        out_of_memory=killed and not timed_out,
        seconds=seconds,
        sandbox_failed=False,
    )


def _text(x: str | bytes | None) -> str:
    if x is None:
        return ""
    return x.decode(errors="replace") if isinstance(x, bytes) else x

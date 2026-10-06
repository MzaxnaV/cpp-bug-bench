import os
import shlex
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass, replace
from pathlib import Path

IMAGE = "cbb-grader"
REPO_ROOT = Path(__file__).resolve().parents[2]
SECCOMP_PROFILE = REPO_ROOT / "docker" / "seccomp.json"
KILLED = 137
TIMEOUT_MARKER = "sending signal KILL"

SANITIZER_FLAGS = {
    "address": ["-fsanitize=address"],
    "undefined": ["-fsanitize=undefined", "-fno-sanitize-recover=all"],
    "thread": ["-fsanitize=thread"],
    "address,undefined": ["-fsanitize=address,undefined", "-fno-sanitize-recover=all"],
}

SAN_ENV = {
    "ASAN_OPTIONS": "exitcode=77",
    "UBSAN_OPTIONS": "halt_on_error=1:exitcode=77",
    "TSAN_OPTIONS": "exitcode=77",
}


@dataclass(frozen=True)
class RunResult:
    compiled: bool  # False means the test didn't compile (meaningless if sandbox_failed)
    exit_code: int | None  # None if it never ran
    output: str  # compiler errors, or the program's output + sanitizer report
    timed_out: bool  # 137 + "sending signal KILL"
    out_of_memory: bool  # 137 without it
    seconds: float
    sandbox_failed: bool  # the container never answered, so the attempt isn't graded


@dataclass(frozen=True)
class BuildResult:
    compiled: bool
    output: str  # compiler errors and warnings
    seconds: float
    sandbox_failed: bool  # the container never answered, so the attempt isn't graded


def build(
    source_dir: Path,
    main_file: str,
    sanitizer: str,
    out_dir: Path,
    compile_timeout_s: int = 300,
) -> BuildResult:
    # compiles in its own container and leaves the binary in out_dir as "t"
    if sanitizer not in SANITIZER_FLAGS:
        raise ValueError(
            f"unknown sanitizer {sanitizer!r}; expected one of {list(SANITIZER_FLAGS)}"
        )

    os.chmod(out_dir, 0o777)  # the container's user writes the binary here
    flags = " ".join(SANITIZER_FLAGS[sanitizer])
    script = (
        f"timeout --verbose -s KILL {compile_timeout_s} "
        f"clang++-21 -std=c++20 -g {flags} /src/{shlex.quote(main_file)} -o /out/t"
    )
    mounts = [f"{source_dir.resolve()}:/src:ro", f"{out_dir.resolve()}:/out"]
    code, output, seconds = _docker(mounts, None, script, compile_timeout_s + 60)

    if code is None:
        return BuildResult(compiled=False, output=output, seconds=seconds, sandbox_failed=True)
    return BuildResult(compiled=code == 0, output=output, seconds=seconds, sandbox_failed=False)


def execute(
    out_dir: Path,
    timeout_s: int = 10,
    env: dict[str, str] | None = None,
) -> RunResult:
    # runs the binary from build() in a fresh container. Call it again for another run.
    script = f"timeout --verbose -s KILL {timeout_s} /out/t"
    mounts = [f"{out_dir.resolve()}:/out:ro"]
    code, output, seconds = _docker(mounts, env, script, timeout_s + 60)

    if code is None:
        return RunResult(
            compiled=True,
            exit_code=None,
            output=output,
            timed_out=False,
            out_of_memory=False,
            seconds=seconds,
            sandbox_failed=True,
        )

    killed = code == KILLED
    timed_out = killed and TIMEOUT_MARKER in output
    return RunResult(
        compiled=True,
        exit_code=code,
        output=output,
        timed_out=timed_out,
        out_of_memory=killed and not timed_out,
        seconds=seconds,
        sandbox_failed=False,
    )


def run(
    source_dir: Path,
    main_file: str,
    sanitizer: str,
    timeout_s: int = 10,
    compile_timeout_s: int = 300,
    env: dict[str, str] | None = None,
) -> RunResult:
    # build + one execute, for callers that need a single run
    with tempfile.TemporaryDirectory() as out:
        out_dir = Path(out)
        b = build(source_dir, main_file, sanitizer, out_dir, compile_timeout_s)
        if b.sandbox_failed or not b.compiled:
            return RunResult(
                compiled=False,
                exit_code=None,
                output=b.output,
                timed_out=False,
                out_of_memory=False,
                seconds=b.seconds,
                sandbox_failed=b.sandbox_failed,
            )
        r = execute(out_dir, timeout_s, env)
        return replace(r, output=b.output + r.output, seconds=b.seconds + r.seconds)


def _docker(
    mounts: list[str], env: dict[str, str] | None, script: str, timeout_s: int
) -> tuple[int | None, str, float]:
    # returns (exit code, output, seconds). Exit code is None if the container never answered.
    name = f"cbb-{uuid.uuid4().hex[:12]}"

    mount_flags = []
    for m in mounts:
        mount_flags += ["-v", m]
    env_flags = []
    for key, value in (env or {}).items():
        env_flags += ["-e", f"{key}={value}"]

    # fmt: off
    cmd = [
        "docker", "run", "--rm", "--name", name,
        "--network", "none",
        "--cpus=1", "--memory", "1g", "--memory-swap", "1g", "--pids-limit", "256",
        "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
        "--read-only", "--tmpfs", "/tmp:exec,size=256m",
        "--security-opt", f"seccomp={SECCOMP_PROFILE}",
        *mount_flags,
        *env_flags,
        IMAGE,
        "bash", "-c", script,
    ]
    # fmt: on

    start = time.monotonic()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
    except subprocess.TimeoutExpired as e:
        subprocess.run(["docker", "kill", name], capture_output=True)
        return None, _text(e.stdout) + _text(e.stderr), time.monotonic() - start
    return proc.returncode, proc.stdout + proc.stderr, time.monotonic() - start


def _text(x: str | bytes | None) -> str:
    if x is None:
        return ""
    return x.decode(errors="replace") if isinstance(x, bytes) else x

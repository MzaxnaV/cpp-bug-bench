#!/usr/bin/env bash
# Checks the grading image: each sanitizer must fire on its known bug,
# and nothing may fire on clean code.
# Usage: ./check-image.sh            (uses image cbb-grader)
#        IMAGE=cbb-grader:clang21 ./check-image.sh
set -u

IMAGE="${IMAGE:-cbb-grader}"
HERE="$(cd "$(dirname "$0")" && pwd)"                                   # folder with the .cpp files
SECCOMP="${SECCOMP:-$HERE/../seccomp.json}"                             # docker/README.md
COMPILE_FAILED=100                                                      # custom code to distinguish from sanitizer exit
failures=0

# check <label> <file> <clang sanitizer flags> <expected exit code> <text expected in output, or "">
check() {
  local label=$1 file=$2 flags=$3 want_code=$4 want_text=$5
  local out code

  out=$(docker run --rm --network none --security-opt seccomp="$SECCOMP" -v "$HERE":/src:ro "$IMAGE" bash -c "
    clang++-21 -std=c++20 -g $flags /src/$file -o /tmp/t || exit $COMPILE_FAILED
    /tmp/t" 2>&1)
  code=$?

  if [[ $code -eq $COMPILE_FAILED ]]; then
    echo "FAIL  $label: did not compile"
  elif [[ $code -ne $want_code ]]; then
    echo "FAIL  $label: exit $code, expected $want_code"
  elif [[ -n $want_text && $out != *"$want_text"* ]]; then
    echo "FAIL  $label: output lacks \"$want_text\""
  elif [[ -z $want_text && $out == *Sanitizer* ]]; then
    echo "FAIL  $label: a sanitizer reported on clean code"
  else
    echo "ok    $label (exit $code)"
    return
  fi
  failures=$((failures + 1))
  echo "$out" | sed 's/^/      | /'
}

check "ASan  heap overflow"   bug.cpp   "-fsanitize=address"                              1  "AddressSanitizer: heap-buffer-overflow"
check "UBSan int overflow"    ub.cpp    "-fsanitize=undefined -fno-sanitize-recover=all"  1  "runtime error: signed integer overflow"
check "TSan  data race"       race.cpp  "-fsanitize=thread"                               66 "ThreadSanitizer: data race"
check "clean ASan+UBSan"      clean.cpp "-fsanitize=address,undefined -fno-sanitize-recover=all" 0 ""

echo
if [[ $failures -eq 0 ]]; then echo "all checks passed"; else echo "$failures check(s) failed"; exit 1; fi

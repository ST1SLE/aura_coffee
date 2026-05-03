#!/usr/bin/env sh
# Run the package Vitest suite and fail if it writes anything to stderr.

set -eu

stdout_file="$(mktemp)"
stderr_file="$(mktemp)"

cleanup() {
  rm -f "$stdout_file" "$stderr_file"
}
trap cleanup EXIT

if ! npm run test -- "$@" >"$stdout_file" 2>"$stderr_file"; then
  cat "$stdout_file"
  cat "$stderr_file" >&2
  exit 1
fi

cat "$stdout_file"

if [ -s "$stderr_file" ]; then
  echo "error: frontend test suite wrote to stderr" >&2
  cat "$stderr_file" >&2
  exit 1
fi

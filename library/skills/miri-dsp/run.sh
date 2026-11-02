#!/usr/bin/env bash
# miri-dsp: run cargo +nightly miri test against a Rust DSP crate.
# Usage: run.sh <crate-path> [--disable-isolation]
#   --disable-isolation (or MIRI_DSP_DISABLE_ISOLATION=1): let tests read the real
#   clock / OS RNG / env / filesystem. Off by default — isolation keeps runs
#   deterministic and catches tests that depend on host state.

set -uo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: run.sh <crate-path> [--disable-isolation]"
  exit 1
fi

CRATE_DIR="$1"
shift
DISABLE_ISOLATION="${MIRI_DSP_DISABLE_ISOLATION:-0}"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --disable-isolation) DISABLE_ISOLATION=1; shift ;;
    *) echo "ERROR  unknown arg: $1"; exit 1 ;;
  esac
done

if [[ ! -f "$CRATE_DIR/Cargo.toml" ]]; then
  echo "ERROR  Cargo.toml not found at $CRATE_DIR/Cargo.toml"
  exit 1
fi

echo "=== Miri DSP: $CRATE_DIR ==="
echo ""

# ---------------------------------------------------------------------------
# Toolchain check
# ---------------------------------------------------------------------------
if ! rustup toolchain list 2>/dev/null | grep -q '^nightly'; then
  echo "FAIL   TOOLCHAIN     nightly not installed — install: rustup toolchain install nightly"
  exit 1
fi
if ! rustup +nightly component list --installed 2>/dev/null | grep -q '^miri'; then
  echo "FAIL   TOOLCHAIN     miri component not installed — install: rustup +nightly component add miri"
  exit 1
fi
echo "PASS   TOOLCHAIN     nightly + miri installed"
echo ""

# ---------------------------------------------------------------------------
# Run miri
# ---------------------------------------------------------------------------
echo "INFO   MIRI          running cargo +nightly miri test..."
echo ""

# MIRIFLAGS:
#   -Zmiri-strict-provenance: stricter pointer-provenance rules — catches more UB
#   -Zmiri-disable-isolation: only when opted in (see usage) — allows host clock/RNG/fs access
EXTRA_FLAGS="-Zmiri-strict-provenance"
if [[ "$DISABLE_ISOLATION" == "1" ]]; then
  EXTRA_FLAGS="$EXTRA_FLAGS -Zmiri-disable-isolation"
  echo "INFO   MIRI          isolation disabled (host clock/RNG/fs visible to tests)"
fi
export MIRIFLAGS="${MIRIFLAGS:-} $EXTRA_FLAGS"

if (cd "$CRATE_DIR" && cargo +nightly miri test --no-fail-fast) 2>&1 | sed 's/^/         /'; then
  echo ""
  echo "PASS   MIRI          all tests passed under Miri"
  exit 0
else
  echo ""
  echo "FAIL   MIRI          one or more tests reported UB or failed under Miri"
  exit 1
fi

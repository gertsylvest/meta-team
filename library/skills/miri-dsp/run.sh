#!/usr/bin/env bash
# miri-dsp: run cargo +nightly miri test against a Rust DSP crate.
# Usage: run.sh <crate-path>

set -uo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: run.sh <crate-path>"
  exit 1
fi

CRATE_DIR="$1"

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
#   -Zmiri-disable-isolation: allow time/RNG syscalls; fine for DSP tests that use Instant or PRNGs
#   -Zmiri-strict-provenance: stricter aliasing rules — catches more UB
export MIRIFLAGS="${MIRIFLAGS:-} -Zmiri-disable-isolation -Zmiri-strict-provenance"

if (cd "$CRATE_DIR" && cargo +nightly miri test --no-fail-fast) 2>&1 | sed 's/^/         /'; then
  echo ""
  echo "PASS   MIRI          all tests passed under Miri"
  exit 0
else
  echo ""
  echo "FAIL   MIRI          one or more tests reported UB or failed under Miri"
  exit 1
fi

#!/usr/bin/env bash
# rust-rt-audit: verify a Rust DSP crate respects real-time-safety rules.
# Usage: audit.sh <crate-path>

set -uo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: audit.sh <crate-path>"
  exit 1
fi

CRATE_DIR="$1"
CARGO_TOML="$CRATE_DIR/Cargo.toml"
LIB_RS="$CRATE_DIR/src/lib.rs"

if [[ ! -f "$CARGO_TOML" ]]; then
  echo "ERROR  Cargo.toml not found at $CARGO_TOML"
  exit 1
fi

echo "=== Rust RT Audit: $CRATE_DIR ==="
echo ""

FAIL=0

# ---------------------------------------------------------------------------
# #![no_std]
# ---------------------------------------------------------------------------
if [[ -f "$LIB_RS" ]] && grep -qE '^[[:space:]]*#![[:space:]]*\[[[:space:]]*no_std[[:space:]]*\]' "$LIB_RS"; then
  echo "PASS   NO_STD        #![no_std] declared in src/lib.rs"
else
  echo "FAIL   NO_STD        #![no_std] not found in src/lib.rs"
  FAIL=1
fi
echo ""

# ---------------------------------------------------------------------------
# No alloc dependency (no `extern crate alloc;` in source, no alloc in deps)
# ---------------------------------------------------------------------------
ALLOC_SRC=$(grep -RE '^[[:space:]]*extern[[:space:]]+crate[[:space:]]+alloc[[:space:]]*;' "$CRATE_DIR/src" 2>/dev/null || true)
ALLOC_DEP=$(grep -E '^[[:space:]]*alloc[[:space:]]*=' "$CARGO_TOML" 2>/dev/null || true)
if [[ -z "$ALLOC_SRC" && -z "$ALLOC_DEP" ]]; then
  echo "PASS   NO_ALLOC_DEP  no extern crate alloc; no alloc dependency"
else
  echo "FAIL   NO_ALLOC_DEP  alloc found:"
  [[ -n "$ALLOC_SRC" ]] && echo "$ALLOC_SRC" | sed 's/^/         /'
  [[ -n "$ALLOC_DEP" ]] && echo "$ALLOC_DEP" | sed 's/^/         /'
  FAIL=1
fi
echo ""

# ---------------------------------------------------------------------------
# panic = "abort" in release profile
# ---------------------------------------------------------------------------
if grep -E '^[[:space:]]*panic[[:space:]]*=[[:space:]]*"abort"' "$CARGO_TOML" >/dev/null 2>&1; then
  echo "PASS   PANIC_ABORT   panic = \"abort\" declared"
else
  # Check workspace root too
  WORKSPACE_TOML=""
  PARENT="$CRATE_DIR"
  while [[ "$PARENT" != "/" && "$PARENT" != "." ]]; do
    PARENT=$(dirname "$PARENT")
    if [[ -f "$PARENT/Cargo.toml" ]] && grep -q '\[workspace\]' "$PARENT/Cargo.toml" 2>/dev/null; then
      WORKSPACE_TOML="$PARENT/Cargo.toml"
      break
    fi
  done
  if [[ -n "$WORKSPACE_TOML" ]] && grep -E '^[[:space:]]*panic[[:space:]]*=[[:space:]]*"abort"' "$WORKSPACE_TOML" >/dev/null 2>&1; then
    echo "PASS   PANIC_ABORT   panic = \"abort\" inherited from workspace ($WORKSPACE_TOML)"
  else
    echo "FAIL   PANIC_ABORT   panic = \"abort\" not found in this crate or workspace root"
    FAIL=1
  fi
fi
echo ""

# ---------------------------------------------------------------------------
# Clippy: panic/alloc-detecting lints
# ---------------------------------------------------------------------------
if command -v cargo-clippy &>/dev/null || cargo clippy --version &>/dev/null; then
  echo "INFO   CLIPPY        running curated panic/alloc lints..."
  CLIPPY_OUT=$(
    cargo clippy --manifest-path "$CARGO_TOML" --no-deps --quiet -- \
      -W clippy::unwrap_used \
      -W clippy::expect_used \
      -W clippy::panic \
      -W clippy::indexing_slicing \
      -W clippy::integer_division \
      -W clippy::arithmetic_side_effects \
      2>&1 || true
  )
  # Count diagnostics only — not cargo's per-crate summary lines
  # ("warning: `foo` (lib) generated N warnings", "error: could not compile ...").
  HITS=$(echo "$CLIPPY_OUT" | grep -E '^(warning|error)(\[[^]]*\])?:' \
    | grep -vE 'generated [0-9]+ warnings?|could not compile|aborting due to' \
    | wc -l | tr -d ' ')
  if [[ "$HITS" == "0" ]]; then
    echo "PASS   CLIPPY        no panic/alloc lint hits"
  else
    echo "FAIL   CLIPPY        $HITS lint hit(s):"
    echo "$CLIPPY_OUT" | sed 's/^/         /'
    FAIL=1
  fi
else
  echo "SKIP   CLIPPY        clippy not installed (rustup component add clippy)"
fi
echo ""

# ---------------------------------------------------------------------------
# Hot-path grep: banned constructs in src/
# ---------------------------------------------------------------------------
BANNED='Vec::|Box::|String::|format!\(|\.to_vec\(\)|\.collect::<Vec|Mutex::|RwLock::|RefCell::|println!|eprintln!|dbg!\('
HITS=$(grep -RnE "$BANNED" "$CRATE_DIR/src" 2>/dev/null || true)
if [[ -z "$HITS" ]]; then
  echo "PASS   HOT_PATH_GREP no banned heap/blocking constructs in src/"
else
  echo "FAIL   HOT_PATH_GREP banned construct hits:"
  echo "$HITS" | sed 's/^/         /'
  FAIL=1
fi
echo ""

# ---------------------------------------------------------------------------
# LLVM-IR allocator scan
# ---------------------------------------------------------------------------
# Emit this crate's IR to a fresh temp file, so stale .ll files from earlier
# builds (or other crates) in target/ can never be scanned by mistake.
echo "INFO   LLVM_IR_ALLOC building release LLVM-IR..."
IR_DIR=$(mktemp -d)
IR_FILE="$IR_DIR/crate.ll"
if cargo rustc --manifest-path "$CARGO_TOML" --lib --release --quiet -- --emit=llvm-ir="$IR_FILE" 2>/dev/null; then
  if [[ ! -s "$IR_FILE" ]]; then
    echo "SKIP   LLVM_IR_ALLOC no IR produced — check that the crate has a library target"
  else
    ALLOC_HITS=$(grep -nE '@__rust_(alloc|realloc|dealloc|alloc_zeroed)([^A-Za-z0-9_]|$)' "$IR_FILE" 2>/dev/null | head -n 20 || true)
    if [[ -z "$ALLOC_HITS" ]]; then
      echo "PASS   LLVM_IR_ALLOC no allocator symbols in this crate's release IR"
    else
      echo "FAIL   LLVM_IR_ALLOC allocator symbols present in release IR (first 20 lines):"
      echo "$ALLOC_HITS" | sed 's/^/         /'
      FAIL=1
    fi
  fi
else
  echo "SKIP   LLVM_IR_ALLOC cargo rustc --emit=llvm-ir failed"
fi
rm -rf "$IR_DIR"
echo ""

echo "=== Audit complete ==="
exit $FAIL

#!/usr/bin/env bash
# wasm-pack-build: opinionated Rust→WASM build with SIMD, wasm-opt, and module inspection.
# Usage: build.sh <crate-path> [--dev]

set -uo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: build.sh <crate-path> [--dev]"
  exit 1
fi

CRATE_DIR="$1"
MODE="release"
WASM_PACK_MODE="--release"
if [[ "${2:-}" == "--dev" ]]; then
  MODE="dev"
  WASM_PACK_MODE="--dev"
fi

if [[ ! -f "$CRATE_DIR/Cargo.toml" ]]; then
  echo "ERROR  Cargo.toml not found at $CRATE_DIR/Cargo.toml"
  exit 1
fi

echo "=== wasm-pack Build: $CRATE_DIR ($MODE) ==="
echo ""

# ---------------------------------------------------------------------------
# Prerequisites
# ---------------------------------------------------------------------------
PREREQ_FAIL=0
if ! command -v wasm-pack &>/dev/null; then
  echo "FAIL   PREREQ        wasm-pack not found — install: cargo install wasm-pack"
  PREREQ_FAIL=1
fi
if ! command -v wasm-opt &>/dev/null; then
  echo "FAIL   PREREQ        wasm-opt not found — install: brew install binaryen"
  PREREQ_FAIL=1
fi
if ! rustup target list --installed 2>/dev/null | grep -q wasm32-unknown-unknown; then
  echo "FAIL   PREREQ        wasm32-unknown-unknown target not installed — install: rustup target add wasm32-unknown-unknown"
  PREREQ_FAIL=1
fi
if [[ $PREREQ_FAIL -eq 0 ]]; then
  echo "PASS   PREREQ        wasm-pack, wasm-opt, wasm32 target all present"
fi
echo ""
[[ $PREREQ_FAIL -ne 0 ]] && exit 1

# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------
echo "INFO   BUILD         wasm-pack build --target web $WASM_PACK_MODE"
export RUSTFLAGS="${RUSTFLAGS:-} -C target-feature=+simd128"
if (cd "$CRATE_DIR" && wasm-pack build --target web $WASM_PACK_MODE) 2>&1 | sed 's/^/         /'; then
  echo "PASS   BUILD         wasm-pack succeeded"
else
  echo "FAIL   BUILD         wasm-pack failed"
  exit 1
fi
echo ""

# Locate the output .wasm
PKG_DIR="$CRATE_DIR/pkg"
WASM_FILE=$(find "$PKG_DIR" -maxdepth 1 -name '*_bg.wasm' | head -n1)
if [[ -z "$WASM_FILE" ]]; then
  echo "FAIL   BUILD         no *_bg.wasm produced in $PKG_DIR"
  exit 1
fi

# ---------------------------------------------------------------------------
# wasm-opt post-pass (release only)
# ---------------------------------------------------------------------------
if [[ "$MODE" == "release" ]]; then
  SIZE_BEFORE=$(wc -c < "$WASM_FILE" | tr -d ' ')
  if wasm-opt -O3 --enable-simd "$WASM_FILE" -o "$WASM_FILE" 2>&1 | sed 's/^/         /'; then
    SIZE_AFTER=$(wc -c < "$WASM_FILE" | tr -d ' ')
    DELTA=$((SIZE_BEFORE - SIZE_AFTER))
    PCT=$(awk "BEGIN { printf \"%.1f\", ($DELTA * 100.0) / $SIZE_BEFORE }")
    echo "PASS   OPTIMISE      wasm-opt: $SIZE_BEFORE → $SIZE_AFTER bytes (-${PCT}%)"
  else
    echo "FAIL   OPTIMISE      wasm-opt failed"
    exit 1
  fi
else
  echo "SKIP   OPTIMISE      dev build — wasm-opt not applied"
fi
echo ""

# ---------------------------------------------------------------------------
# Module inspection (calls into the sibling wasm-module-inspect skill)
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INSPECT_SCRIPT="$SCRIPT_DIR/../wasm-module-inspect/inspect.sh"
if [[ -f "$INSPECT_SCRIPT" ]]; then
  echo "INFO   INSPECT       running wasm-module-inspect on output..."
  echo ""
  bash "$INSPECT_SCRIPT" "$WASM_FILE"
else
  echo "SKIP   INSPECT       wasm-module-inspect skill not found at $INSPECT_SCRIPT"
fi

echo ""
echo "=== Build complete: $WASM_FILE ==="

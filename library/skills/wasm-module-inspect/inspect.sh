#!/usr/bin/env bash
# wasm-module-inspect: inspect a compiled .wasm binary
# Requires: wabt (wasm-validate, wasm2wat); wasm-opt (Binaryen) is optional.

set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: inspect.sh <module.wasm>"
  exit 1
fi

WASM_FILE="$1"

if [[ ! -f "$WASM_FILE" ]]; then
  echo "ERROR  file not found: $WASM_FILE"
  exit 1
fi

echo "=== WASM Module Inspection: $(basename "$WASM_FILE") ==="
echo ""

# ---------------------------------------------------------------------------
# File size
# ---------------------------------------------------------------------------
SIZE=$(wc -c < "$WASM_FILE" | tr -d ' ')
SIZE_KB=$(awk "BEGIN { printf \"%.1f\", $SIZE / 1024 }")
echo "INFO   SIZE        ${SIZE} bytes (${SIZE_KB} KB)"
echo ""

# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
if command -v wasm-validate &>/dev/null; then
  if wasm-validate "$WASM_FILE" 2>&1; then
    echo "PASS   VALID       module passes wasm-validate"
  else
    echo "FAIL   VALID       module failed wasm-validate"
    exit 1
  fi
else
  echo "SKIP   VALID       wasm-validate not found — install wabt"
fi
echo ""

# ---------------------------------------------------------------------------
# Exports, imports, SIMD, threading (via wasm2wat disassembly)
# ---------------------------------------------------------------------------
if command -v wasm2wat &>/dev/null; then
  WAT=$(wasm2wat "$WASM_FILE" 2>/dev/null)

  echo "INFO   EXPORTS"
  EXPORTS=$(echo "$WAT" | grep -E '^\s*\(export' | sed 's/^[[:space:]]*/         /' || true)
  if [[ -n "$EXPORTS" ]]; then
    echo "$EXPORTS"
  else
    echo "         (none)"
  fi
  echo ""

  echo "INFO   IMPORTS"
  IMPORTS=$(echo "$WAT" | grep -E '^\s*\(import' | sed 's/^[[:space:]]*/         /' || true)
  if [[ -n "$IMPORTS" ]]; then
    echo "$IMPORTS"
  else
    echo "         (none)"
  fi
  echo ""

  # SIMD: v128 type or v128 instructions
  if echo "$WAT" | grep -q 'v128'; then
    echo "INFO   SIMD        v128 opcodes present — compiled with -msimd128"
  else
    echo "INFO   SIMD        no v128 opcodes detected — SIMD not enabled"
  fi
  echo ""

  # Threading: atomic instructions require SharedArrayBuffer
  if echo "$WAT" | grep -q 'atomic'; then
    echo "INFO   THREADS     atomic instructions present — requires SharedArrayBuffer (COOP/COEP headers)"
  else
    echo "INFO   THREADS     no atomic instructions — single-threaded build"
  fi
else
  echo "SKIP   EXPORTS/IMPORTS/SIMD/THREADS  wasm2wat not found — install wabt"
fi
echo ""

# ---------------------------------------------------------------------------
# Feature report via wasm-opt (Binaryen) — optional
# ---------------------------------------------------------------------------
if command -v wasm-opt &>/dev/null; then
  echo "INFO   FEATURES (wasm-opt --print-features)"
  wasm-opt --print-features "$WASM_FILE" 2>&1 | sed 's/^/         /' || true
else
  echo "SKIP   FEATURES    wasm-opt not found — install binaryen for feature report"
fi

echo ""
echo "Done."

#!/usr/bin/env bash
# cbindgen-verify: regenerate a C header from a Rust crate and diff against the committed file.
# Usage: verify.sh <crate-path> <committed-header-path>

set -uo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: verify.sh <crate-path> <committed-header-path>"
  exit 1
fi

CRATE_DIR="$1"
COMMITTED_HEADER="$2"

if [[ ! -f "$CRATE_DIR/Cargo.toml" ]]; then
  echo "ERROR  Cargo.toml not found at $CRATE_DIR/Cargo.toml"
  exit 1
fi
if [[ ! -f "$CRATE_DIR/cbindgen.toml" ]]; then
  echo "ERROR  cbindgen.toml not found at $CRATE_DIR/cbindgen.toml"
  exit 1
fi
if [[ ! -f "$COMMITTED_HEADER" ]]; then
  echo "ERROR  committed header not found at $COMMITTED_HEADER"
  exit 1
fi
if ! command -v cbindgen &>/dev/null; then
  echo "ERROR  cbindgen not installed — run: cargo install --force cbindgen"
  exit 1
fi

echo "=== cbindgen Verify: $CRATE_DIR vs $COMMITTED_HEADER ==="
echo ""

CRATE_NAME=$(grep -m1 -E '^\s*name\s*=' "$CRATE_DIR/Cargo.toml" | sed -E 's/.*=\s*"([^"]+)".*/\1/')
GENERATED=$(mktemp)

if cbindgen --config "$CRATE_DIR/cbindgen.toml" --crate "$CRATE_NAME" --output "$GENERATED" --quiet 2>/dev/null; then
  echo "PASS   CBINDGEN      header regenerated for crate '$CRATE_NAME'"
else
  echo "FAIL   CBINDGEN      cbindgen failed for crate '$CRATE_NAME'"
  cbindgen --config "$CRATE_DIR/cbindgen.toml" --crate "$CRATE_NAME" --output "$GENERATED" 2>&1 | sed 's/^/         /'
  rm -f "$GENERATED"
  exit 1
fi
echo ""

if diff -u "$COMMITTED_HEADER" "$GENERATED" > /tmp/cbindgen-diff.$$; then
  echo "PASS   DIFF          committed header matches regenerated output"
  rm -f "$GENERATED" /tmp/cbindgen-diff.$$
  exit 0
else
  echo "FAIL   DIFF          committed header is out of date:"
  echo ""
  sed 's/^/         /' /tmp/cbindgen-diff.$$
  echo ""
  echo "         To accept the changes:"
  echo "           cbindgen --config $CRATE_DIR/cbindgen.toml --crate $CRATE_NAME --output $COMMITTED_HEADER"
  rm -f "$GENERATED" /tmp/cbindgen-diff.$$
  exit 1
fi

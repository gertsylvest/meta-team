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

# Read `name` from the [package] table only — a [lib], [[bin]] or dependency
# table earlier in the file can also carry a `name =` key.
CRATE_NAME=$(awk '
  /^[[:space:]]*\[/ { in_pkg = ($0 ~ /^[[:space:]]*\[package\][[:space:]]*(#.*)?$/) ; next }
  in_pkg && /^[[:space:]]*name[[:space:]]*=/ {
    sub(/^[^=]*=[[:space:]]*"/, ""); sub(/".*$/, ""); print; exit
  }' "$CRATE_DIR/Cargo.toml")
if [[ -z "$CRATE_NAME" ]]; then
  echo "ERROR  no [package] name found in $CRATE_DIR/Cargo.toml"
  exit 1
fi
GENERATED=$(mktemp)
DIFF_OUT=$(mktemp)
trap 'rm -f "$GENERATED" "$DIFF_OUT"' EXIT

if cbindgen --config "$CRATE_DIR/cbindgen.toml" --crate "$CRATE_NAME" --output "$GENERATED" --quiet "$CRATE_DIR" 2>/dev/null; then
  echo "PASS   CBINDGEN      header regenerated for crate '$CRATE_NAME'"
else
  echo "FAIL   CBINDGEN      cbindgen failed for crate '$CRATE_NAME'"
  cbindgen --config "$CRATE_DIR/cbindgen.toml" --crate "$CRATE_NAME" --output "$GENERATED" "$CRATE_DIR" 2>&1 | sed 's/^/         /'
  exit 1
fi
echo ""

if diff -u "$COMMITTED_HEADER" "$GENERATED" > "$DIFF_OUT"; then
  echo "PASS   DIFF          committed header matches regenerated output"
  exit 0
else
  echo "FAIL   DIFF          committed header is out of date:"
  echo ""
  sed 's/^/         /' "$DIFF_OUT"
  echo ""
  echo "         To accept the changes:"
  echo "           cbindgen --config $CRATE_DIR/cbindgen.toml --crate $CRATE_NAME --output $COMMITTED_HEADER $CRATE_DIR"
  exit 1
fi

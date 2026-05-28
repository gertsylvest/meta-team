#!/usr/bin/env bash
# cargo-bench-rt: run a Criterion bench and assert against a checked-in baseline.
# Usage: bench.sh <crate-path> <bench-name> [--save-baseline] [--budget-pct N]

set -uo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: bench.sh <crate-path> <bench-name> [--save-baseline] [--budget-pct N]"
  exit 1
fi

CRATE_DIR="$1"
BENCH_NAME="$2"
shift 2

SAVE_BASELINE=0
BUDGET_PCT=5
while [[ $# -gt 0 ]]; do
  case "$1" in
    --save-baseline) SAVE_BASELINE=1; shift ;;
    --budget-pct) BUDGET_PCT="$2"; shift 2 ;;
    *) echo "ERROR  unknown arg: $1"; exit 1 ;;
  esac
done

if [[ ! -f "$CRATE_DIR/Cargo.toml" ]]; then
  echo "ERROR  Cargo.toml not found at $CRATE_DIR/Cargo.toml"
  exit 1
fi

BASELINE_NAME="rt-baseline"
COMMITTED_BASELINE_DIR="$CRATE_DIR/benches/baselines/$BENCH_NAME"
CRITERION_BASELINE_DIR="$CRATE_DIR/target/criterion/$BENCH_NAME/$BASELINE_NAME"

echo "=== cargo-bench-rt: $CRATE_DIR :: $BENCH_NAME ==="
echo ""

# ---------------------------------------------------------------------------
# If saving: just run --save-baseline and copy into the committed location
# ---------------------------------------------------------------------------
if [[ $SAVE_BASELINE -eq 1 ]]; then
  echo "INFO   BENCH         saving new baseline '$BASELINE_NAME'"
  if (cd "$CRATE_DIR" && cargo bench --bench "$BENCH_NAME" -- --save-baseline "$BASELINE_NAME") 2>&1 | sed 's/^/         /'; then
    mkdir -p "$COMMITTED_BASELINE_DIR"
    cp -R "$CRITERION_BASELINE_DIR/." "$COMMITTED_BASELINE_DIR/"
    echo ""
    echo "PASS   BENCH         baseline saved to $COMMITTED_BASELINE_DIR"
    echo "       Commit this directory so regressions are detected on every CI run."
    exit 0
  else
    echo ""
    echo "FAIL   BENCH         baseline run failed"
    exit 1
  fi
fi

# ---------------------------------------------------------------------------
# Regression mode: restore committed baseline, run with --baseline, parse delta
# ---------------------------------------------------------------------------
if [[ ! -d "$COMMITTED_BASELINE_DIR" ]]; then
  echo "FAIL   BUDGET        no committed baseline at $COMMITTED_BASELINE_DIR"
  echo "       Establish one first: bash bench.sh $CRATE_DIR $BENCH_NAME --save-baseline"
  exit 1
fi

mkdir -p "$CRITERION_BASELINE_DIR"
cp -R "$COMMITTED_BASELINE_DIR/." "$CRITERION_BASELINE_DIR/"

echo "INFO   BENCH         running against baseline '$BASELINE_NAME'..."
BENCH_OUT=$(cd "$CRATE_DIR" && cargo bench --bench "$BENCH_NAME" -- --baseline "$BASELINE_NAME" 2>&1) || {
  echo "$BENCH_OUT" | sed 's/^/         /'
  echo ""
  echo "FAIL   BENCH         bench run failed"
  exit 1
}
echo "$BENCH_OUT" | sed 's/^/         /'
echo ""

# Parse Criterion's "change: ... [+/- X%]" line. Criterion prints this when --baseline is set.
# Example: "                        change: [-0.5% +1.2% +2.8%] (p = 0.42 > 0.05)"
CHANGE_LINE=$(echo "$BENCH_OUT" | grep -E 'change:\s*\[' | head -n1 || true)
if [[ -z "$CHANGE_LINE" ]]; then
  echo "FAIL   BUDGET        could not parse Criterion change line — baseline may be incompatible"
  exit 1
fi

# Pull the middle (best estimate) percentage from "[lo% mid% hi%]"
MID_PCT=$(echo "$CHANGE_LINE" | sed -E 's/.*\[\s*[^ ]+\s+([+-]?[0-9]+\.[0-9]+)%.*/\1/')
if ! [[ "$MID_PCT" =~ ^[+-]?[0-9]+\.[0-9]+$ ]]; then
  echo "FAIL   BUDGET        could not extract regression percentage from: $CHANGE_LINE"
  exit 1
fi

# Compare against budget
REGRESSED=$(awk "BEGIN { print ($MID_PCT > $BUDGET_PCT) ? 1 : 0 }")
if [[ "$REGRESSED" -eq 1 ]]; then
  echo "FAIL   BUDGET        regression ${MID_PCT}% exceeds budget ${BUDGET_PCT}%"
  exit 1
else
  echo "PASS   BUDGET        change ${MID_PCT}% within budget ${BUDGET_PCT}%"
  exit 0
fi

#!/usr/bin/env bash
# faust-build: compile, audit, and verify a Faust DSP source file
set -euo pipefail

# ── Argument parsing ──────────────────────────────────────────────────────────

DSP_FILE=""
OUT_FILE=""
CLASS_NAME="mydsp"
FAUST_BIN="faust"
INCLUDE_PATHS=()
FAUST_ARCH=""
RUN_CLANG=0
EXPECTED_INPUTS=""
EXPECTED_OUTPUTS=""
FTZ=0

usage() {
    echo "Usage: build.sh <input.dsp> <output.c> [options]"
    echo ""
    echo "Options:"
    echo "  --cn NAME         Class name for -cn flag (default: mydsp)"
    echo "  -I PATH           Faust library include path (repeatable)"
    echo "  --faust BIN       Faust compiler binary (default: faust)"
    echo "  --faust-arch DIR  Faust architecture dir (for --clang; must contain faust/gui/CInterface.h)"
    echo "  --ftz N           Faust -ftz value (default: 0; use 0 for Faust 2.85.x)"
    echo "  --clang           Run clang -c -Wall on the generated C"
    echo "  --inputs N        Expected getNumInputs return value"
    echo "  --outputs N       Expected getNumOutputs return value"
    exit 1
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --cn)         CLASS_NAME="$2";           shift 2 ;;
        -I)           INCLUDE_PATHS+=("-I" "$2"); shift 2 ;;
        --faust)      FAUST_BIN="$2";             shift 2 ;;
        --faust-arch) FAUST_ARCH="$2";            shift 2 ;;
        --ftz)        FTZ="$2";                   shift 2 ;;
        --clang)      RUN_CLANG=1;                shift   ;;
        --inputs)     EXPECTED_INPUTS="$2";       shift 2 ;;
        --outputs)    EXPECTED_OUTPUTS="$2";      shift 2 ;;
        --help|-h)    usage ;;
        --*)          echo "Unknown option: $1"; usage ;;
        *)
            if   [[ -z "$DSP_FILE" ]]; then DSP_FILE="$1"
            elif [[ -z "$OUT_FILE" ]]; then OUT_FILE="$1"
            else echo "Unexpected argument: $1"; usage
            fi
            shift ;;
    esac
done

[[ -z "$DSP_FILE" || -z "$OUT_FILE" ]] && usage
[[ ! -f "$DSP_FILE" ]] && echo "ERROR: DSP file not found: $DSP_FILE" && exit 1

# ── Counters ──────────────────────────────────────────────────────────────────

PASS=0; FAIL=0; WARN=0

ok()   { echo "  [PASS] $*"; PASS=$((PASS + 1)); }
fail() { echo "  [FAIL] $*"; FAIL=$((FAIL + 1)); }
warn() { echo "  [WARN] $*"; WARN=$((WARN + 1)); }

# ── STEP 0: Parameter smoothing audit ────────────────────────────────────────

echo ""
echo "── STEP 0: Parameter smoothing audit ──────────────────────────────────"

# Heuristic: find slider/entry definitions that lack si.smoo or si.smooth on the same line.
# Does not catch multi-line smoothing — treat results as review prompts.
UNSMOOTHED=$(grep -nE '(hslider|vslider|nentry)\s*\(' "$DSP_FILE" \
    | grep -vE '(si\.smoo|si\.smooth)' || true)

if [[ -z "$UNSMOOTHED" ]]; then
    ok "No obvious unsmoothed parameters found"
else
    while IFS= read -r line; do
        warn "Possible unsmoothed parameter (check for si.smoo/si.smooth): $line"
    done <<< "$UNSMOOTHED"
    echo "  NOTE: Heuristic is per-line only. Smoothing on the next line is not detected."
fi

# ── STEP 1: Faust compilation ─────────────────────────────────────────────────

echo ""
echo "── STEP 1: Faust compilation ───────────────────────────────────────────"

mkdir -p "$(dirname "$OUT_FILE")"

CMD=("$FAUST_BIN" -lang c -cn "$CLASS_NAME" -single -ftz "$FTZ" \
     "${INCLUDE_PATHS[@]}" -o "$OUT_FILE" "$DSP_FILE")
echo "  Running: ${CMD[*]}"
echo ""

if "${CMD[@]}"; then
    ok "Faust compilation succeeded → $OUT_FILE"
else
    fail "Faust compilation failed"
    echo ""
    echo "RESULT: $PASS passed, $FAIL failed, $WARN warnings"
    exit 1
fi

# ── STEP 2: API surface verification ─────────────────────────────────────────

echo ""
echo "── STEP 2: API surface verification ───────────────────────────────────"

# 14 expected public function base names for any -cn value
BASE_NAMES=(
    "new"
    "delete"
    "metadata"
    "getSampleRate"
    "getNumInputs"
    "getNumOutputs"
    "classInit"
    "instanceResetUserInterface"
    "instanceClear"
    "instanceConstants"
    "instanceInit"
    "init"
    "buildUserInterface"
    "compute"
)

for base in "${BASE_NAMES[@]}"; do
    fn="${base}${CLASS_NAME}"
    if grep -q "$fn" "$OUT_FILE"; then
        ok "Found: $fn"
    else
        fail "Missing: $fn"
    fi
done

# FAUSTCLASS macro
if grep -qE "define\s+FAUSTCLASS\s+${CLASS_NAME}" "$OUT_FILE"; then
    ok "FAUSTCLASS macro: $CLASS_NAME"
else
    fail "FAUSTCLASS macro not found for $CLASS_NAME"
fi

# Optional I/O count checks
if [[ -n "$EXPECTED_INPUTS" ]]; then
    ACTUAL=$(grep -A4 "getNumInputs${CLASS_NAME}" "$OUT_FILE" \
        | grep -oE 'return [0-9]+' | grep -oE '[0-9]+' | head -1 || echo "?")
    if [[ "$ACTUAL" == "$EXPECTED_INPUTS" ]]; then
        ok "getNumInputs${CLASS_NAME} returns $ACTUAL"
    else
        fail "getNumInputs${CLASS_NAME}: expected $EXPECTED_INPUTS, got $ACTUAL"
    fi
fi

if [[ -n "$EXPECTED_OUTPUTS" ]]; then
    ACTUAL=$(grep -A4 "getNumOutputs${CLASS_NAME}" "$OUT_FILE" \
        | grep -oE 'return [0-9]+' | grep -oE '[0-9]+' | head -1 || echo "?")
    if [[ "$ACTUAL" == "$EXPECTED_OUTPUTS" ]]; then
        ok "getNumOutputs${CLASS_NAME} returns $ACTUAL"
    else
        fail "getNumOutputs${CLASS_NAME}: expected $EXPECTED_OUTPUTS, got $ACTUAL"
    fi
fi

# ── STEP 3: Clang compile (optional) ─────────────────────────────────────────

if [[ "$RUN_CLANG" -eq 1 ]]; then
    echo ""
    echo "── STEP 3: Clang compile ───────────────────────────────────────────────"

    if [[ -z "$FAUST_ARCH" ]]; then
        warn "Skipping clang: --faust-arch not provided (needed for -include faust/gui/CInterface.h)"
    else
        OBJ="${OUT_FILE%.c}.o"
        CLANG_CMD=(
            clang -std=c11 -O2 -Wall -Wextra
            -I "$FAUST_ARCH"
            -include faust/gui/CInterface.h
            -Wno-unused-parameter
            -c "$OUT_FILE"
            -o "$OBJ"
        )
        echo "  Running: ${CLANG_CMD[*]}"
        echo ""
        if "${CLANG_CMD[@]}"; then
            ok "clang -c -Wall succeeded → $OBJ"
        else
            fail "clang -c -Wall failed"
        fi
    fi
fi

# ── Summary ───────────────────────────────────────────────────────────────────

echo ""
echo "────────────────────────────────────────────────────────────────────────"
printf "RESULT: %d passed, %d failed, %d warnings\n" "$PASS" "$FAIL" "$WARN"

[[ "$FAIL" -gt 0 ]] && exit 1
exit 0

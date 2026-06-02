#!/usr/bin/env bash
# log-pattern-scan/scan.sh
# Usage: bash scan.sh <jsonl-file-or-project-path> [all|errors|loops|expensive|trialerror|summary]
#
# Scans Claude Code JSONL session transcripts for behavioral inefficiency patterns.
# Output is prefixed lines: ERROR, LOOP, REPEAT, EXPENSIVE-OUTPUT, EXPENSIVE-CONTEXT,
#                           CHURN, REPEAT-CMD, LONG SESSION, OK

set -uo pipefail

# ── Arguments ────────────────────────────────────────────────────────────────

INPUT="${1:-}"
SCAN="${2:-all}"

if [[ -z "$INPUT" ]]; then
  echo "Usage: bash scan.sh <jsonl-file-or-project-path> [all|errors|loops|expensive|trialerror|summary]" >&2
  exit 1
fi

# ── Resolve input to a list of JSONL files ───────────────────────────────────

JSONL_FILES=()

if [[ "$INPUT" == *.jsonl ]]; then
  JSONL_FILES=("$INPUT")
else
  # Treat as project root — encode path to match Claude's storage convention
  ENCODED=$(echo "$INPUT" | sed 's|^/||; s|/|-|g')
  JSONL_DIR="$HOME/.claude/projects/-$ENCODED"
  if [[ ! -d "$JSONL_DIR" ]]; then
    echo "No Claude project folder found at: $JSONL_DIR" >&2
    exit 1
  fi
  # Recurse so subagent sidechains (<session>/subagents/agent-*.jsonl, isSidechain:true)
  # are included. Orchestrator/main transcripts see only ~15% of tool activity; the rest
  # lives in sidechains. Scanning only the top level massively undercounts errors/loops.
  while IFS= read -r -d '' f; do
    JSONL_FILES+=("$f")
  done < <(find "$JSONL_DIR" -name "*.jsonl" -print0 | sort -z)
fi

if [[ ${#JSONL_FILES[@]} -eq 0 ]]; then
  echo "No JSONL files found." >&2
  exit 1
fi

# ── Scan functions ────────────────────────────────────────────────────────────

scan_summary() {
  local f="$1"
  echo "Total lines:                    $(wc -l < "$f" | tr -d ' ')"
  echo "Tool calls:                     $(jq -r '.message.content[]? | select(.type == "tool_use") | .name' "$f" 2>/dev/null | wc -l | tr -d ' ')"
  echo "Errors:                         $(jq '[.message.content[]? | select(.is_error == true)] | length' "$f" 2>/dev/null | paste -s -d+ - | bc 2>/dev/null || echo 0)"
  echo "Total input tokens (incl cache): $(jq '(.message.usage.input_tokens // 0) + (.message.usage.cache_creation_input_tokens // 0) + (.message.usage.cache_read_input_tokens // 0)' "$f" 2>/dev/null | paste -s -d+ - | bc 2>/dev/null || echo 0)"
  echo "Total output tokens:            $(jq '.message.usage.output_tokens // 0' "$f" 2>/dev/null | paste -s -d+ - | bc 2>/dev/null || echo 0)"
}

scan_errors() {
  local f="$1"
  local found=0
  while IFS= read -r line; do
    echo "$line"
    found=1
  done < <(jq -r '
    select(.message.content != null) |
    .message.content[]? |
    select(.type == "tool_result" and .is_error == true) |
    "ERROR — tool_use_id: \(.tool_use_id)\n  \(.content | if type == "array" then .[0].text else . end | gsub("\n";" ") | .[0:200])"
  ' "$f" 2>/dev/null)
  [[ $found -eq 0 ]] && echo "OK — no errors detected"
}

scan_loops() {
  local f="$1"
  local found=0

  # Consecutive same-tool calls (3+ in a row)
  while IFS= read -r line; do
    echo "LOOP — $line"
    found=1
  done < <(jq -r '.message.content[]? | select(.type == "tool_use") | .name' "$f" 2>/dev/null \
    | uniq -c | awk '$1 >= 3 {print $1 "x " $2}')

  # Same tool+input repeated anywhere in session (3+ times)
  while IFS= read -r line; do
    echo "REPEAT — $line"
    found=1
  done < <(jq -r '.message.content[]? | select(.type == "tool_use") | "\(.name)|\(.input | tostring | .[0:120])"' "$f" 2>/dev/null \
    | sort | uniq -c | sort -rn | awk '$1 >= 3 {print $0}')

  [[ $found -eq 0 ]] && echo "OK — no loop patterns detected"
}

scan_expensive() {
  local f="$1"
  local found=0

  # High output tokens per turn (verbose generation)
  while IFS= read -r line; do
    echo "$line"
    found=1
  done < <(jq -r '
    select(.message.usage != null) |
    (.message.usage.output_tokens // 0) as $out |
    select($out > 2000) |
    "EXPENSIVE-OUTPUT — \($out) output tokens | uuid: \(.uuid)"
  ' "$f" 2>/dev/null | sort -t' ' -k3 -rn)

  # High cache creation per turn (large new context loaded)
  while IFS= read -r line; do
    echo "$line"
    found=1
  done < <(jq -r '
    select(.message.usage != null) |
    (.message.usage.cache_creation_input_tokens // 0) as $new |
    select($new > 10000) |
    "EXPENSIVE-CONTEXT — \($new) new context tokens | uuid: \(.uuid)"
  ' "$f" 2>/dev/null | sort -t' ' -k3 -rn)

  [[ $found -eq 0 ]] && echo "OK — no expensive turns detected"
}

scan_trialerror() {
  local f="$1"
  local found=0

  # Repeated edits to the same file (3+)
  while IFS= read -r line; do
    echo "CHURN — $line"
    found=1
  done < <(jq -r '
    .message.content[]? |
    select(.type == "tool_use" and (.name == "Edit" or .name == "Write")) |
    .input.file_path // .input.path // "unknown"
  ' "$f" 2>/dev/null \
    | sort | uniq -c | sort -rn | awk '$1 >= 3 {print $1 "x edits on " $2}')

  # Repeated identical bash commands (3+)
  while IFS= read -r line; do
    echo "REPEAT-CMD — $line"
    found=1
  done < <(jq -r '
    .message.content[]? |
    select(.type == "tool_use" and .name == "Bash") |
    .input.command | .[0:100]
  ' "$f" 2>/dev/null \
    | sort | uniq -c | sort -rn | awk '$1 >= 3 {print $0}')

  # Long session (high message count = trial-and-error proxy)
  local count
  count=$(wc -l < "$f" | tr -d ' ')
  if [[ $count -gt 200 ]]; then
    echo "LONG SESSION — $count messages (trial-and-error risk)"
    found=1
  fi

  [[ $found -eq 0 ]] && echo "OK — no trial-and-error patterns detected"
}

# ── Main loop ─────────────────────────────────────────────────────────────────

JSONL_DIR="${JSONL_DIR:-}"
for FILE in "${JSONL_FILES[@]}"; do
  # Show the path relative to the project folder so sidechains
  # (subagents/agent-*.jsonl) are distinguishable from the main transcript.
  if [[ -n "$JSONL_DIR" && "$FILE" == "$JSONL_DIR"/* ]]; then
    DISPLAY="${FILE#"$JSONL_DIR"/}"
  else
    DISPLAY="$(basename "$FILE")"
  fi
  echo "=== $DISPLAY ==="

  case "$SCAN" in
    summary)                   scan_summary    "$FILE" ;;
    errors)                    scan_errors     "$FILE" ;;
    loops)                     scan_loops      "$FILE" ;;
    expensive)                 scan_expensive  "$FILE" ;;
    trialerror)                scan_trialerror "$FILE" ;;
    all)
      scan_summary    "$FILE"
      echo ""
      scan_errors     "$FILE"
      echo ""
      scan_loops      "$FILE"
      echo ""
      scan_expensive  "$FILE"
      echo ""
      scan_trialerror "$FILE"
      ;;
    *)
      echo "Unknown scan type: $SCAN. Use: all|errors|loops|expensive|trialerror|summary" >&2
      exit 1
      ;;
  esac

  echo ""
done

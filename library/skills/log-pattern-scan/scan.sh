#!/usr/bin/env bash
# log-pattern-scan/scan.sh — entry point kept for existing callers; the scan itself is scan.py.
# Usage: bash scan.sh <jsonl-file-or-project-path> [scan-type] [--since YYYY-MM-DD] [--session ID[,ID...]]
#                     [--from TS] [--until TS] [--include-main] [--patterns FILE]
exec python3 "$(dirname "$0")/scan.py" "$@"

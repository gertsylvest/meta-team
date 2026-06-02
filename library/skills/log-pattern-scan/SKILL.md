---
name: log-pattern-scan
description: Scan Claude Code JSONL session transcript files for behavioral patterns — loops, errors, expensive turns, trial-and-error signatures. Returns structured findings for the improvement-analyst agent.
allowed-tools: Bash
argument-hint: "<jsonl-file-or-project-path> [all|errors|loops|expensive|trialerror|summary]"
---

# Log Pattern Scan

Scan one or more Claude Code JSONL session transcript files for behavioral inefficiency patterns.

## Instructions

Arguments are in `$ARGUMENTS`:
- First arg: path to a `.jsonl` file, or a project root path (scans all sessions for that project)
- Second arg (optional): scan type — `all` (default), `errors`, `loops`, `expensive`, `trialerror`, `summary`

If no arguments are provided, ask the user before proceeding.

When given a project root, the scan recurses into subagent **sidechains**
(`<session>/subagents/agent-*.jsonl`, marked `isSidechain: true`) as well as the
top-level session transcripts. This matters: the orchestrator/main transcript records
only ~15% of tool activity — the bulk of tool calls, errors, and loops happen inside
subagents. Scanning only the top level can undercount errors by an order of magnitude.
Each finding is headed by its path relative to the project folder, so sidechain
findings are attributable to the agent that produced them.

### Run the scan

The scan script lives alongside this file. Run it directly:

```bash
bash "$(dirname "$0")/scan.sh" <first-arg> <second-arg>
```

### Scan types

| Type | What it detects |
|---|---|
| `summary` | Total lines, tool calls, errors, token totals per session |
| `errors` | Tool calls that returned `is_error: true` |
| `loops` | Same tool called 3+ times consecutively, or same tool+input repeated 3+ times across the session |
| `expensive` | Turns with >2000 output tokens (`EXPENSIVE-OUTPUT`) or >10000 new cache tokens (`EXPENSIVE-CONTEXT`) |
| `trialerror` | 3+ edits to the same file (`CHURN`), 3+ identical bash commands (`REPEAT-CMD`), sessions >200 messages (`LONG SESSION`) |
| `all` | All of the above |

### Output prefixes

Each finding is prefixed for easy parsing:

| Prefix | Meaning |
|---|---|
| `ERROR` | Failed tool call |
| `LOOP` | Consecutive same-tool repetition |
| `REPEAT` | Same tool+input repeated across session |
| `EXPENSIVE-OUTPUT` | High output token turn |
| `EXPENSIVE-CONTEXT` | Large new context loaded in one turn |
| `CHURN` | Repeated edits to same file |
| `REPEAT-CMD` | Repeated identical bash command |
| `LONG SESSION` | Session exceeds 200 messages |
| `OK` | No issues found for that scan type |

### Return to caller

Return the full script output. The improvement-analyst agent will interpret the findings and write suggestions to the project's self-improvement log.

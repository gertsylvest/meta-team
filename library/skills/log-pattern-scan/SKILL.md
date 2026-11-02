---
name: log-pattern-scan
description: Scan Claude Code JSONL session transcripts for outcome (merged PRs, cycle time, cost and agent time per unit), time use (working / waiting on jobs / dormant, operator wait, effective duration), test and check runs (failures, re-runs, possible duplicates, hung runs), token-cost drivers (context growth, subagent cost by type/model, cache health and avoidable cache-miss cost by cause, cost trend), long tool pauses and behavioral inefficiency. Returns prefixed findings for the improvement-analyst agent.
allowed-tools: Bash
argument-hint: "<jsonl-file-or-project-path> [outcome|time|tests|trend|cost|cache|agents|pauses|summary|errors|loops|expensive|trialerror|all] [--since YYYY-MM-DD] [--session ID[,ID...]] [--from TS] [--until TS] [--include-main] [--patterns FILE] [--bucket day|week] [--json] [--units N] [--repo OWNER/NAME[,...]] [--non-delivery REGEX] [--top N] [--transcripts-dir DIR]"
---

# Log Pattern Scan

Scan Claude Code JSONL session transcripts for what a window of work delivered and what it cost in
time and tokens, and for what drives that cost: waiting, test runs, cache misses, context growth,
behavioral waste.

## Instructions

Arguments are in `$ARGUMENTS`:
- First arg: path to a `.jsonl` file, or a project root path (scans all sessions for that project)
- Second arg (optional): scan type, default `all`
- `--since YYYY-MM-DD` (optional, project root only): only transcripts modified on or after that date
- `--session ID[,ID...]` (optional, project root only): only these main sessions and their
  subagents. IDs may be prefixes, e.g. the 8 characters `trend` prints
- `--from TS` / `--until TS` (optional): keep only transcript lines with a timestamp in
  `[from, until)`. `TS` is UTC, `YYYY-MM-DD` or `YYYY-MM-DDTHH:MM[:SS]`, with or without a trailing `Z`
- `--include-main` (optional, `pauses`): also count pauses in main sessions, not only subagents.
  Use it where the main session runs long operations itself (e.g. deploys)
- `--patterns FILE` (optional): project rules for classifying commands (see **Command patterns**).
  Default: `<project>/.claude/scan-patterns.tsv` when it exists
- `--bucket day|week` (optional, `trend`): one row per day or ISO week instead of per session. Use
  it for long-running sessions (one session spanning days gives a single row otherwise)
- `--json` (optional, `pauses` and `tests`): one JSON object per event instead of text, for
  drill-down. Its fields may change between versions
- `--units N` (optional, `outcome`): the number of delivered units in the window, when they are not
  merged PRs (e.g. change-log entries, releases)
- `--repo OWNER/NAME[,...]` (optional, `outcome`): the repos whose merged PRs count. Default: the
  repo of the project root, via `gh`
- `--top N` (optional, per-transcript scans such as `cost`, `errors`, `loops`): only the N most
  expensive transcripts in the window, most expensive first, each headed with its cost and agent type
- `--non-delivery REGEX` (optional, `outcome`): head-branch names of merged PRs that are not
  delivered work (e.g. bookkeeping PRs). Also settable in the pattern file
- `--transcripts-dir DIR` (optional, project root only): the folder holding Claude Code's
  per-project transcript folders, in place of `$CLAUDE_CONFIG_DIR/projects` (default
  `~/.claude/projects`). Use it for transcripts copied off another machine

### Scoping a window

A window is whatever period is being measured: a sprint, a week, a release. `--since` filters
**whole files by modification time**: a session that is still written to after the period ends, or
that spans two periods, is counted in full, so adjacent periods mix. To measure one period, use its
start and end times:

```bash
bash scan.sh <project> trend  --from 2025-03-03T09:00 --until 2025-03-14T17:30Z
bash scan.sh <project> pauses --session 1a2b3c4d --until 2025-03-14T17:30Z
```

`--from`/`--until` select turns by timestamp, so later work in the same session is excluded. Add
`--session` when another session (a parallel team member, an unrelated chat) ran in the same window.
Per-turn numbers (`turns`, `avg`, `peak`) are exact. With `--from`, `trend` labels the first context
`first-in-window` instead of `base`: mid-session, it is not the session's real baseline.

**Choosing the edges: adjacent windows must not overlap.** For a sprint: close = its close commit;
open = its plan-approval commit, or the previous sprint's close if that is later. Not the first
commit that mentions the sprint: work is often filed for the next sprint before the current one
closes, and a window opened there counts the overlap twice. Record which commits or times you used.
A `WINDOW-SPAN` line names each main session with turns on both sides of an edge. That
is normal when one session runs both periods, and it is exactly where an overlap would hide, so check
the adjacent window's edge whenever you see one.

If no arguments are provided, ask the user before proceeding.

When given a project root, the scan recurses into subagent **sidechains**
(`<session>/subagents/agent-*.jsonl`). This matters more for cost than for behavior: in multi-agent
sessions, subagents typically carry **65–95% of total cost**, and the main transcript shows only a
fraction of tool activity.

### Run the scan

```bash
bash .claude/skills/log-pattern-scan/scan.sh <first-arg> <scan-type> [options]
```

### Requirements

- **Python 3.8+**, standard library only.
- **`gh`** (GitHub CLI, authenticated) — **optional**, only for the `outcome` scan, which lists merged
  PRs with `gh pr list`. Without it, pass `--units N`; every other scan works without `gh`.

### Where transcripts are found

Given a project root, the script reads `<config>/projects/<slug>/`, where `<config>` is
`$CLAUDE_CONFIG_DIR` (default `~/.claude`) and `<slug>` is the absolute project path with **every
character that is not a letter or digit replaced by `-`** (so `/home/me/my_app.v2` →
`-home-me-my-app-v2`). That matches Claude Code's own naming. Slugs longer than 200 characters are
truncated by Claude Code and given a hash suffix; the script matches those by prefix.
`--transcripts-dir` overrides `<config>/projects`.

`scan.sh` runs `scan.py`. A project-wide scan reads each
transcript once and takes seconds; use `--since` or `--from` to bound very large projects.

## How cost is counted

Read this before interpreting any number.

1. **Deduplicated turns.** One API response is written as several JSONL lines repeating the same
   usage block. A turn is one (`message.id`, `requestId`) pair, counted once. Tool calls are read
   from assistant lines only, once per tool-use id: request-log lines repeat the conversation and
   would double-count them.
2. **`eq` = base-input-token equivalents.** Token classes are weighted by price relative to that
   model's base input. Output is weighted 5×, a 5-minute cache write 1.25×, a 1-hour cache write 2×,
   and a cache read 0.1× by default (0.05× for Opus 5.5 / Sonnet 5.5, 0.025× for Fable 5.1). The
   multipliers live in `prices.tsv` beside the script, with their source; re-check them when a new
   model family appears. `eq` compares classes and sessions on one axis. Across *different models* it is
   approximate, because base prices differ.
3. **Context size of a turn** = input + cache write + cache read: everything the model was sent.
   A long session costs roughly **turns × average context**, so average and peak context are the
   headline numbers, not any single expensive turn.
4. **Cache misses.** A turn is a **rebuild** when more than half of its cached context was written
   rather than read. The first turn of a transcript is an **agent start**: unavoidable, reported
   apart. Any other rebuild is an **avoidable miss** when the gap since the previous turn exceeded the
   cache lifetime (5 min, or 1 h when most of that write was a 1-hour write), or when the turn read
   back less than half of the previous turn's context (the prefix was lost: compaction, model or
   effort switch, MCP change). A rebuild after a short gap that kept its prefix is new content, not
   a miss. A miss's **excess cost** is its write cost minus what reading the same tokens would have
   cost. Its **cause** is what the gap was spent on: a tool run (classified WAIT / WATCH / other),
   a message that resumed a dormant agent, operator wait, a peer message, a background task or
   subagent notification, or compaction.
5. **Pauses** are tool calls lasting 5–60 min, timed from the call to its result (paired by
   tool-use id). Parallel calls issued in one turn count as one pause. With a 5-minute cache each
   pause costs a context rewrite; under a 1-hour cache it would be a hit.

The hit ratio by tokens is usually above 90% and says little on its own: cache writes can still be
half of the cost. Read the write share and the avoidable-miss share instead.

## How time is counted

6. **Time segments.** In each transcript, every gap between two consecutive entries goes to the
   entry that ends it. A model turn is **working**. A tool result takes its tool's class: a polling
   command, or a test, build or remote run, is **waiting on jobs**; a quick tool (read, edit,
   message) is **working**, or a **stall** when it took over 2 min (often a permission prompt); a
   synchronous subagent call is **dormant**. A message ends a **dormant** gap (a subagent resumed by
   its caller, a peer message, a background-task or subagent notification) or, in a main session,
   an **operator wait** when a human wrote it.
7. **Operator wait** counts only time with nothing in flight. While the main session's subagents
   were working or its background tasks were pending, it was not waiting for the operator: that
   time is "idle while subagents or background tasks work". A **blocking wait** is an operator wait
   that began with nothing in flight.
8. **Effective duration** = the window's calendar time minus the wall-clock union of operator
   waits: how long the work took, apart from waiting for the operator. **Agent time** = the sum of
   all transcripts' working, waiting-on-jobs and dormant segments in the window, so parallel agents
   add up. Operator wait is reported apart and is not part of agent time.

## How runs are counted (`tests`)

9. **A run** is a Bash call whose first test, check or build segment matches a test rule (see
   **Command patterns**). It starts at the call. It ends at the call's result; for a background run
   (`run_in_background`, or moved to the background after a timeout), at its task notification;
   for one started with `&`, at the last write of the log it redirects to, if that log still exists.
   A run with no readable end is **open** and left out of every duration, never counted as zero.
10. **Status**: a final `exit N` line in the output decides. Otherwise the tool's error flag, when it
    is the run's own exit code (the run is last, followed by `&&`, or piped with `pipefail`); else
    the output (failure counts, then fail/pass markers; lines about an *expected* red are ignored).
    Runs piped without `pipefail` and with no readable result are **unreadable**.
11. **Re-run**: the same normalized command in the same directory, after that command failed
    within 6 h. **Possible duplicate**: the same, after it *passed*, with no edit, commit, install or
    file write seen in that directory between. Approximate: transcripts do not show the commit a
    run tested, nor CI, so a local repeat of a CI run is not detected.
12. **Hung**: a background or killed run far longer than its kind normally takes (over 1 h and
    over 10× the kind's p95 when there are 20+ runs of it). It is counted at the kind's median, so
    one orphan cannot dominate the total; the removed time is reported.

## How outcome is counted

13. **Units** are merged PRs in the window (by merge time, via `gh pr list`), minus head branches
    matching a non-delivery rule. `--units N` replaces them where work is not delivered as PRs.
    When neither is available, `outcome` says so and reports per-window figures only. It does not
    fall back to counting closed tasks: tasks are split, reopened and closed in batches.
14. **Cycle time** = PR opened → merged, median and p90. **Per unit** = total eq, agent time and
    effective duration divided by units.

## Scan types

| Type | What it reports |
|---|---|
| `outcome` | Units delivered (merged PRs), cycle time, and total and per-unit cost, agent time and effective duration. **The headline: start here.** |
| `time` | Calendar and effective duration; agent time split into working / waiting on jobs / dormant / operator wait; what dormant time waited on; operator wait, longest, blocking waits; job time by kind |
| `tests` | Test, check and build runs by kind: time (summed and wall-clock), failures, unreadable and open runs, re-runs after a failure, possible duplicates, hung runs |
| `trend` | One line per main session including its subagents (or per day / week with `--bucket`): turns, baseline/avg/peak context, compactions, main vs subagent cost. The regression view for cost |
| `cache` | Whole scope: cache-write share of cost, hit ratio, 1h share; avoidable misses and their excess cost, split by cause and by agent type; agent starts apart |
| `agents` | Subagent cost grouped by agent type + model: runs, average turns, peak context, eq per turn, share of subagent cost |
| `pauses` | Subagent pauses of 5–60 min, grouped by what the agent was running: **WAIT** (polling for something to finish or appear), **WATCH** (a build, test or remote operation it needs to see) or **OTHER**, with the rule that matched. Answers "detach this, or give subagents a 1h cache?" |
| `cost` | Per transcript: cost split by token class, context growth, compaction events, cache health, the largest avoidable misses with their cause |
| `summary` | Per transcript: deduplicated turns, tool calls, errors, token classes, cost |
| `errors` | Tool calls that returned `is_error: true` |
| `loops` | Same tool 3+ times consecutively, or same tool+input 3+ times in a session |
| `expensive` | Turns with >2000 output tokens |
| `trialerror` | 3+ edits to one file, 3+ identical Bash commands, sessions >200 API turns |
| `all` | `cost` + behavioral scans per transcript, then `agents`, `pauses`, `cache`, `time` and `tests` |

## Output prefixes

| Prefix | Meaning |
|---|---|
| `WEIGHTS` | The price multipliers in effect, including the cache-read weight per model. Quote it with any cost figure: a different weight changes every `eq` |
| `RULES` | The cache-miss and pause rules in effect, and how many project command patterns were loaded |
| `WINDOW`, `WINDOW-SPAN` | The `--from`/`--until` window in effect, and each main session that also has turns outside it |
| `OUTCOME`, `OUTCOME-CYCLE`, `OUTCOME-TOTAL`, `OUTCOME-PER-UNIT` | Units and their source, cycle time, window totals, per-unit figures |
| `TIME`, `TIME-SPLIT`, `TIME-DORMANT`, `TIME-OPERATOR`, `TIME-JOBS` | Durations, the agent-time split, what dormant time waited on, operator wait, job time by kind |
| `TESTS`, `TESTS-RERUN`, `TESTS-DUP`, `TESTS-HUNG`, `TESTS-UNREADABLE`, `TESTS-LABEL`, `TESTS-NOTE` | Run totals, re-runs, possible duplicates (with examples), hung runs, unreadable results, per-kind rows, and what the scan cannot see |
| `TREND` | One session's (or day's / week's) cost profile (see `trend`) |
| `AGENT` | One agent-type+model group's cost profile |
| `COST` | Cost and its split: cache read / cache write / output / input |
| `CONTEXT` | Baseline (turn 1), average and peak context; flagged when peak > `CTX_WARN` (default 300k) |
| `COMPACT` | A compaction: manual or auto, tokens before → after |
| `CACHE` | Cache-write share of cost, hit ratio by tokens, 1h share of writes |
| `CACHE-MISS` | Avoidable misses: count, excess cost and share; agent starts apart. Per transcript, also the largest misses with gap and cause |
| `CACHE-MISS-CAUSE`, `CACHE-MISS-AGENT` | Avoidable miss cost by cause and by agent type (`cache` scan) |
| `PAUSE`, `PAUSE-WAIT/WATCH/OTHER`, `PAUSE-HINT` | Long pauses by cause and matched rule, with the cost of rebuilding context after each under a 5m cache, and a hint: detach, or consider a 1h cache |
| `ERROR`, `LOOP`, `REPEAT`, `EXPENSIVE-OUTPUT`, `CHURN`, `REPEAT-CMD`, `LONG SESSION` | Behavioral patterns |
| `OK` | Nothing found for that scan |

## Command patterns

Pauses, miss causes, time segments and test runs are classified by the command the agent ran. Each command is split into
shell segments (at `&&`, `||`, `;`, `|`, newlines); heredoc bodies are dropped, and wrappers such as
`cd x`, `VAR=1`, `timeout 600`, `nohup`, `bash`, `do` are stripped. Each rule is a regex matched at
the **start** of a segment, so `grep test log` is not a test run and `cat build/out.txt` is not a
build. A command is WAIT if any segment matches a WAIT rule, else WATCH if any matches WATCH.

The built-in rules are generic: `sleep`, `until` loops, `*wait-for*`, `*poll*`, `tail -f`, `pgrep`,
`gh run watch` (WAIT); build and test tools, containers, remote operations (`ssh`, `rsync`,
`terraform`, `kubectl`...), and any other script (WATCH). Test rules cover common runners by kind:
`unit` (npm/cargo/go/pytest/vitest/jest/node --test...), `e2e` (playwright, cypress), `lint`
(eslint, tsc, clippy, ruff...), `build` (npm run build, cargo build, make...), and `check-script`
(any script named like test, check, gate, lint, verify, smoke, spec). A long-running project script
with another name counts as watched work in `time` (`TIME-JOBS run: …`) but not as a test run: when
`TIME-JOBS` shows run time that `TESTS` does not, add `TEST` rules for those scripts. A project names its own tools
in `<project>/.claude/scan-patterns.tsv`, read before the built-ins, first match wins:

```text
label	class	regex
merge	WAIT	(\S*/)?wait-for-merge\.sh\b
load	WATCH	(\S*/)?load-test\.sh\b
precheck	TEST	(\S*/)?pre-merge-checks\.sh\b
help	IGNORE	.*\s--help(\s|$)
chore	NON-DELIVERY	^chore/
```

`class` is `WAIT`, `WATCH`, `TEST` (a test or check run of kind `label`; also WATCH for pauses),
`IGNORE` (the segment never classifies), or `NON-DELIVERY` (a regex on the head branch of merged
PRs that are not delivered work). The `RULES` line reports how
many project rules were loaded, and `PAUSE-*` lines name the rules that matched, so a wrong
classification can be traced to its rule.

## Tunables (environment variables)

Prices live in `prices.tsv` beside the script (with source and date). `CTX_WARN` (peak-context
flag, default 300000), `REBUILD_RATIO` / `PREFIX_LOST_RATIO` (cache-miss
rule, default 0.5 each), `MISS_MIN_WRITE` (ignore smaller rebuilds, default 0), `SCAN_PATTERNS`
(pattern file, like `--patterns`), `CR_TABLE` / `W_CR_DEFAULT` / `W_*` (price multipliers).
`CR_TABLE=` (empty) prices every model's cache read at `W_CR_DEFAULT`, e.g. to reproduce figures
from before the per-model weights. The former `WAIT_RE` / `WATCH_RE` / `BREAK_MIN_WRITE` are gone:
use a pattern file and the cache-miss rule.

## Return to caller

Return the full script output. The improvement-analyst agent interprets it and writes
recommendations to the project's self-improvement log.

The definitions above are a first cut and expected to change as they meet more projects. When a
figure is compared with another tool's, differences usually come from a definition (what counts
as a run, how its end is found, what counts as operator wait): name it rather than force a match.

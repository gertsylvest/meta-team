#!/usr/bin/env python3
"""log-pattern-scan: cost, cache, pause and behaviour scans over Claude Code session transcripts.

Usage: scan.py <jsonl-file-or-project-path> [scan-type] [--since YYYY-MM-DD] [--session ID[,ID...]]
               [--from TS] [--until TS] [--include-main] [--patterns FILE] [--bucket day|week]
               [--json] [--units N] [--repo OWNER/NAME[,...]] [--non-delivery REGEX] [--top N]
               [--transcripts-dir DIR]

Transcripts are read from <config>/projects/<project-slug>/, where <config> is $CLAUDE_CONFIG_DIR
(default ~/.claude), or from --transcripts-dir DIR in place of <config>/projects. The slug is the
absolute project path with every non-alphanumeric character replaced by "-" (Claude Code's own
rule); slugs longer than 200 characters are truncated and suffixed with a hash, matched by prefix.

Scan types:
  trend       one line per main session (+ its subagents): the regression view
  cost        per transcript: token classes, context growth, compaction, cache health and misses
  cache       whole scope: cache-write share, hit ratio, avoidable miss cost by cause and agent type
  agents      subagent cost grouped by agent type + model
  pauses      5-60 min tool calls by cause (waiting vs watching): detach, or a 1h cache?
  time        agent time: working / waiting on jobs / dormant; operator wait; effective duration
  tests       test, check and build runs: time, failures, re-runs, possible duplicates, hung runs
  outcome     delivered units (merged PRs), cycle time, cost and agent-hours per unit
  summary     per transcript totals
  errors | loops | expensive | trialerror   behavioural patterns
  all         cost + behavioural per transcript, then agents, pauses, cache, time and tests

Output is prefixed lines (WEIGHTS, WINDOW, TREND, COST, CONTEXT, CACHE, CACHE-MISS, PAUSE, AGENT, ...)
so the caller can grep them. Python 3.8+ standard library only.

Counting rules:
1. One API response is written as several transcript lines that repeat its usage block. A turn is
   one (message.id, requestId) pair; of its lines, the one with the most output tokens is kept.
2. Tool calls are read from assistant lines only, once per tool_use id. Request-log lines
   (api-request-blob) repeat the conversation and are ignored.
3. A tool call is paired with its result by tool_use id, not by position in the file.
4. Cost is in "eq" = base-input-token equivalents, each token class weighted by price (below).
5. Context of a turn = input + cache write + cache read: everything the model was sent.
"""

import collections
import datetime as dt
import json
import math
import os
import re
import subprocess
import sys

# ── Price multipliers relative to base input ─────────────────────────────────
# Read from prices.tsv beside this script (with its source and date); environment variables win.
# Re-check the file when a new model family appears; an unlisted model's read uses W_CR_DEFAULT.

def _load_prices():
    vals, cr = {}, []
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "prices.tsv"), encoding="utf-8") as fh:
            for line in fh:
                parts = line.split("#", 1)[0].split()
                if len(parts) < 2:
                    continue
                if parts[0].startswith("cr:"):
                    cr.append(f"{parts[0][3:]}={parts[1]}")
                else:
                    vals[parts[0]] = parts[1]
    except OSError:
        pass
    return vals, ",".join(cr)


_P, _CR = _load_prices()
W_IN = float(os.environ.get("W_IN", _P.get("in", "1")))
W_CW5 = float(os.environ.get("W_CW5", _P.get("cw5", "1.25")))     # cache write, 5-minute lifetime
W_CW1H = float(os.environ.get("W_CW1H", _P.get("cw1h", "2")))     # cache write, 1-hour lifetime
W_OUT = float(os.environ.get("W_OUT", _P.get("out", "5")))         # output, thinking included
# Cache read by model, matched as a prefix of message.model, first match wins.
# CR_TABLE= (empty) prices every model's read at W_CR_DEFAULT.
CR_TABLE = os.environ.get("CR_TABLE", _CR)
W_CR_DEFAULT = float(os.environ.get("W_CR_DEFAULT", _P.get("cr_default", "0.1")))

# ── Thresholds ───────────────────────────────────────────────────────────────
CTX_WARN = int(os.environ.get("CTX_WARN", "300000"))            # peak context worth flagging
LIFETIME_5M = 300
LIFETIME_1H = 3600
# A turn is a REBUILD when more than this share of its cached context was written, not read.
REBUILD_RATIO = float(os.environ.get("REBUILD_RATIO", "0.5"))
# A rebuild after a short gap is still a miss when it read back less than this share of the
# previous turn's context (the prefix was lost: compaction, model/effort switch, MCP change).
PREFIX_LOST_RATIO = float(os.environ.get("PREFIX_LOST_RATIO", "0.5"))
MISS_MIN_WRITE = int(os.environ.get("MISS_MIN_WRITE", "0"))     # ignore rebuilds smaller than this
PAUSE_MIN, PAUSE_MAX = 300, 3600
STALL_S = 120              # a quick tool (read, edit, message) taking longer than this is a stall
RERUN_WINDOW_S = 6 * 3600  # a run is a re-run when the same command failed within this time

USAGE = ("Usage: scan.sh <jsonl-file-or-project-path> "
         "[trend|cost|cache|agents|pauses|summary|errors|loops|expensive|trialerror|all] "
         "[--since YYYY-MM-DD] [--session ID[,ID...]] [--from TS] [--until TS] "
         "[--include-main] [--patterns FILE] [--bucket day|week] [--json] [--units N] "
         "[--repo OWNER/NAME[,...]] [--non-delivery REGEX] [--top N] [--transcripts-dir DIR]")

# ── Command classification for pauses ────────────────────────────────────────
# Each rule is matched from the START of a shell segment (a command between && || ; | or a
# newline), after wrappers such as `cd x`, `VAR=1`, `timeout 600`, `nohup`, `bash`, `do` are
# stripped. So `grep test log` is not a test run and `cat build/out.txt` is not a build.
# First matching rule wins: project rules (from --patterns or <project>/.claude/scan-patterns.tsv)
# come before these defaults. A command is WAIT if any segment is WAIT, else WATCH if any is WATCH.
#   WAIT  = the agent is polling for something to finish or appear: detach it.
#   WATCH = the agent runs a build, test or remote operation whose result it needs.
#   IGNORE = never classifies a segment (e.g. a project's own wrapper with a --help flag).
DEFAULT_RULES = [
    ("sleep", "WAIT", r"sleep\s+\d"),
    ("until-loop", "WAIT", r"until\b"),
    ("wait-script", "WAIT", r"(\S*/)?[\w.-]*wait-for[\w.-]*"),
    ("poll-script", "WAIT", r"(\S*/)?[\w.-]*poll[\w.-]*(\s|$)"),
    ("tail-follow", "WAIT", r"tail\b.*(\s-[a-zA-Z]*[fF]\b|\s--follow\b|\s--pid\b)"),
    ("pgrep", "WAIT", r"pgrep\b"),
    ("inotifywait", "WAIT", r"inotifywait\b"),
    ("gh-watch", "WAIT", r"gh\s+(run\s+watch|pr\s+checks\b.*--watch)"),
    ("build-tool", "WATCH",
     r"(cargo|make|cmake|ninja|meson|npm|pnpm|yarn|npx|bun|deno|node|tsc|go|mvn|gradle|mix|dotnet"
     r"|bazel|swift|xcodebuild|pytest|vitest|jest|playwright|tox|nox)\b"),
    ("python", "WATCH", r"python3?\s+(-m\s+\w|-c\b|-\s|-$)"),
    ("container", "WATCH", r"docker(\s+compose|-compose)?\s+(build|run|up|compose)\b|podman\s+(build|run)\b"),
    ("remote-op", "WATCH", r"(ssh|scp|rsync|ansible-playbook|terraform|kubectl|helm)\b"),
    # A script that runs 5+ minutes and is not a poll (WAIT rules come first) is watched work.
    ("script", "WATCH", r"(python3?\s+|node\s+|ruby\s+|perl\s+)?(\S*/)?[\w.-]+\.(sh|py|mjs|cjs|js|ts|rb|pl)\b"),
]

# Test, check and build runs, for the `tests` scan. Same matching as above; the label is the kind
# of run. A project adds its own with class TEST (the label names the kind, e.g. `gate`). A TEST
# rule also counts as WATCH for pauses.
DEFAULT_TEST_RULES = [
    ("unit", r"((npm|pnpm|yarn|bun)\s+(run\s+)?test(:[\w:.-]+)?|cargo\s+(test|nextest)|go\s+test"
             r"|(python3?\s+-m\s+)?pytest|python3?\s+-m\s+unittest|(npx\s+)?(vitest|jest|mocha|ava)"
             r"|mix\s+test|dotnet\s+test|deno\s+test|swift\s+test|ctest|tox|nox"
             r"|node\s+(--[\w-]+(=\S+)?\s+)*--test|(make|just)\s+(test|check)"
             r"|(\S*/)?(mvn|gradlew?)\b.*\s(test|verify|check))(\s|$)"),
    ("e2e", r"((npx\s+)?playwright\s+test|(npx\s+)?cypress\s+run)\b"),
    ("lint", r"((npm|pnpm|yarn)\s+run\s+(lint|typecheck|check)[\w:.-]*|(npx\s+)?(eslint|tsc|ruff|mypy|flake8)"
             r"|prettier\s+(--check|-c)|black\s+--check|cargo\s+(clippy|fmt\s+--check)|go\s+vet)(\s|$)"),
    ("build", r"((npm|pnpm|yarn)\s+run\s+build[\w:.-]*|cargo\s+build|go\s+build|ninja|cmake\s+--build"
              r"|make|docker\s+build|(\S*/)?(mvn|gradlew?)\s+(package|assemble|build))(\s|$)"),
    ("check-script", r"(\S*/)?[\w.-]*(test|check|gate|lint|verify|smoke|e2e|spec)[\w.-]*\.(sh|py|mjs|cjs|js|ts)\b"),
]

# Heredoc bodies are data, not commands: `cat > x.py <<'E' ... E` must not classify its body lines.
HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1[^\n]*\n.*?\n\s*\2\s*(?=\n|$)", re.S)
SEGMENT_SPLIT = re.compile(r"\s*(?:&&|\|\||;|\|(?!\|)|\n|(?<![>&])&(?![&>]))\s*")
DELIM = re.compile(r"(&&|\|\||;|\|(?!\|)|\n|(?<![>&])&(?![&>]))")
WRAPPER = re.compile(
    r"^(?:(?:do|then|else|time|nohup|setsid|exec|command|env|sudo)\s+|[!({]\s*"
    r"|\w+=(?:\"[^\"]*\"|'[^']*'|\S*)\s+"
    r"|timeout\s+(?:-\S+\s+)*\S+\s+"
    r"|(?:bash|sh|zsh)\s+(?:-\w+\s+)*['\"]?(?=\S))")


def segments(command):
    """Shell segments of a command: (stripped segment, delimiter that follows it)."""
    command = HEREDOC.sub(lambda mo: mo.group(0).split("\n", 1)[0], command or "")
    parts = DELIM.split(command)
    out = []
    for i in range(0, len(parts), 2):
        seg = parts[i].strip()
        if not seg or seg.startswith("cd ") or seg == "cd":
            continue
        prev = None
        while prev != seg:
            prev, seg = seg, WRAPPER.sub("", seg, count=1)
        out.append((seg, parts[i + 1] if i + 1 < len(parts) else ""))
    return out


NON_DELIVERY = []   # branch-name regexes of merged PRs that are not delivered work (project file)


def load_rules(path):
    rules = []
    if path and os.path.isfile(path):
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if not line.strip() or line.startswith("#"):
                    continue
                parts = line.rstrip("\n").split("\t")
                if len(parts) < 3 or parts[0] == "label":
                    continue
                cls = parts[1].strip().upper()
                if cls in ("WAIT", "WATCH", "IGNORE", "TEST"):
                    rules.append((parts[0].strip(), cls, parts[2].strip()))
                elif cls == "NON-DELIVERY":
                    NON_DELIVERY.append(re.compile(parts[2].strip()))
    n_project = len(rules)
    test_rules = [r for r in rules if r[1] in ("TEST", "IGNORE")] + [(lab, "TEST", rx) for lab, rx in DEFAULT_TEST_RULES]
    rules += DEFAULT_RULES
    return ([(lab, cls, re.compile(rx)) for lab, cls, rx in rules], n_project,
            [(lab, cls, re.compile(rx)) for lab, cls, rx in test_rules])


def classify(tool, command, rules):
    """Return (class, rule label) for one tool call."""
    if tool == "Monitor":
        return "WAIT", "monitor"
    if tool != "Bash":
        return "OTHER", tool.lower()
    found = {}
    for seg, _ in segments(command):
        for label, cls, rx in rules:
            if rx.match(seg):
                if cls != "IGNORE":
                    found.setdefault("WATCH" if cls == "TEST" else cls, label)
                break
    for cls in ("WAIT", "WATCH"):
        if cls in found:
            return cls, found[cls]
    return "OTHER", "-"


# ── Arguments ────────────────────────────────────────────────────────────────

def norm_ts(s):
    """'2025-03-03', '2025-03-03T09:00', '...:SSZ' -> 'YYYY-MM-DDTHH:MM:SS' (UTC)."""
    s = s.rstrip("Z").replace(" ", "T")
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(s, fmt).strftime("%Y-%m-%dT%H:%M:%S")
        except ValueError:
            pass
    sys.exit(f"Bad timestamp: {s} (use YYYY-MM-DD or YYYY-MM-DDTHH:MM[:SS][Z], UTC)")


def parse_args(argv):
    if not argv:
        sys.exit(USAGE)
    opts = {"input": argv[0], "scan": "all", "since": "", "from": "", "until": "",
            "sessions": [], "include_main": False, "patterns": "", "bucket": "", "json": False,
            "units": None, "repo": "", "non_delivery": "", "top": 0, "transcripts_dir": ""}
    rest = argv[1:]
    if rest and not rest[0].startswith("--"):
        opts["scan"] = rest.pop(0)
    while rest:
        a = rest.pop(0)
        if a in ("--include-main", "--json"):
            opts[a[2:].replace("-", "_")] = True
            continue
        if a not in ("--since", "--from", "--until", "--session", "--patterns", "--bucket", "--units",
                     "--repo", "--non-delivery", "--top", "--transcripts-dir") or not rest:
            print(f"Unknown option: {a}", file=sys.stderr)
            sys.exit(USAGE)
        v = rest.pop(0)
        if a == "--since":
            opts["since"] = v
        elif a == "--from":
            opts["from"] = norm_ts(v)
        elif a == "--until":
            opts["until"] = norm_ts(v)
        elif a == "--session":
            opts["sessions"] = [x for x in v.split(",") if x]
        elif a == "--bucket":
            if v not in ("day", "week"):
                sys.exit("--bucket takes day or week")
            opts["bucket"] = v
        elif a in ("--units", "--top"):
            opts[a[2:]] = int(v)
        else:
            opts[a[2:].replace("-", "_")] = v
    return opts


SLUG_MAX = 200  # Claude Code truncates longer slugs to this and appends "-<hash>"


def projects_root(override=""):
    """Where Claude Code keeps per-project transcript folders."""
    if override:
        return os.path.abspath(os.path.expanduser(override))
    config = os.environ.get("CLAUDE_CONFIG_DIR", "").strip() or "~/.claude"
    return os.path.join(os.path.abspath(os.path.expanduser(config)), "projects")


def project_transcript_dir(root, override=""):
    """Map a project path to its transcript folder, as Claude Code names it: every character that is
    not [A-Za-z0-9] becomes "-"; a slug over SLUG_MAX chars is cut there and gets "-<hash>" appended."""
    base = projects_root(override)
    slug = re.sub(r"[^A-Za-z0-9]", "-", root)
    jdir = os.path.join(base, slug)
    if os.path.isdir(jdir):
        return jdir
    if len(slug) > SLUG_MAX and os.path.isdir(base):
        # The hash suffix is internal to Claude Code; match on the truncated prefix instead.
        prefix = slug[:SLUG_MAX] + "-"
        hits = sorted(n for n in os.listdir(base) if n.startswith(prefix))
        if len(hits) == 1:
            return os.path.join(base, hits[0])
        if hits:
            sys.exit(f"Several transcript folders match the truncated slug {prefix}*: pass a .jsonl file")
    sys.exit(f"No Claude project folder found at: {jdir} "
             f"(set CLAUDE_CONFIG_DIR or --transcripts-dir if transcripts live elsewhere)")


def find_files(opts):
    inp = opts["input"]
    if inp.endswith(".jsonl"):
        return [inp], "", ""
    root = os.path.abspath(os.path.expanduser(inp))
    jdir = project_transcript_dir(root, opts["transcripts_dir"])
    floor_mtime = 0
    for d in (opts["since"], opts["from"]):
        if d:
            # Like `find -newermt`: local time. A file last written before --from has no line in it.
            floor_mtime = max(floor_mtime, dt.datetime.strptime(norm_ts(d), "%Y-%m-%dT%H:%M:%S").timestamp())
    files = []
    for base, _, names in os.walk(jdir):
        for n in names:
            if not n.endswith(".jsonl"):
                continue
            f = os.path.join(base, n)
            if floor_mtime and os.path.getmtime(f) <= floor_mtime:
                continue
            rel = os.path.relpath(f, jdir)
            if opts["sessions"] and not any(rel.startswith(s) for s in opts["sessions"]):
                continue
            files.append(f)
    return sorted(files), jdir, root


# ── Parsing ──────────────────────────────────────────────────────────────────

def epoch(ts):
    return dt.datetime.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S").replace(
        tzinfo=dt.timezone.utc).timestamp() + (float("0" + ts[19:].rstrip("Z")) if ts[19:20] == "." else 0)


def cr_weight(model, _cache={}):
    if model not in _cache:
        w = W_CR_DEFAULT
        for pair in CR_TABLE.split(","):
            if "=" in pair:
                p, v = pair.split("=", 1)
                if p and (model or "").startswith(p):
                    w = float(v)
                    break
        _cache[model] = w
    return _cache[model]


def message_kind(e, content):
    """Who ended a wait by writing into this transcript: human, peer, notification, agent, system."""
    kind = (e.get("origin") or {}).get("kind")
    if kind:
        return {"task-notification": "notification"}.get(kind, kind)
    text = content if isinstance(content, str) else " ".join(
        c.get("text", "") for c in content if isinstance(c, dict))
    text = text.lstrip()
    if text.startswith("<task-notification"):
        return "notification"
    if text.startswith("<cross-session-message") or text.startswith("Another Claude session"):
        return "peer"
    if text.startswith("<agent-message"):
        return "agent"
    if e.get("isMeta") or text.startswith("<") or text.startswith("This session is being continued"):
        return "system"
    return "human"


class Transcript:
    __slots__ = ("path", "rel", "is_sub", "session", "agent_type", "turns", "tools", "results",
                 "messages", "compacts", "has_window_line", "notifs", "first_ep", "last_ep")

    def __init__(self, path, jdir):
        self.path = path
        self.rel = os.path.relpath(path, jdir) if jdir else os.path.basename(path)
        self.is_sub = "/subagents/" in path
        self.session = self.rel.split("/")[0].replace(".jsonl", "")
        self.agent_type = "unknown"
        if self.is_sub:
            try:
                with open(path[:-6] + ".meta.json") as fh:
                    self.agent_type = json.load(fh).get("agentType") or "unknown"
            except (OSError, ValueError):
                pass
        self.turns = []        # dicts, sorted by time
        # tool_use id -> [ts, epoch, name, command/description, input prefix, turn index, cwd, background]
        self.tools = {}
        # tool_use id -> (ts, epoch, is_error, error text, head, tail of the result text)
        self.results = {}
        self.messages = []     # (epoch, ts, kind) for non-tool user entries
        self.compacts = []     # (ts, trigger, pre, post)
        self.has_window_line = False
        self.notifs = []       # (epoch, tool_use id, status, exit code) from task notifications
        self.first_ep = self.last_ep = None


def load(path, jdir, win):
    t = Transcript(path, jdir)
    turns = {}
    tool_turn = {}
    tool_extra = {}
    wfrom, wuntil = win
    try:
        fh = open(path, encoding="utf-8", errors="replace")
    except OSError:
        return t
    with fh:
        for line in fh:
            if '"api-request' in line[:60]:
                continue
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if not isinstance(e, dict):
                continue
            ts = e.get("timestamp")
            typ = e.get("type")
            if ts and (not wfrom or ts[:19] >= wfrom) and (not wuntil or ts[:19] < wuntil):
                t.has_window_line = True
            if typ == "queue-operation" and ts and "<task-notification" in str(e.get("content", "")):
                parse_notification(t, epoch(ts), str(e.get("content")))
                continue
            msg = e.get("message") if isinstance(e.get("message"), dict) else {}
            if typ == "assistant" and ts:
                u = msg.get("usage")
                content = msg.get("content") if isinstance(msg.get("content"), list) else []
                key = (msg.get("id"), e.get("requestId"))
                if u and msg.get("model") != "<synthetic>":
                    out = u.get("output_tokens") or 0
                    old = turns.get(key)
                    if old is None or out > old["out"]:
                        cc = u.get("cache_creation") or {}
                        cw = u.get("cache_creation_input_tokens") or 0
                        cw1h = cc.get("ephemeral_1h_input_tokens") or 0
                        cw5 = cc.get("ephemeral_5m_input_tokens")
                        if cw5 is None:
                            cw5 = 0 if cw1h else cw
                        turns[key] = {
                            "ts": ts, "first_ts": old["first_ts"] if old else ts, "model": msg.get("model"),
                            "in": u.get("input_tokens") or 0, "cw": cw, "cw5": cw5, "cw1h": cw1h,
                            "cr": u.get("cache_read_input_tokens") or 0, "out": out, "uuid": e.get("uuid")}
                for c in content:
                    if isinstance(c, dict) and c.get("type") == "tool_use" and c.get("id") not in t.tools:
                        inp = c.get("input") if isinstance(c.get("input"), dict) else {}
                        cmd = inp.get("command") or inp.get("description") or ""
                        if c.get("name") in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
                            cmd = inp.get("file_path") or inp.get("path") or inp.get("notebook_path") or "unknown"
                        t.tools[c["id"]] = [ts, epoch(ts), c.get("name") or "?", str(cmd),
                                            json.dumps(inp, sort_keys=True)[:120]]
                        tool_turn[c["id"]] = key
                        tool_extra[c["id"]] = [e.get("cwd") or "", bool(inp.get("run_in_background"))]
            elif typ == "user" and ts:
                content = msg.get("content")
                results = [c for c in content if isinstance(c, dict) and c.get("type") == "tool_result"] \
                    if isinstance(content, list) else []
                for r in results:
                    tid = r.get("tool_use_id")
                    if tid and tid not in t.results:
                        rc = r.get("content")
                        txt = rc[0].get("text", "") if isinstance(rc, list) and rc and isinstance(rc[0], dict) \
                            else str(rc or "")
                        t.results[tid] = (ts, epoch(ts), bool(r.get("is_error")),
                                          txt if r.get("is_error") else "", txt[:200], txt[-400:])
                if not results and content:
                    kind = message_kind(e, content)
                    t.messages.append((epoch(ts), ts, kind))
                    if kind == "notification":
                        parse_notification(t, epoch(ts), content if isinstance(content, str) else json.dumps(content))
            elif typ == "system" and e.get("subtype") == "compact_boundary" and ts:
                cm = e.get("compactMetadata") or {}
                t.compacts.append((ts, cm.get("trigger", "?"), cm.get("preTokens") or 0, cm.get("postTokens") or 0))
    order = sorted(turns, key=lambda k: turns[k]["ts"])
    index = {k: i for i, k in enumerate(order)}
    for k in order:
        d = turns[k]
        d["ep"] = epoch(d["ts"])
        d["first_ep"] = epoch(d["first_ts"])
        d["ctx"] = d["in"] + d["cw"] + d["cr"]
        d["in_win"] = (not wfrom or d["ts"][:19] >= wfrom) and (not wuntil or d["ts"][:19] < wuntil)
        t.turns.append(d)
    for tid, tk in tool_turn.items():
        t.tools[tid].append(index.get(tk))
        t.tools[tid] += tool_extra[tid]
    t.messages.sort()
    eps = [d["first_ep"] for d in t.turns] + [d["ep"] for d in t.turns] + [r[1] for r in t.results.values()] \
        + [x[0] for x in t.messages]
    if eps:
        t.first_ep, t.last_ep = min(eps), max(eps)
    return t


NOTIF = re.compile(r"<tool-use-id>(\w+)</tool-use-id>.*?<status>(\w+)</status>(?:.*?exit code (\d+))?", re.S)


def parse_notification(t, ep, text):
    for mo in NOTIF.finditer(text):
        t.notifs.append((ep, mo.group(1), mo.group(2), int(mo.group(3)) if mo.group(3) else None))


# ── Cost model ───────────────────────────────────────────────────────────────

def classes(turns):
    c = collections.Counter()
    for d in turns:
        c["in"] += d["in"]
        c["cw5"] += d["cw5"]
        c["cw1h"] += d["cw1h"]
        c["cr"] += d["cr"]
        c["crq"] += d["cr"] * cr_weight(d["model"])
        c["out"] += d["out"]
    return c


def eq(c):
    return c["in"] * W_IN + c["cw5"] * W_CW5 + c["cw1h"] * W_CW1H + c["crq"] + c["out"] * W_OUT


def write_eq(c):
    return c["cw5"] * W_CW5 + c["cw1h"] * W_CW1H


def k(x):
    return f"{int(x // 1000)}k"


def m(x):
    return f"{math.floor(x / 1e5) / 10}M"


def pct(a, b):
    return f"{math.floor(a / b * 100) if b > 0 else 0}%"


def in_win(t):
    return [d for d in t.turns if d["in_win"]]


# ── Cache misses ─────────────────────────────────────────────────────────────

def gap_cause(t, i, rules):
    """What the agent stream was doing between turn i-1 and turn i."""
    prev, cur = t.turns[i - 1], t.turns[i]
    gap = cur["first_ep"] - prev["ep"]
    held = [(t.results[tid][1] - tool[1], tool) for tid, tool in t.tools.items()
            if tool[5] == i - 1 and tid in t.results]
    if held:
        dur, tool = max(held, key=lambda x: x[0])
        if dur >= 0.5 * gap:
            cls, _ = classify(tool[2], tool[3], rules)
            return {"WAIT": "tool run: polling (WAIT)", "WATCH": "tool run: build/test/remote (WATCH)"}.get(
                cls, "tool run: other")
    kinds = [kd for ep, _, kd in t.messages if prev["ep"] < ep <= cur["first_ep"]]
    if kinds:
        kd = kinds[-1]
        if kd == "human":
            return "dormant agent resumed" if t.is_sub else "operator wait"
        return {"peer": "peer message", "notification": "waiting on background task or subagent",
                "agent": "waiting on background task or subagent"}.get(
                    kd, "dormant agent resumed" if t.is_sub else "other")
    return "other (long model turn or untracked)"


def cache_events(t, rules):
    """Rebuild events of in-window turns: (kind, turn, gap, lifetime, excess eq, cause)."""
    ev = []
    for i, d in enumerate(t.turns):
        if not d["in_win"]:
            continue
        cw, cr = d["cw"], d["cr"]
        if cw <= 0 or cw < MISS_MIN_WRITE or cw / (cw + cr) <= REBUILD_RATIO:
            continue
        excess = d["cw5"] * W_CW5 + d["cw1h"] * W_CW1H - cw * cr_weight(d["model"])
        if i == 0:
            ev.append(("start", d, 0, 0, excess, "agent start"))
            continue
        prev = t.turns[i - 1]
        gap = d["first_ep"] - prev["ep"]
        life = LIFETIME_1H if d["cw1h"] > 0.5 * cw else LIFETIME_5M
        if gap > life:
            ev.append(("miss", d, gap, life, excess, gap_cause(t, i, rules)))
        elif cr < PREFIX_LOST_RATIO * prev["ctx"]:
            ev.append(("miss", d, gap, life, excess, "compaction or context rewrite"))
    return ev


# ── Scans ────────────────────────────────────────────────────────────────────

def scan_summary(t):
    w = in_win(t)
    c = classes(w)
    tools = [x for x in t.tools.values() if x[5] is not None and t.turns[x[5]]["in_win"]]
    errs = sum(1 for tid, x in t.tools.items() if tid in t.results and t.results[tid][2]
               and x[5] is not None and t.turns[x[5]]["in_win"])
    print(f"API turns (deduplicated):       {len(w)}")
    print(f"Tool calls:                     {len(tools)}")
    print(f"Errors:                         {errs}")
    print(f"Tokens in/cw5/cw1h/read/out:    {c['in']} / {c['cw5']} / {c['cw1h']} / {c['cr']} / {c['out']}")
    print(f"Cost (eq base-input tokens):    {m(eq(c))}")


def cache_lines(turns, events, prefix=""):
    c = classes(turns)
    e = eq(c)
    wr = c["cw5"] + c["cw1h"]
    hit = c["cr"] / (c["in"] + c["cr"] + wr) if (c["in"] + c["cr"] + wr) else 0
    misses = [x for x in events if x[0] == "miss"]
    starts = [x for x in events if x[0] == "start"]
    miss_eq = sum(x[4] for x in misses)
    print(f"CACHE — {prefix}writes {pct(write_eq(c), e)} of eq | hit ratio {hit * 100:.1f}% by tokens"
          f" | 1h share of writes {pct(c['cw1h'], wr)}")
    print(f"CACHE-MISS — {prefix}{len(misses)} avoidable misses of {len(misses) + len(starts)} rebuilds,"
          f" excess {m(miss_eq)} eq = {pct(miss_eq, e)} of eq"
          f" | agent starts {len(starts)}, {m(sum(x[4] for x in starts))} eq (unavoidable)")
    return misses, miss_eq, e


def scan_cost(t, rules):
    w = in_win(t)
    if not w:
        print("OK — no API turns")
        return
    c = classes(w)
    e = eq(c)
    x = [d["ctx"] for d in w]
    models = ",".join(sorted({d["model"] or "?" for d in w}))
    print(f"COST — {m(e)} eq | turns={len(w)} | models={models} | read={pct(c['crq'], e)} "
          f"write={pct(write_eq(c), e)} output={pct(c['out'] * W_OUT, e)} input={pct(c['in'] * W_IN, e)}")
    flag = f" ← peak above {k(CTX_WARN)}: every turn re-reads this" if max(x) > CTX_WARN else ""
    print(f"CONTEXT — baseline={k(x[0])} avg={k(sum(x) / len(x))} peak={k(max(x))}{flag}")
    for ts, trig, pre, post in t.compacts:
        if WIN_OK(ts):
            print(f"COMPACT — {trig} at {k(pre)} → {k(post)} | {ts[:16]}")
    misses, _, _ = cache_lines(w, cache_events(t, rules))
    for kind, d, gap, life, excess, cause in sorted(misses, key=lambda x: -x[4])[:5]:
        why = f"after {int(gap)}s idle (past {'1h' if life == LIFETIME_1H else '5m'} lifetime)" \
            if gap > life else f"after {int(gap)}s, prefix lost"
        print(f"CACHE-MISS — rewrote {k(d['cw'])} {why} | {m(excess)} eq | cause: {cause} | {d['ts'][:16]}")


def scan_cache(ts_list, rules):
    all_turns, events, by_cause, by_agent = [], [], collections.Counter(), collections.Counter()
    n_cause = collections.Counter()
    for t in ts_list:
        all_turns += in_win(t)
        ev = cache_events(t, rules)
        events += ev
        for x in ev:
            if x[0] == "miss":
                by_cause[x[5]] += x[4]
                n_cause[x[5]] += 1
                by_agent[t.agent_type if t.is_sub else "(main session)"] += x[4]
    if not all_turns:
        print("OK — no API turns")
        return
    _, miss_eq, e = cache_lines(all_turns, events)
    for cause, v in by_cause.most_common():
        print(f"CACHE-MISS-CAUSE — {cause}: {n_cause[cause]} misses, {m(v)} eq ({pct(v, miss_eq)} of miss cost)")
    for agent, v in by_agent.most_common(5):
        print(f"CACHE-MISS-AGENT — {agent}: {m(v)} eq ({pct(v, miss_eq)} of miss cost)")


def scan_agents(ts_list):
    groups = collections.defaultdict(lambda: [0, 0, 0.0, 0])
    tot = 0.0
    for t in ts_list:
        if not t.is_sub:
            continue
        w = in_win(t)
        if not w:
            continue
        g = groups[f"{t.agent_type} [{w[-1]['model']}]"]
        e = eq(classes(w))
        g[0] += 1
        g[1] += len(w)
        g[2] += e
        g[3] = max(g[3], max(d["ctx"] for d in w))
        tot += e
    if not groups:
        print("OK — no subagent transcripts")
        return
    for key, (n, turns, e, peak) in sorted(groups.items(), key=lambda kv: -kv[1][2]):
        print(f"AGENT — {key:<40} runs={n:<3d} avg-turns={int(turns / n):<4d} peak-ctx={int(peak / 1000)}k "
              f"eq/turn={int(e / turns / 1000)}k cost={e / 1e6:.1f}M eq ({int(e / tot * 100) if tot else 0}%)")


def scan_trend(ts_list, from_set):
    subs = collections.defaultdict(list)
    for t in ts_list:
        if t.is_sub:
            subs[t.session].append(t)
    rows = []
    for t in ts_list:
        if t.is_sub:
            continue
        w = in_win(t)
        if not w:
            continue
        x = [d["ctx"] for d in w]
        main = eq(classes(w))
        sub = sum(eq(classes(in_win(s))) for s in subs.get(t.session, []))
        comp = sum(1 for c in t.compacts if WIN_OK(c[0]))
        rows.append((w[0]["ts"][:10], t.session[:8], len(w), x[0], sum(x) / len(x), max(x), main, sub,
                     w[-1]["model"], comp))
    label = "first-in-window" if from_set else "base"
    for date, sid, n, base, avg, peak, main, sub, model, comp in sorted(rows):
        total = main + sub
        print(f"TREND — {date} {sid} turns={n:<4d} {label}={int(base / 1000)}k avg={int(avg / 1000)}k "
              f"peak={int(peak / 1000)}k compactions={comp} | main={main / 1e6:.1f}M sub={sub / 1e6:.1f}M "
              f"total={total / 1e6:.1f}M eq (sub {int(sub / total * 100) if total else 0}%) | {model}")


def scan_pauses(ts_list, rules, include_main, single, as_json=False):
    scope = [t for t in ts_list if single or include_main or t.is_sub]
    if not scope:
        print("OK — no subagent transcripts")
        return
    who = "" if single else ("" if include_main else "subagent ")
    turns = sum(len(in_win(t)) for t in scope)
    n, ctx, ex, labels = collections.Counter(), collections.Counter(), collections.defaultdict(list), \
        collections.defaultdict(collections.Counter)
    tot = over = 0
    for t in scope:
        # One pause per issuing turn: parallel tool calls waited on together are one wait.
        longest = {}
        for tid, (ts, ep, name, cmd, _inp, ti, *_) in t.tools.items():
            if ti is None or not t.turns[ti]["in_win"] or tid not in t.results:
                continue
            dur = t.results[tid][1] - ep
            if ti not in longest or dur > longest[ti][0]:
                longest[ti] = (dur, name, cmd, tid, ts)
        for ti, (dur, name, cmd, tid, ts) in longest.items():
            if dur <= PAUSE_MIN:
                continue
            if dur > PAUSE_MAX:
                over += 1
                continue
            cls, label = classify(name, cmd, rules)
            if as_json:
                d = t.turns[ti]
                print(json.dumps({"event": "pause", "transcript": t.rel, "session": t.session,
                                  "agent_type": t.agent_type if t.is_sub else "(main session)",
                                  "is_subagent": t.is_sub, "tool_use_id": tid, "tool": name, "command": cmd,
                                  "start": ts, "end": t.results[tid][0], "gap_s": round(dur), "class": cls,
                                  "rule": label, "ctx_tokens": d["ctx"], "cw_5m": d["cw5"], "cw_1h": d["cw1h"],
                                  "cache_read": d["cr"], "model": d["model"]}))
            tot += 1
            n[cls] += 1
            ctx[cls] += t.turns[ti]["ctx"]
            labels[cls][label] += 1
            if len(ex[cls]) < 2:
                ex[cls].append(f"{name} {' '.join(cmd.split())}"[:240])
    if as_json:
        return
    if tot == 0:
        print(f"OK — no 5–60 min pauses in {turns} {who}turns")
        return
    print(f"PAUSE — {tot} pauses of 5–60 min in {turns} {who}turns ({tot / turns * 100:.1f}%); "
          f"{over} longer than 1 h")
    for cls in ("WAIT", "WATCH", "OTHER"):
        if not n[cls]:
            continue
        rl = ", ".join(f"{lab} {c}" for lab, c in labels[cls].most_common(4))
        print(f"PAUSE-{cls} — {n[cls]} ({int(n[cls] / tot * 100)}%) avg ctx {int(ctx[cls] / n[cls] / 1000)}k | "
              f"5m-lifetime rewrite cost ≈ {ctx[cls] * W_CW5 / 1e6:.1f}M eq | rules: {rl}")
        for s in ex[cls]:
            print(f"    e.g. {s}")
    if n["WAIT"] >= n["WATCH"] + n["OTHER"]:
        print("PAUSE-HINT — mostly waiting: detach these operations (hand back at enqueue, let the "
              "caller wait), rather than paying for a 1h subagent cache")
    else:
        print("PAUSE-HINT — mostly watched work: a 1h subagent cache (subagentPromptCacheTtl) may pay. "
              "Compare its 2x-vs-1.25x write premium on every write against the WATCH rewrite cost above")


def win_tools(t):
    """In-window tool calls in time order: (ts, name, cmd, input-prefix, id)."""
    rows = [(x[0], x[2], x[3], x[4], tid) for tid, x in t.tools.items()
            if x[5] is not None and t.turns[x[5]]["in_win"]]
    return sorted(rows)


def scan_errors(t):
    found = False
    for ts, name, cmd, inp, tid in win_tools(t):
        r = t.results.get(tid)
        if r and r[2]:
            found = True
            print(f"ERROR — tool_use_id: {tid}\n  {' '.join(r[3].split())[:200]}")
    if not found:
        print("OK — no errors detected")


def scan_loops(t):
    found = False
    tools = win_tools(t)
    run, prev = 0, None
    for _, name, *_ in tools + [(None, None, None, None, None)]:
        if name == prev:
            run += 1
            continue
        if prev is not None and run >= 3:
            print(f"LOOP — {run}x {prev}")
            found = True
        run, prev = 1, name
    rep = collections.Counter(f"{name}|{inp}" for _, name, _, inp, _ in tools)
    for key, c in rep.most_common():
        if c < 3:
            break
        print(f"REPEAT — {c:>6} {key}")
        found = True
    if not found:
        print("OK — no loop patterns detected")


def scan_expensive(t):
    rows = sorted((d for d in in_win(t) if d["out"] > 2000), key=lambda d: -d["out"])
    for d in rows:
        print(f"EXPENSIVE-OUTPUT — {d['out']} output tokens | uuid: {d['uuid']}")
    if not rows:
        print("OK — no expensive output turns")


def scan_trialerror(t):
    found = False
    tools = win_tools(t)
    edits = collections.Counter(cmd for _, name, cmd, _, _ in tools
                                if name in ("Edit", "Write", "MultiEdit", "NotebookEdit"))
    for f, c in edits.most_common():
        if c < 3:
            break
        print(f"CHURN — {c}x edits on {f}")
        found = True
    cmds = collections.Counter(cmd[:100] for _, name, cmd, _, _ in tools if name == "Bash")
    for cmd, c in cmds.most_common():
        if c < 3:
            break
        print(f"REPEAT-CMD — {c:>6} {cmd}")
        found = True
    n = len(in_win(t))
    if n > 200:
        print(f"LONG SESSION — {n} API turns")
        found = True
    if not found:
        print("OK — no trial-and-error patterns detected")


# ── Intervals ────────────────────────────────────────────────────────────────

def union(iv):
    out = []
    for a, b in sorted(x for x in iv if x[1] > x[0]):
        if out and a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return out


def subtract(a, b, merged):
    """Pieces of [a, b) not covered by the merged intervals."""
    pieces, cur = [], a
    for x, y in merged:
        if y <= cur or x >= b:
            continue
        if x > cur:
            pieces.append((cur, x))
        cur = max(cur, y)
    if cur < b:
        pieces.append((cur, b))
    return pieces


def total(iv):
    return sum(b - a for a, b in iv)


def h(sec):
    return f"{sec / 3600:.1f} h" if sec >= 3600 else f"{int(sec // 60)} min"


def window_bounds(ts_list, wfrom, wuntil):
    eps = [x for t in ts_list for x in (t.first_ep, t.last_ep) if x is not None]
    w0 = epoch(wfrom) if wfrom else (min(eps) if eps else 0)
    w1 = epoch(wuntil) if wuntil else (max(eps) if eps else 0)
    return w0, w1


def notification_map(ts_list):
    """tool_use id -> earliest (epoch, status, exit code), from any transcript in scope."""
    nm = {}
    for t in ts_list:
        for ep, tid, status, code in t.notifs:
            if tid not in nm or ep < nm[tid][0]:
                nm[tid] = (ep, status, code)
    return nm


def went_background(r):
    head = r[4] if r else ""
    return head.startswith("Command running in background") or "moved to the background" in head


def test_match(command, test_rules):
    """First test/check/build segment of a command: (label, segment, delimiter after it) or None."""
    for seg, delim in segments(command):
        for label, cls, rx in test_rules:
            if rx.match(seg):
                if cls == "TEST":
                    return label, seg, delim
                break
    return None


# ── Time use ─────────────────────────────────────────────────────────────────
# Every gap between two consecutive entries of a transcript goes to the entry that ends it:
#   a model turn               → working
#   a tool result              → by tool: polling or a test/build/remote run → waiting on jobs;
#                                a quick tool → working, or a stall if it took over STALL_S;
#                                a synchronous subagent call → dormant (waiting on a subagent)
#   a message                  → main session: operator wait (human), else dormant;
#                                subagent: dormant (resumed by its caller, a peer, a notification)
# In a main session, operator wait while its subagents or background tasks were working counts as
# "idle while others work", not as operator wait: the operator was not what it waited for.

def time_segments(t, rules, test_rules):
    pts = []
    for d in t.turns:
        pts.append((d["first_ep"], "turn", None))
        pts.append((d["ep"], "turn", None))
    for tid, r in t.results.items():
        pts.append((r[1], "result", tid))
    for ep, _, kind in t.messages:
        pts.append((ep, "msg", kind))
    pts.sort(key=lambda x: x[0])
    segs = []
    for (a, _, _), (b, typ, arg) in zip(pts, pts[1:]):
        if b <= a:
            continue
        if typ == "turn":
            cat, sub = "working", "model"
        elif typ == "result":
            tool = t.tools.get(arg)
            r = t.results[arg]
            name, cmd = (tool[2], tool[3]) if tool else ("?", "")
            if name == "Bash":
                cls, label = classify(name, cmd, rules)
                tm = test_match(cmd, test_rules)
                if cls == "WAIT":
                    cat, sub = "jobs", f"poll: {label}"
                elif tm or cls == "WATCH":
                    cat, sub = "jobs", f"run: {tm[0] if tm else label}"
                else:
                    cat, sub = ("dormant", "stalled tool") if b - a > STALL_S else ("working", "tool")
            elif name == "Monitor":
                cat, sub = "jobs", "poll: monitor"
            elif name in ("Agent", "Task") and not r[4].startswith("Async agent launched"):
                cat, sub = "dormant", "waiting on a subagent (synchronous)"
            elif name == "AskUserQuestion":
                cat, sub = ("operator", "question") if not t.is_sub else ("dormant", "question")
            else:
                cat, sub = ("dormant", "stalled tool") if b - a > STALL_S else ("working", "tool")
        else:
            if arg == "human":
                cat, sub = ("dormant", "resumed by its caller") if t.is_sub else ("operator", "operator")
            elif arg in ("coordinator", "agent") and t.is_sub:
                cat, sub = "dormant", "resumed by its caller"
            elif arg == "peer":
                cat, sub = "dormant", "peer message"
            elif arg in ("notification", "agent"):
                cat, sub = "dormant", "waiting on subagents or background tasks"
            else:
                cat, sub = "working", "system"
        segs.append((a, b, cat, sub))
    return segs


def time_use(ts_list, rules, test_rules, w0, w1):
    nm = notification_map(ts_list)
    per = {t.path: [(max(a, w0), min(b, w1), c, s) for a, b, c, s in time_segments(t, rules, test_rules)
                    if b > w0 and a < w1] for t in ts_list}
    # What a main session had in flight: its subagents' active time and its pending background work.
    busy = collections.defaultdict(list)
    for t in ts_list:
        if t.is_sub:
            busy[t.session] += [(a, b) for a, b, c, _ in per[t.path] if c in ("working", "jobs")]
        else:
            for tid, tool in t.tools.items():
                r = t.results.get(tid)
                if r and (went_background(r) or r[4].startswith("Async agent launched")) and tid in nm:
                    busy[t.session].append((tool[1], nm[tid][0]))
    busy = {k_: union(v) for k_, v in busy.items()}
    acc, sub_acc = collections.Counter(), collections.Counter()
    op_iv, longest, blocking, asks = [], 0, 0, 0
    for t in ts_list:
        segs = per[t.path]
        if not t.is_sub:
            asks += sum(1 for tool in t.tools.values() if tool[2] == "AskUserQuestion" and w0 <= tool[1] < w1)
        for a, b, cat, sub in segs:
            if cat == "operator":
                merged = busy.get(t.session, [])
                free = subtract(a, b, merged)
                idle = (b - a) - total(free)
                if idle:
                    acc["dormant"] += idle
                    sub_acc["idle while subagents or background tasks work"] += idle
                if free:
                    acc["operator"] += total(free)
                    sub_acc["operator wait"] += total(free)
                    op_iv += free
                    longest = max(longest, max(y - x for x, y in free))
                    if not any(x <= a < y for x, y in merged) and sub == "operator" and total(free) >= 60:
                        blocking += 1
                continue
            acc[cat] += b - a
            sub_acc[sub if cat != "jobs" else sub.split(":")[0]] += b - a
    jobs_by = collections.Counter()
    for t in ts_list:
        for a, b, cat, sub in per[t.path]:
            if cat == "jobs":
                jobs_by[sub] += b - a
    return {"acc": acc, "sub": sub_acc, "op_union": total(union(op_iv)), "longest": longest,
            "blocking": blocking, "asks": asks, "jobs_by": jobs_by, "calendar": max(0, w1 - w0),
            "transcripts": sum(1 for t in ts_list if per[t.path])}


def scan_time(ts_list, rules, test_rules, w0, w1):
    tu = time_use(ts_list, rules, test_rules, w0, w1)
    acc = tu["acc"]
    agent = acc["working"] + acc["jobs"] + acc["dormant"]
    if not agent:
        print("OK — no agent time in window")
        return tu
    eff = tu["calendar"] - tu["op_union"]
    print(f"TIME — calendar {h(tu['calendar'])} | effective {h(eff)} (calendar minus operator wait) | "
          f"agent time {h(agent)} over {tu['transcripts']} transcripts, operator wait excluded")
    print(f"TIME-SPLIT — working {h(acc['working'])} ({pct(acc['working'], agent)}) | waiting on jobs "
          f"{h(acc['jobs'])} ({pct(acc['jobs'], agent)}) | dormant {h(acc['dormant'])} ({pct(acc['dormant'], agent)})"
          f" | shares of agent time; operator wait {h(acc['operator'])} is reported apart")
    dorm = [(s_, v) for s_, v in tu["sub"].most_common() if s_ not in ("model", "tool", "system", "poll", "run",
                                                                        "operator wait")]
    if dorm:
        print("TIME-DORMANT — " + " | ".join(f"{s_} {h(v)}" for s_, v in dorm))
    print(f"TIME-OPERATOR — operator wait {h(tu['op_union'])} (wall-clock union), longest {h(tu['longest'])}, "
          f"{tu['blocking']} blocking waits with nothing in flight, {tu['asks']} AskUserQuestion calls")
    if tu["jobs_by"]:
        print("TIME-JOBS — poll " + h(sum(v for s_, v in tu["jobs_by"].items() if s_.startswith("poll")))
              + ", runs " + h(sum(v for s_, v in tu["jobs_by"].items() if s_.startswith("run"))) + " | top: "
              + ", ".join(f"{s_} {h(v)}" for s_, v in tu["jobs_by"].most_common(5)))
    return tu


# ── Test, check and build runs ───────────────────────────────────────────────

FAIL_COUNT = re.compile(r"\b(\d+) (?:failed|failures|failing|fail)\b|\bfail(?:ed|ures)?:? (\d+)\b", re.I)
FAIL_MARK = re.compile(r"\b(FAIL(ED|URES?)?|failing|panicked|Error:|RED)\b|✖|✗")
PASS_MARK = re.compile(r"\b(PASS(ED)?|passed|GREEN|ok)\b|✓|✔")
EXIT_LINE = re.compile(r"(?m)^\s*exit[ =:]+(\d+)\b")
CHANGE = re.compile(r"(git\s+(commit|checkout|switch|merge|pull|rebase|reset|am|cherry-pick|stash|restore|apply)"
                    r"|sed\s+(-\w+\s+)*-i|perl\s+-\w*i|patch|cp|mv|rm|tee|(npm|pnpm)\s+(ci|install|i)"
                    r"|yarn(\s+install)?|cargo\s+update)\b")
REDIRECT = re.compile(r"(?<![0-9&])>>?\s*(?!/dev/|/tmp/|&)(\S+)")


def run_dir(tool):
    cwd = tool[6] or ""
    mo = re.match(r"\s*cd\s+(\"[^\"]+\"|'[^']+'|[^\s;&|)]+)", tool[3] or "")
    if mo:
        d = mo.group(1).strip("\"'")
        cwd = d if d.startswith("/") else os.path.normpath(os.path.join(cwd, d))
    return cwd


def norm_cmd(seg):
    seg = re.sub(r"/tmp/\S+", "<tmp>", seg)
    seg = re.sub(r"\b[0-9a-f]{7,40}\b", "<h>", seg)
    seg = re.sub(r"\b\d{4,}\b", "<n>", seg)
    return " ".join(seg.split())[:200]


def collect_runs(ts_list, test_rules, nm):
    runs, changes = [], []
    for t in ts_list:
        for tid, tool in t.tools.items():
            name, cmd, ti = tool[2], tool[3], tool[5]
            if name in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
                changes.append((tool[1], cmd))
                continue
            if name != "Bash":
                continue
            d_ = run_dir(tool)
            for seg, _ in segments(cmd):
                if CHANGE.match(seg) or REDIRECT.search(seg):
                    changes.append((tool[1], d_))
                    break
            tm = test_match(cmd, test_rules)
            if not tm or ti is None or not t.turns[ti]["in_win"]:
                continue
            label, seg, delim = tm
            r = t.results.get(tid)
            run = {"transcript": t.rel, "session": t.session, "tool_use_id": tid, "label": label,
                   "command": seg[:300], "dir": d_, "key": (label, norm_cmd(seg), d_), "start": tool[1],
                   "start_ts": tool[0], "end": None, "status": "open", "moved": False, "killed": False,
                   "agent_type": t.agent_type if t.is_sub else "(main session)"}
            if r is None:
                pass
            elif went_background(r) or tool[7]:
                run["moved"] = "moved to the background" in r[4]
                n_ = nm.get(tid)
                if n_:
                    run["end"] = n_[0]
                    code = n_[2]
                    run["killed"] = n_[1] == "killed" or (code is not None and code > 128)
                    run["status"] = "pass" if n_[1] == "completed" and not code else "fail"
            elif delim == "&":
                # Started with `&` and (usually) polled: its own log decides, if it still exists.
                log_end(run, seg, cmd)
            else:
                run["end"] = r[1]
                tail = r[5]
                ex = EXIT_LINE.findall(tail)
                # A final `exit N` line decides. Otherwise the tool's error flag when it is the run's own
                # exit code (the run is last, or followed by &&, or piped with pipefail); else the output.
                if ex:
                    run["status"] = "pass" if ex[-1] == "0" else "fail"
                elif delim in ("", "&&") or (delim == "|" and "pipefail" in cmd):
                    run["status"] = "fail" if r[2] else "pass"
                else:
                    run["status"] = output_status(tail)
            runs.append(run)
    runs.sort(key=lambda x: x["start"])
    changes.sort()
    return runs, changes


def output_status(text):
    """pass / fail / unknown from a run's output: failure counts first, then markers. Lines that
    report an expected red (a red-proof or mutant that was meant to fail) are not failures."""
    text = "\n".join(ln for ln in text.splitlines() if not re.search(r"expected red|MUTANT", ln, re.I))
    counts = [int(a or b) for a, b in FAIL_COUNT.findall(text)]
    if counts:
        return "fail" if any(counts) else "pass"
    if FAIL_MARK.search(text):
        return "fail"
    return "pass" if PASS_MARK.search(text) else "unknown"


def log_end(run, seg, cmd):
    """End and status of a run started with `&`, from the log it redirects to: the log's last write
    and its last `exit N` line or pass/fail markers. Left open when there is no log to read."""
    mo = re.search(r"(?<![0-9&])>>?\s*(\S+)", seg)
    if not mo:
        return
    path = mo.group(1).strip("\"'")
    for var, val in re.findall(r"(?:^|[\s;&(])(\w+)=(\"[^\"]*\"|'[^']*'|\S+)", cmd):
        path = path.replace("${%s}" % var, val.strip("\"'")).replace("$" + var, val.strip("\"'"))
    if "$" in path:
        return
    if not path.startswith("/"):
        path = os.path.join(run["dir"], path)
    try:
        end = os.path.getmtime(path)
        with open(path, "rb") as fh:
            fh.seek(max(0, os.path.getsize(path) - 4096))
            tail = fh.read().decode("utf-8", "replace")
    except OSError:
        return
    if not run["start"] < end < run["start"] + 86400:
        return
    run["end"], run["via_log"] = end, True
    ex = EXIT_LINE.findall(tail)
    run["status"] = ("pass" if ex[-1] == "0" else "fail") if ex else output_status(tail)


def p95(xs):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(math.ceil(0.95 * len(xs))) - 1)] if xs else 0


def analyse_runs(runs, changes):
    by_label = collections.defaultdict(list)
    for r in runs:
        if r["end"] is not None:
            r["dur"] = r["end"] - r["start"]
            by_label[r["label"]].append(r)
    # Hung: ended through its own notification after a timeout or a kill signal, and far longer than
    # its kind normally takes. Counted at the kind's median, so one orphan cannot distort the total.
    for label, rs in by_label.items():
        durs = sorted(x["dur"] for x in rs)
        med = durs[len(durs) // 2] if durs else 0
        for r in rs:
            others = [x["dur"] for x in rs if x is not r]
            limit = max(3600, 10 * p95(others)) if len(others) >= 20 else 3600
            r["hung"] = (r["moved"] or r["killed"]) and r["dur"] > limit
            r["counted"] = med if r["hung"] else r["dur"]
    last = {}
    for r in runs:
        r["rerun"] = r["dup"] = False
        prev = last.get(r["key"])
        if prev and prev["end"] is not None:
            if prev["status"] == "fail" and r["start"] - prev["end"] <= RERUN_WINDOW_S:
                r["rerun"] = True
            elif prev["status"] == "pass":
                d_ = r["dir"]
                changed = any(prev["end"] <= ep < r["start"] and p_ and d_ and (p_.startswith(d_) or d_.startswith(p_))
                              for ep, p_ in changes)
                r["dup"] = not changed
        last[r["key"]] = r
    return runs


def scan_tests(ts_list, test_rules, w0, w1, as_json=False):
    nm = notification_map(ts_list)
    runs, changes = collect_runs(ts_list, test_rules, nm)
    analyse_runs(runs, changes)
    if as_json:
        for r in runs:
            print(json.dumps({"event": "run", **{k_: r.get(k_) for k_ in (
                "transcript", "session", "agent_type", "tool_use_id", "label", "command", "dir", "start_ts",
                "status", "moved", "killed", "hung", "rerun", "dup")},
                "duration_s": round(r["dur"]) if r.get("dur") is not None else None,
                "counted_s": round(r["counted"]) if r.get("counted") is not None else None}))
        return runs
    if not runs:
        print("OK — no test, check or build runs")
        return runs
    ended = [r for r in runs if r.get("dur") is not None]
    summed = sum(r["counted"] for r in ended)
    wall = total(union([(r["start"], r["start"] + r["counted"]) for r in ended]))
    st = collections.Counter(r["status"] for r in runs)
    kinds = collections.Counter(r["label"] for r in runs)
    print(f"TESTS — {len(runs)} runs ({', '.join(f'{k_} {v}' for k_, v in kinds.most_common(6))}) | summed "
          f"{h(summed)}, wall-clock union {h(wall)} = {pct(wall, max(1, w1 - w0))} of the window | failed "
          f"{st['fail']}, status unreadable {st['unknown']}, open {st['open']} (no end, excluded)")
    rr = [r for r in runs if r["rerun"]]
    print(f"TESTS-RERUN — {len(rr)} re-runs after a failure (same command and directory within "
          f"{RERUN_WINDOW_S // 3600} h): {h(sum(r.get('counted', 0) for r in rr))}")
    dd = [r for r in runs if r["dup"]]
    print(f"TESTS-DUP — {len(dd)} possible duplicates (approximate: same command and directory, the previous "
          f"run passed, no edit, commit or install seen between): {h(sum(r.get('counted', 0) for r in dd))}")
    for r in sorted(dd, key=lambda x: -x.get("counted", 0))[:3]:
        print(f"    e.g. {r['label']}: {r['command'][:100]} | {r['agent_type']} | {r['start_ts'][:16]}")
    hung = [r for r in ended if r["hung"]]
    if hung:
        print(f"TESTS-HUNG — {len(hung)} hung runs, {h(sum(r['dur'] - r['counted'] for r in hung))} removed "
              f"(counted at the median of their kind)")
    if st["unknown"]:
        print(f"TESTS-UNREADABLE — {st['unknown']} runs whose result cannot be read (piped or chained without "
              f"`set -o pipefail` and no pass/fail line): a final `exit N` line from the script fixes this")
    agg = collections.defaultdict(lambda: collections.Counter())
    for r in runs:
        a = agg[r["label"]]
        a["n"] += 1
        a["t"] += r.get("counted", 0) or 0
        a["fail"] += r["status"] == "fail"
        a["rerun"] += r["rerun"]
        a["dup"] += r["dup"]
    for label, a in sorted(agg.items(), key=lambda kv: -kv[1]["t"])[:8]:
        print(f"TESTS-LABEL — {label}: {a['n']} runs, {h(a['t'])}, failed {a['fail']}, re-runs {a['rerun']}, "
              f"possible duplicates {a['dup']}")
    print("TESTS-NOTE — transcripts do not show CI: a local run of what CI already ran on the same commit is "
          "not detected here")
    return runs


# ── Outcome ──────────────────────────────────────────────────────────────────

def merged_prs(root, repos, w0, w1):
    """Merged PRs in [w0, w1) via gh: (list of (opened, merged, branch), error)."""
    d0 = dt.datetime.fromtimestamp(w0, dt.timezone.utc).strftime("%Y-%m-%d")
    d1 = dt.datetime.fromtimestamp(w1, dt.timezone.utc).strftime("%Y-%m-%d")
    prs = []
    for repo in (repos or [None]):
        cmd = ["gh", "pr", "list", "--state", "merged", "--search", f"merged:{d0}..{d1}", "--limit", "1000",
               "--json", "number,createdAt,mergedAt,headRefName"] + (["--repo", repo] if repo else [])
        try:
            res = subprocess.run(cmd, cwd=root or None, capture_output=True, text=True, timeout=120)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return None, f"gh not runnable: {exc}"
        if res.returncode != 0:
            return None, f"gh failed: {' '.join(res.stderr.split())[:160]}"
        for pr in json.loads(res.stdout or "[]"):
            mep = epoch(pr["mergedAt"])
            if w0 <= mep < w1:
                prs.append((epoch(pr["createdAt"]), mep, pr.get("headRefName") or ""))
    return prs, ""


def pctl(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(math.ceil(q * len(xs))) - 1)] if xs else 0


def scan_outcome(ts_list, rules, test_rules, w0, w1, opts, root):
    tu = time_use(ts_list, rules, test_rules, w0, w1)
    agent_s = tu["acc"]["working"] + tu["acc"]["jobs"] + tu["acc"]["dormant"]
    eff = tu["calendar"] - tu["op_union"]
    cost = sum(eq(classes(in_win(t))) for t in ts_list)
    units, source = None, ""
    if opts["units"] is not None:
        units, source = opts["units"], "given with --units"
    else:
        prs, err = merged_prs(root, [r for r in opts["repo"].split(",") if r], w0, w1) if (root or opts["repo"]) \
            else (None, "no project root")
        if prs is None:
            print(f"OUTCOME — units: not available ({err}). Per-unit figures need merged PRs or --units N; "
                  f"per-window figures only")
        else:
            nd = NON_DELIVERY + ([re.compile(opts["non_delivery"])] if opts["non_delivery"] else [])
            keep = [p_ for p_ in prs if not any(rx.search(p_[2]) for rx in nd)]
            units, source = len(keep), f"merged PRs ({len(prs) - len(keep)} non-delivery excluded)"
            if not prs:
                source += "; if this work is not delivered as PRs, give the unit count with --units N"
            cyc = [m_ - o_ for o_, m_, _ in keep]
            if cyc:
                print(f"OUTCOME-CYCLE — PR open → merge over {len(cyc)} PRs: median {h(pctl(cyc, 0.5))}, "
                      f"p90 {h(pctl(cyc, 0.9))}")
    print(f"OUTCOME-TOTAL — calendar {h(tu['calendar'])} | effective {h(eff)} | agent time {h(agent_s)} "
          f"(operator wait excluded) | cost {m(cost)} eq")
    if units is not None:
        print(f"OUTCOME — {units} units: {source}")
        if units:
            print(f"OUTCOME-PER-UNIT — {m(cost / units)} eq | {h(agent_s / units)} agent time | "
                  f"{h(eff / units)} effective duration")


# ── Trend by calendar bucket ─────────────────────────────────────────────────

def scan_trend_bucket(ts_list, bucket):
    rows = collections.defaultdict(lambda: {"turns": [], "main": 0.0, "sub": 0.0})
    for t in ts_list:
        for d in in_win(t):
            day = dt.date.fromisoformat(d["ts"][:10])
            key = day.isoformat() if bucket == "day" else "%04d-W%02d" % day.isocalendar()[:2]
            r = rows[key]
            r["turns"].append(d["ctx"])
            r["sub" if t.is_sub else "main"] += eq(classes([d]))
    for key in sorted(rows):
        r = rows[key]
        x, tot_ = r["turns"], r["main"] + r["sub"]
        print(f"TREND — {key} turns={len(x):<5d} avg={int(sum(x) / len(x) / 1000)}k peak={int(max(x) / 1000)}k | "
              f"main={r['main'] / 1e6:.1f}M sub={r['sub'] / 1e6:.1f}M total={tot_ / 1e6:.1f}M eq "
              f"(sub {int(r['sub'] / tot_ * 100) if tot_ else 0}%)")


# ── Main ─────────────────────────────────────────────────────────────────────

def main(argv):
    global WIN_OK
    opts = parse_args(argv)
    scan = opts["scan"]
    if scan not in ("trend", "cost", "cache", "agents", "pauses", "time", "tests", "outcome", "summary",
                    "errors", "loops", "expensive", "trialerror", "all"):
        print(f"Unknown scan type: {scan}", file=sys.stderr)
        sys.exit(1)
    wfrom, wuntil = opts["from"], opts["until"]
    WIN_OK = lambda ts: (not wfrom or ts[:19] >= wfrom) and (not wuntil or ts[:19] < wuntil)
    files, jdir, root = find_files(opts)
    pattern_file = opts["patterns"] or os.environ.get("SCAN_PATTERNS", "") or (
        os.path.join(root, ".claude", "scan-patterns.tsv") if root else "")
    rules, n_project, test_rules = load_rules(pattern_file)
    ts_list = [t for t in (load(f, jdir, (wfrom, wuntil)) for f in files) if t.has_window_line]
    if not ts_list:
        sys.exit("No JSONL files found.")
    w0, w1 = window_bounds(ts_list, wfrom, wuntil)
    if opts["json"]:
        if scan == "pauses":
            return scan_pauses(ts_list, rules, opts["include_main"], not jdir, as_json=True)
        if scan == "tests":
            return scan_tests(ts_list, test_rules, w0, w1, as_json=True)
        sys.exit("--json works with the pauses and tests scans")

    if scan in ("trend", "agents", "pauses", "cache", "summary", "cost", "outcome", "all"):
        print(f"WEIGHTS — in={W_IN:g} cw5={W_CW5:g} cw1h={W_CW1H:g} out={W_OUT:g} | cache read: "
              f"{CR_TABLE or '(no per-model overrides)'}, else {W_CR_DEFAULT:g}")
    if scan in ("pauses", "cache", "cost", "time", "tests", "outcome", "all"):
        print(f"RULES — rebuild: >{REBUILD_RATIO:g} of context written | miss: rebuild after a gap past the "
              f"lifetime (5m, or 1h when most of the write is 1h), or after a shorter gap reading back "
              f"<{PREFIX_LOST_RATIO:g} of the previous context | pause: tool call of {PAUSE_MIN // 60}–"
              f"{PAUSE_MAX // 60} min | patterns: {n_project} project rules"
              f"{' from ' + pattern_file if n_project else ''} + {len(DEFAULT_RULES)} pause and "
              f"{len(DEFAULT_TEST_RULES)} test defaults")
    if wfrom or wuntil:
        print(f"WINDOW — from={wfrom or 'start'} until={wuntil or 'end'} (UTC)")
        for t in ts_list:
            if t.is_sub:
                continue
            before = sum(1 for d in t.turns if wfrom and d["ts"][:19] < wfrom)
            after = sum(1 for d in t.turns if wuntil and d["ts"][:19] >= wuntil)
            if before + after:
                print(f"WINDOW-SPAN — session {t.session[:8]} has {before} turns before --from and {after} "
                      f"at/after --until: it is shared with an adjacent window. Check that window does not "
                      f"overlap this one")

    single = not jdir
    if scan == "trend":
        return scan_trend_bucket(ts_list, opts["bucket"]) if opts["bucket"] else scan_trend(ts_list, bool(wfrom))
    if scan == "time":
        return scan_time(ts_list, rules, test_rules, w0, w1)
    if scan == "tests":
        return scan_tests(ts_list, test_rules, w0, w1)
    if scan == "outcome":
        return scan_outcome(ts_list, rules, test_rules, w0, w1, opts, root)
    if scan == "agents":
        return scan_agents(ts_list)
    if scan == "pauses":
        return scan_pauses(ts_list, rules, opts["include_main"], single)
    if scan == "cache":
        return scan_cache(ts_list, rules)

    files_out = ts_list
    if opts["top"]:
        # The N most expensive transcripts in the window, most expensive first.
        files_out = sorted(ts_list, key=lambda t: -eq(classes(in_win(t))))[:opts["top"]]
    for t in files_out:
        print(f"=== {t.rel} ===" + (f" ({m(eq(classes(in_win(t))))} eq"
                                     f"{', ' + t.agent_type if t.is_sub else ', main session'})" if opts["top"] else ""))
        if scan == "summary":
            scan_summary(t)
        elif scan == "cost":
            scan_cost(t, rules)
        elif scan == "errors":
            scan_errors(t)
        elif scan == "loops":
            scan_loops(t)
        elif scan == "expensive":
            scan_expensive(t)
        elif scan == "trialerror":
            scan_trialerror(t)
        else:
            scan_cost(t, rules)
            print()
            scan_errors(t)
            print()
            scan_loops(t)
            print()
            scan_expensive(t)
            print()
            scan_trialerror(t)
        print()
    if scan == "all" and not single:
        print("=== subagents by type ===")
        scan_agents(ts_list)
        print()
        print("=== pauses ===")
        scan_pauses(ts_list, rules, opts["include_main"], single)
        print()
        print("=== cache ===")
        scan_cache(ts_list, rules)
        print()
        print("=== time ===")
        scan_time(ts_list, rules, test_rules, w0, w1)
        print()
        print("=== tests ===")
        scan_tests(ts_list, test_rules, w0, w1)


WIN_OK = None

if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except BrokenPipeError:
        pass

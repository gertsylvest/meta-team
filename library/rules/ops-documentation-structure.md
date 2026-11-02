# Ops Documentation Structure

This rule tells an ops team where each kind of document lives and what shape it takes, so that the
next agent, often a headless one reading cold, can find the current state of an environment and the
procedure to act on it without asking. An ops team works in continuous flow (runbooks, a change log,
incidents, and a board of open work), not in sprints, so this rule replaces the development
`documentation-structure.md` for ops projects. It has no sprint results, no retrospective files and no
milestone plan. The Ops Improvement Review in `ops-ways-of-working.md` is the improvement loop.

## The "documentation folder"
1. The "documentation folder" holds written documentation created by the orchestrator or any subagent, and MUST BE stored under `@/documentation`.
2. `@/documentation` is organised into purpose sub-folders (see "Folder Layout" below). Pick the sub-folder that matches a document's purpose rather than writing loose files at the documentation root.
3. It is ok for the orchestrator or subagents to create further sub-folders to improve the structure.
4. Every document is a **markdown file in this repo, committed to git**. A document that lives only in a chat answer, a scratch file outside the repo, or an external authoring service is invisible to the next session and to other teams. Use an external document surface only when the operator names it in the request.

## Documentation Index
`@/documentation/INDEX.md` is the read-first entry point: a short map that points to the environments registry, the key runbooks, and what lives in each sub-folder. Agents SHOULD consult it to orient themselves before reading or writing docs. The orchestrator keeps it current when a sub-folder, a key runbook, or a living infra document is added, moved, or retired. Individual change-log entries, incident notes and tasks do NOT warrant an INDEX.md update; their folders are self-describing by filename.

A sub-folder that holds more than one kind of thing (for example `metrics/`, with hand-written logs beside generated reports) carries its own `README.md` table: path, what it is, who writes it.

## Folder Layout
The `--type ops` bootstrap creates the first five folders and seeds `metrics/build-deploy-metrics.md` and `infra/environments.md`. The rest are created when first needed.

- `runbooks/` — one runbook per repeatable procedure (`<subject>.md`). The canonical scripts, unit files and config a runbook installs live in `runbooks/assets/<runbook-name>/`, so the runbook and the thing it applies are reviewed together. Diagram sources go in `runbooks/diagrams/`.
- `change-log/` — append-only, **one file per change**, named `YYYY-MM-DD-<slug>.md`, with the frontmatter defined in `ops-ways-of-working.md` → Change Log.
- `incidents/` — one note per incident, named `YYYY-MM-DD-<slug>.md`.
- `infra/` — `environments.md` (the environments registry, the single living source of truth for what exists and what version is live), plus specs, posture documents, security reviews, and `staged/` for configuration prepared but not yet applied.
- `metrics/` — `build-deploy-metrics.md` (the hand-kept metrics log, orchestrator-owned), any studies, and generated reports. See "Metrics" below.
- `tasks/` — the kanban board, if the project uses taskmd (see "Tasks" below).
- `design-notes/` — per-decision design notes for changes larger than a single runbook edit.
- `spikes/` — investigation and prototyping write-ups and their outcomes.
- `improvement/` — inputs to and outcomes of the Ops Improvement Review, when they outgrow a line in the metrics log.
- `operator-profile.md` — the Signal Capture Log (see `ops-ways-of-working.md` → FOR ORCHESTRATOR ONLY).
- `roadmap.md` (optional) — where the platform and the team's operating posture are heading, staged by observable triggers rather than dates. It covers the ops/infra axis only; a product roadmap owned elsewhere is referenced, never copied.

**Archiving**: a retired runbook or superseded spec moves to an `archive/` sub-folder of its folder, with a one-line note at its top naming what replaced it. Change-log entries and incident notes are never archived, moved or rewritten.

## Document types

- **Runbooks declare the five fields in `ops-ways-of-working.md`**: trigger, idempotent steps, success criteria, failure/remediation path, approval requirement. Write the steps so a headless agent can execute them. When a runbook's procedure changes, edit the runbook in the same change and record it in the change log; do not leave the corrected procedure only in a change-log entry.
- **Change-log entries record what happened, not what is**: what changed, when, which runbook, the outcome, autonomous or operator-initiated, and the artifacts and rollback target involved. They are a historical record. A later correction is appended as a dated note in the entry, never a silent rewrite.
- **Incident notes open with status and severity**: then a summary, a UTC timeline, the cause (or "unexplained", stated plainly, with what is and is not established), the mitigation, and follow-ups. Each follow-up becomes a task or names the runbook it changed.
- **Infra documents say whether they are living or point-in-time**: a living document (the registry, a current spec) carries a status line saying so and is kept true. A point-in-time document (a review, a posture snapshot) carries its date in its filename or first line and is not updated afterwards; a newer review supersedes it and links back. When part of a living document is superseded, mark that part as superseded rather than deleting it, and say where the current version is.
- **One canonical copy, pointers elsewhere**: a long-lived list or config (a deny list, an allow-list, a host inventory) is kept in exactly one place, and every other document points to it. Two copies drift, and nothing tells a reader which one is current.

## Historical vs operational documents
Every document is either **historical** (change-log entries, incident notes, closed tasks, point-in-time reviews) or **operational** (runbooks, `environments.md`, living specs, open tasks, scripts). Historical documents are left as written. Operational documents are read as instructions for what to do now and MUST be kept true. This is the split used by the identifier-change and target-change rules in `ops-ways-of-working.md`.

## Metrics
`metrics/build-deploy-metrics.md` is the hand-kept log, governed by the 80/20 rule in `ops-ways-of-working.md`. Machine output that a collector can regenerate (daily CSVs, caches) may be kept out of git, provided the generated **reports** that carry the figures are committed and the metrics `README.md` says where the raw data lives and how it is rebuilt. Reports carry aggregates only: no transcript text and no secret values.

## Tasks
Open ops work is tracked as tasks with the **`taskmd` CLI** per `@.claude/rules/taskmd-cli.md`, in `@/documentation/tasks/` (`.taskmd.yaml`: `dir: ./documentation/tasks`). Tasks MUST NOT use the Claude internal task system.

The board is **kanban, not sprints**: statuses are the columns (`pending → in-progress → in-review → completed`, with `blocked` and `cancelled` as side states), work is pulled with `taskmd next`, and the board is viewed with `taskmd board`. No sprint tasks and no `sprint-NN` tags. Tag tasks by area (`deploy`, `security`, `infra`, `metrics`) and by requesting team where one exists.

A task tracks that work is open; the runbook holds the procedure and the change log holds the outcome. A change-log entry names its task in its `task:` field, and a task is completed only when its change-log entry exists. Follow-ups from incidents and from the Ops Improvement Review become tasks.

## Lead with the value driver (document fly-in)

Every runbook, design note, spike write-up, incident note, and infra spec or review MUST open with a short **fly-in**: a few lines of plain prose immediately after the H1, before any mechanism or provenance, so that a reader knows within the first ~5 lines what the document is for. Write it as ordinary sentences (no field labels), covering in this order:

1. **The outcome / value**: what this keeps working, prevents, or makes possible (the *"so that…"*), not the mechanism.
2. **Today → target**: where things stand now, and where this moves them (for an incident: the impact and the current status).
3. **What this document is**: a procedure to run, a decision to ratify, a review verdict, an incident record, and its scope boundary.

Provenance (task IDs, dates, who asked), decision logs and history come **below** the fly-in. The body can and should stay dense and implementation-grade for its primary audience, other agents.

Mechanism-first opening (avoid):

> # Runbook — threshold-gated reap of regenerable caches
> Task 12. A systemd timer fires hourly and runs a script that checks `df` and, above 80%, removes…

Value-driver first (prefer):

> # Runbook — threshold-gated reap of regenerable caches
> Keeps the build host's root disk out of pressure, so builds and agent sessions do not fail on a full disk. Today the existing prune layers free nothing while root sits above 80%; this adds the caches that actually fill it. This is the operational runbook and holds the canonical script and units; it does not replace the per-repo prune hooks.

## Project Documentation
- Information that backs up or is important for understanding key decisions must be written in a very short and concise way to a markdown file under the appropriate `@/documentation/` purpose sub-folder (a design decision → `design-notes/`; a resolved investigation → `spikes/`; a security review → `infra/`).
- Logically separated parts of the control-plane repo that can be worked on with limited context from the rest (a monitoring-as-code folder, a scripts or tooling folder, an installable unit set) MUST have a **README.md** at their root, giving an agent the structure, key files, how it is applied, and its dependencies on anything outside the folder.
- **Diagrams and tables** in any markdown doc MUST follow the `markdown-diagrams-tables` skill (`.claude/skills/markdown-diagrams-tables/`): box/flow diagrams are **generated** from a committed D2 source (never hand-drawn ASCII, which drifts out of alignment), and pipe tables are normalized with Prettier so they render correctly. The author picks ASCII (default) or Mermaid per diagram — neither is forced.
- **Secrets never appear in documentation**: reference a secret by name and location, never by value (`secrets-handling.md`).

## Project Root README
Every project folder MUST have a `README.md` at the project root that:
- Briefly describes the top-level folder structure (what each folder is for)
- Points out key documents (the environments registry, INDEX.md, the most-used runbooks, the roadmap if there is one)
- Notes any separately applied tooling folders (monitoring-as-code, installable units)
- Is written for an audience of Claude or an engineer wanting a quick structural orientation — not end-user documentation

The orchestrator updates it if and only if the top-level folder structure changes or a new key living document is added. Routine activity (change-log entries, incidents, tasks, runbook edits) does NOT warrant updating the README.

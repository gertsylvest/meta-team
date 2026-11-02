# Standing Backlog

> **What this is:** the project's live pool of **triaged, actionable, not-yet-scheduled** work —
> reported defects and small enhancements/chores that should feed a future sprint but aren't part of
> any current one. It exists so sprints can be **planned from reported work**, not only from the
> forward roadmap.

## Source of truth = taskmd (tag `backlog`)

The backlog is **not a hand-maintained table** (which drifts) — it *is* taskmd. Every backlog item is a
task tagged **`backlog`**. Query and plan from it:

```bash
taskmd list --filter tag=backlog                       # the whole standing pool
taskmd list --filter tag=backlog --filter tag=bug      # just reported defects
taskmd list --filter tag=backlog --filter priority=high
```

Because the `backlog` tag is **removed when an item is pulled into a sprint** (see Graduation below),
`tag=backlog` always means "still unscheduled" — no status filter is needed to read the live pool.

## Tag & priority convention

| Dimension    | How it's recorded                    | Values |
|--------------|--------------------------------------|--------|
| In the pool  | tag `backlog`                        | present = unscheduled; removed on graduation |
| Type         | tag                                  | `bug`, `enhancement`, `chore`, `spike` |
| Severity     | `--priority`                         | `critical` (broken/unusable), `high` (wrong behaviour w/ workaround), `medium` (rough edge), `low` (polish) |
| Source       | optional free tag (project-defined)  | e.g. `live-test`, `<surface>`, `<component>` |

## Intake (who: the PM; see ways-of-working.md → Standing Backlog)

For each reported item:

1. `taskmd add "<concise symptom or ask>" --priority <sev> --tags backlog,<type>[,<source>] --format json`
2. Read the `file_path` from the JSON, then Edit the task to fill:
   - `## Objective` — for a **bug**: observed vs expected, repro steps, and the surface (which
     screen/module/input). For an **enhancement/chore**: the ask and its motivation. For a **spike**
     (research/investigation catch-all): the question to answer and what a useful outcome looks like.
   - `## Acceptance Criteria` — a real, checkable definition of done (never leave the `TODO` placeholder).
3. Set **priority by severity** so triage can rank. Severity is the operator's steer; when unstated, the
   PM proposes one and flags it for confirmation.

Filing a *pending, unscheduled* backlog task is an allowed always-on path. (What ways-of-working forbids
is creating tasks *after the fact* to describe work already completed — that's different.)

## Graduation into a sprint

At sprint planning the PM treats `taskmd list --filter tag=backlog` as a candidate pool alongside the
milestone plan and the retro carry stream, triages by priority, groups related items, and proposes a
scope for operator approval. When an item is pulled into a sprint:

```bash
taskmd set <task-id> --remove-tag backlog --add-tag sprint-NN
```

The **type tag stays** (`bug`/`enhancement`/`chore`/`spike`) so the item remains queryable historically
after it closes; only the `backlog` (=unscheduled) marker is dropped.

A **`spike`-type** entry is an *un-scheduled* research/investigation idea. When it graduates it becomes
sprint-attached spike task(s) per ways-of-working (spikes are always tied to a specific sprint) — the
backlog entry is where the idea waits until then.

## Relationship to the retro carry stream

Peer-review **nits** and retro **carry items** stay in their own flow (the carry stream in the sprint
result doc) — that stream is for **internal-quality** follow-ups. This backlog is for **reported product
work**. A carry item that turns out to be a user-visible defect may be re-tagged into the backlog
(`--add-tag backlog,bug`); conversely a backlog item isn't a carry item.

> Development-project concept. Ops projects track this via `documentation/incidents/` + `change-log/`
> instead (no taskmd).

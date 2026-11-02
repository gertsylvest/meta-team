# Documentation Structure

## The "documentation folder"
1. The "documentation folder" holds written documentation created by any subagent, and MUST BE stored under @/project-docs
2. `@/project-docs` is organised into purpose sub-folders (see "Folder Layout" below). Pick the sub-folder that matches a document's purpose rather than writing loose files at the project-docs root.
3. It is ok for the orchestrator or subagents to create further sub-folders to improve the structure

## Documentation Index
`@/project-docs/INDEX.md` is the read-first entry point to all non-source-code documentation: a map that points to each key document and summarises what lives in each sub-folder. Agents SHOULD consult INDEX.md first to orient themselves before reading or writing docs. INDEX.md MUST be kept current whenever documents are added, moved, or retired — the orchestrator and PM own this maintenance (the PM reviews it as part of the Sprint End Workflow).

## Folder Layout
`@/project-docs` is organised into purpose sub-folders. Several carry an `archive/` sub-folder for superseded or historical material:
- `architecture/` — `architecture.md` (key architecture, technical design, tech stack, and the **Testing and Feedback Strategy**) and `design-vision.md` (design vision, goals and anti-goals), plus related companion docs. Has `archive/`.
- `project/` — `milestone-plan.md` (high-level design and implementation milestone plan), `issue-backlog.md` (the standing-backlog convention — see ways-of-working.md → Standing Backlog), and other project-level planning/decision docs. Has `archive/`.
- `design-notes/` — per-feature or per-decision design notes. Has `archive/`.
- `spikes/` — research and prototyping spike write-ups and their outcomes. Has `archive/`.
- `specs/` — `development-environment.md` (key decisions on the development environment, updated continuously) and other frozen contracts or specifications. Has `archive/`.
- `notes/` — informal working notes that do not yet warrant a structured home.
- `resources/` — external references, source captures, and supporting material.
- `sprint-outcomes/` — one sprint result file per sprint (the retrospective is a section within it — see "Sprint Results").

**Archiving**: the orchestrator or PM SHOULD occasionally move superseded, resolved, or stale documents into the relevant `archive/` sub-folder so the active folders stay focused on current material. Update INDEX.md whenever archiving.

## Sprint Definition
"Sprints" are defined using a special "sprint task" created with the taskmd CLI (`taskmd add` — see `taskmd-cli.md`), which must include:
- the **sprint number**
- a **sprint objective**
- a set of **desired outcomes** or deliverables
- a **definition of done** which could include e.g. the fidelity of the solution
- a short **sprint description**
- a tag "sprint-{{sprint_number}}", to enable searching and filtering within a specific sprint

## Tasks
"Tasks" (including the "sprint" tasks) MUST be documented with the taskmd CLI (`taskmd add`, `taskmd list`, `taskmd get`, `taskmd set`, `taskmd next`, `taskmd validate` — `taskmd-cli.md` is the authoritative cheatsheet). They MUST NOT use the claude internal task system.

## Project Plan
The "Project plan" MUST have the following documents, stored under @/project-docs:
    - @/project-docs/specs/development-environment.md holds key decisions on the development environment, updated continuously.
    - @/project-docs/architecture/architecture.md holds key decisions on architecture, technical design (such as interface design), tech stack, and the project's **Testing and Feedback Strategy** (see ways-of-working.md).
    - @/project-docs/project/milestone-plan.md holds the high-level design- and implementation milestone plan, which is iteratively updated.
    - @/project-docs/architecture/design-vision.md holds the design vision, goals and anti-goals.

**Plan ownership follows repo ownership**. A plan is owned by the repo that
owns the work it sequences. A repo that *consumes* that work keeps a **pointer** to the owner's plan —
never a fork of it. Where a portfolio or program roadmap sequences across repos, it is owned by the
umbrella repo and referenced from here, and `milestone-plan.md` in this repo covers **this** project's
own milestones underneath it. The failure this prevents is slow and quiet: a forked plan stays
plausible while the owner's moves on, and the two then contradict each other with no way to tell from
either one which is current. The same applies to any long-lived list that sequences another repo's
work (a language backlog, a device roadmap): pointer, not copy. When ownership moves, the plan moves
with it, and whatever is left behind becomes a pointer in the same change.

## Lead with the value driver (document fly-in)

Every architecture doc, design note, spike write-up, or ADR MUST open with a short **fly-in** — a few lines of plain prose placed immediately after the H1, before any mechanism, provenance, or technical exposition — so that a reader knows *within the first ~5 lines* what the document wants to achieve and why it matters. Write it as ordinary sentences (no field labels or headings), but make sure it covers, in this order:

1. **The outcome / value** — the real-world capability or end-user outcome this drives, or the problem it removes (the *"so that…"*), not the mechanism.
2. **Today → target** — where things stand now, and where this moves them.
3. **What this document is** — a decision to ratify, a build spec, a spike result, etc. — and its scope boundary.

Provenance (ask/task IDs, sprint numbers, dates), decision logs, historical context, and the technical design all come **below** the fly-in. They orient other agents but are not the value driver, and must never be the first thing a reader hits. The fly-in is a signpost, not a summary — a few sentences. The remaining body can and should stay dense and implementation-grade for its primary audience (other agents); the fly-in is the one part written so a non-immersed reader (the operator, or a freshly-spawned agent) grasps intent immediately.

Mechanism-first opening (avoid) — the title *is* the solution and the first line is provenance:

> # Split notification pipeline — transactional queue vs digest batcher
> Task 112 (architect-owned). This note formalizes the proposal from the sprint 9 review to split notification delivery into two logical queues…

Value-driver first (prefer) — same content, same jargon, but the driver leads:

> # Split notification pipeline
> Gets password-reset and order-confirmation emails to users within seconds even during a marketing send — today one queue carries both, so a large digest batch delays the transactional mail behind it. This note proposes splitting that one queue into two (transactional vs digest); it is a ratification target, not a build spec, and covers queue routing only. (Origin: task 112, sprint 9 load test — see decision log below.)

## Project Documentation
- Information that backs up or is important for understanding key decisions must be written in a very short and concise way to a markdown file under the appropriate `@/project-docs/` purpose sub-folder (a per-feature design note → `design-notes/`; a resolved research spike → `spikes/`; an external reference → `resources/`; informal working notes → `notes/`). 
- Logically separated modules of the solution (i.e. code sections that can be worked on with limited need for context outside of the module or the "project plan") MUST have a **README.md** at their root, that provides enough context to quickly for an agent to understand the module structure, key folders, and key dependencies to entities outside of the module.
- **Diagrams and tables** in any markdown doc MUST follow the `markdown-diagrams-tables` skill (`.claude/skills/markdown-diagrams-tables/`): box/flow diagrams are **generated** from a committed D2 source (never hand-drawn ASCII, which drifts out of alignment), and pipe tables are normalized with Prettier so they render correctly. The author picks ASCII (default) or Mermaid per diagram — neither is forced.

## Sprint Results
Each sprint produces a **single** sprint result file — the retrospective is a section within it, **not a separate file**. It MUST be stored in `@/project-docs/sprint-outcomes/`; create this folder if it does not yet exist.

"sprint result" files are named "sprint-{{sprint_number}}-result.md" and MUST include:
- A short description of the outcomes of the sprint
- List any shortcomings (tasks that were deferred, achieved only partially, or that did not meet their completion criteria, and so on)
- A short description of how to demonstrate the outcomes of the sprint, e.g. via an automatic test or manual test file, or user instructions on how to validate the outcome.
- The **carry stream** — a "Deferred from retrospective" and/or "Dropped from retrospective" section carrying every recommendation not adopted this sprint (see "Carry-forward discipline" below).
- A **## Retrospective** section (see below).

### Retrospective section
The PM writes the retrospective as a section of the sprint result file, from input each agent supplies **inline when it reports its sprint work complete** (the `request: sprint work done` signal — see ways-of-working.md), while the work is still fresh. The PM does NOT run a separate cold solicitation round. The section covers:
- **Effort-saving opportunities — the ONLY feedback solicited from each agent** (replacing the former start/stop/skill/suggestion grid, which produced mostly un-actioned boilerplate). Each agent reports *if and only if* it sees an opportunity to save **significant** effort through a **skill or a script** that would eliminate **repeat work** it hit this sprint (repetitive, trial-and-error, or many-step manual sequences that recur). These are concrete build proposals, not general observations — an agent with nothing substantial to report says "nothing this sprint". No fixed section grid is filled in.
- **PM curation → build-or-drop carry stream.** The PM is the filter: the PM MAY decline to surface an agent's recommendation if it is not substantial enough to be worth building (record the decision in one line). Every recommendation the PM *does* surface MUST enter the **carry stream** (the "Deferred from retrospective" ledger above) as a **build-or-drop** item — it is either **built** (a task is created for it) or **dropped** (with a reason); it may not persist as a vague suggestion.
- **Mascot consult (optional, by exception).** Where a mascot agent is on the team, the PM MAY consult it for a fresh perspective — reserved for oracle-worthy moments (nearing a major milestone, or an unusually difficult sprint), not every sprint. See ways-of-working.md.

### Carry-forward discipline
The carry stream is retained in full: each surfaced build-item notes its carry-over count on its first line, and **any item carried 3 times MUST be escalated to the operator for an explicit build-or-drop decision** rather than being quietly carried a 4th time. This running count is how repeated slippage stays visible without a separate tracking file.

## Project Root README
Every project folder MUST have a `README.md` at the project root that:
- Briefly describes the top-level folder structure (what each folder is for)
- Points out key documents (e.g. architecture, design vision, milestone plan, latest sprint outcome)
- Notes any separate compilation units or significant submodules
- Is written for an audience of Claude or a developer wanting a quick structural orientation — not end-user documentation

The PM MUST review this file as part of the Sprint End Workflow and update it if and only if:
- The project's top-level folder structure has changed (new or removed folders)
- New key technical design documents or architectural decisions have been added

Routine sprint activity (new sprint result files, task changes, minor code additions) does NOT warrant updating the README.


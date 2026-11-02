---
name: orchestrator
description: Managing and growing the meta-team library; bootstrapping new projects from it.
model: fable
memory: local
tools:
  - Read
  - Write
  - Edit
  - Grep
  - Glob
  - Skill
  - Bash
  - WebFetch
  - WebSearch
  - get-task-status
  - update-task
  - split-task
  - verify-task
  - next-task
  - add-task
  - validate-tasks
  - do-task
  - get-task
  - complete-task
  - list-tasks
---
# Project description

This is the meta-team project — a curated library of agents, orchestrators, skills, rules, and team definitions that can be used to bootstrap new Claude Code projects.

The workflow has two modes:
1. **Library mode** — defining and refining new agents, orchestrators, skills, rules, and teams, adding them to the library when ready
2. **Bootstrap mode** — interactive conversation to understand a new project's needs, then running a script to scaffold that project from the library

## Machine-local instructions

Instructions specific to one machine or to the operator's own portfolio of projects (repo names, credential flows, local paths, which projects exist) do **not** belong in this file. They live in a local rule under `.claude/rules/` that is not published. This file must read correctly without that rule: where a local rule exists, it overrides the defaults stated here.

## Optional: private source, public curated mirror

A library can be kept in a private repo, with a curated subset snapshot-published to a separate public repo. The public repo is never edited directly.

- **What's published**: only files listed in `.publish-manifest` at the repo root.
- **How to publish**: run `./scripts/publish.sh "<commit message>"`. The script clears the public worktree (`$META_TEAM_PUBLIC_ROOT`) and re-snapshots from the manifest, then commits and pushes. It refuses to publish if a manifested file matches a pattern in `.publish-denylist` (internal names and paths, kept private).
- **Preview without committing**: `./scripts/publish.sh --diff` shows what would change.
- **To expose a new file publicly**: add a line to `.publish-manifest`, then publish.
- **To remove a file from public**: delete the line from `.publish-manifest`, then publish. The next snapshot will not include it.

When a new agent, skill, rule, or other library file is created, it is **private by default**. Promoting it to the public mirror requires an explicit manifest edit + publish.

## Folder Structure

### Library (`/library`)
The gold-standard, curated definitions. Only promoted, reviewed files live here.

- `/library/agents/` — agent definition files (subagents)
- `/library/orchestrators/` — orchestrator profile files (choose one per project)
- `/library/skills/` — skill definitions, each in a subfolder: `/library/skills/{{skill_name}}/SKILL.md`
- `/library/rules/` — rule files
- `/library/teams/` — team definition files, named descriptively: `/library/teams/{{team_name}}.md` (e.g. `dev-team.md`, `research-team.md`)
- `/library/documentation/` - documentation of the "meta-team" project and resources

### Workspace (`/workspace`)
Temporary staging area for drafts being evaluated. Files here are not gold-standard yet.
Same structure as `/library` (teams are flat files: `workspace/teams/{{team_name}}.md`). Once approved, files are promoted to `/library`, and removed from the workspace folder structure

- Do NOT delete or overwrite workspace files unless they have been promoted to library, or until explicitly asked
- Before writing a new file, check for filename conflicts and add a number suffix if needed

### Templates (`/templates`)
- `/templates/CLAUDE.md` — base CLAUDE.md template used when bootstrapping new projects

### Scripts (`/scripts`)
- `/scripts/new-project.sh` — interactive script to scaffold a new project from the library

## Working in Library Mode

### New agent definition
1. Engage until the agent's role and traits are clear
2. Research best practices or examples online if helpful
3. Consider whether some traits belong in rules or skills instead — suggest this if so
4. Use `/library/agents/pm.md` as the default template unless the operator prefers another
5. Write the draft to `/workspace/agents/` and ask for confirmation
6. Iterate based on feedback, then promote to `/library/agents/` when approved

### New orchestrator definition
1. Engage until the orchestrator's profile and scope are clear
2. Use an existing orchestrator in `/library/orchestrators/` as a reference if available
3. Write the draft to `/workspace/orchestrators/` and ask for confirmation
4. Iterate based on feedback, then promote to `/library/orchestrators/` when approved

### New rule definition
1. Engage until the rule's intent is clear
2. Use `/library/rules/documentation-structure.md` as the default template
3. Write the draft to `/workspace/rules/` and ask for confirmation
4. Iterate, then promote to `/library/rules/` when approved
5. **Rule-agent pairing**: if the rule is specific to a particular agent type or workflow rather than the whole project, consider embedding it directly in those agent files instead of keeping it as a standalone rule.

### New skill definition
1. Engage until the skill's purpose and steps are clear; research and find scripts if relevant
2. Use the existing skill structure in `/library/skills/` as a reference
3. Write draft to `/workspace/skills/{{skill_name}}/SKILL.md` and ask for confirmation
4. Iterate, then promote to `/library/skills/` when approved
5. **Skill-agent pairing**: if the skill is specific to a particular agent type, add it to the `skills:` frontmatter field of the relevant agent file(s) in `/library/agents/` at the same time. The bootstrap script reads this field to auto-include skills when those agents are selected — an unlinked skill will silently be omitted from bootstrapped projects.

### New team definition
1. Engage until the team composition is clear
2. Reference the agents and orchestrator the team will use
3. Write draft to `/workspace/teams/{{team_name}}.md` and ask for confirmation
4. Iterate, then promote to `/library/teams/{{team_name}}.md` when approved
- Note: team files are named descriptively in the library (e.g. `dev-team.md`). When deployed to a project, the script copies the file to `.claude/rules/teams/team-definition.md` — the `teams/` subfolder is auto-loaded by Claude Code (rules are discovered recursively), and the consistent filename allows agent `@` imports to resolve correctly.

### Keeping deployed projects current

A library change reaches a deployed project **only** when someone hand-carries it as a delta — nothing
pushes, and the project cannot tell it is behind.

- Find candidates by comparing the library's rule markers (every bolded rule title and `###` heading)
  with each project's deployed copy. Derive the markers from the library files, never from a
  hand-maintained list, which would be blind to any rule nobody remembered to add to it.
- A missing marker is a **candidate, not a defect**: a project that adopted a rule *in its own words*
  looks identical to one that never received it. Classify each hit as **lag** (send a delta) or
  **local adaptation** (leave it alone), and record deliberate divergences so the classification is
  not re-argued every time.
- Keep bold rule titles and headings stable when editing library rules — renaming one makes every
  deployed project look behind.
- Fixes go to the owning team as a message or PR — never by editing their tree (see
  `ways-of-working.md` → "Other teams do not edit this repo's tree").

## Working in Bootstrap Mode

When the operator wants to start a new project:

1. Ask for the project name (kebab-case), the parent directory (default: `~/dev`; use a subdirectory like `~/dev/<group>` for grouped projects), project type (development, research, ops, or custom), and a brief description of the project's purpose
2. Determine the project type — development, research, ops, or custom — and apply the rules below
3. Ask clarifying questions to understand the team needed: domain, workflows, key roles
4. Based on the answers, recommend an orchestrator from `/library/orchestrators/` and a set of agents, skills, and rules from the library
5. Present the proposed team composition and confirm with the operator
6. Run `/scripts/new-project.sh` with the project name, `--type development` or `--type research`, the `--purpose` description, and the selected files to scaffold the project — this generates the project CLAUDE.md from the template (including standard tool grants) and copies all selected library files
7. Set up the git repository (see **Git repository setup** below)
8. Report the new project path and what was created

### Git repository setup

Before running the bootstrap script, ask the operator which of the three git setups applies. The answer determines whether the script is used at all.

**What gets committed (single-developer mode).** The whole scaffold is committed to git — `CLAUDE.md`, `.claude/` (agents, rules, skills, and repo-local `memory/`), `project-docs/` (which now includes the `project-docs/tasks/` backlog — see **Task folder location** below). Only genuinely machine-local / ephemeral state is excluded via `.gitignore`: `.claude/settings.local.json` and `.DS_Store`. This is a deliberate reversal of the earlier multi-collaborator model (where each developer kept an independent local Claude setup and only shared code) — in single-developer mode the setup and backlog should travel with the repo (durability, cloud-box migration, reproducibility). This applies to **Options A and C** below (the operator's own repos). **Option B is the sole exception**: when working inside an upstream repo you do not own, the scaffold must stay out of that repo's history.

**Agent memory and git — commit the root tree, never a stray one.** Repo-local agent memory (`.claude/agent-memory-local/<agent>/`) is **committed**; that is the point of the decision above, and a project whose memory sits untracked is losing it on every box migration. The one exception is a **stray tree at a non-root path**: agent memory resolves against the **dispatch's cwd**, so a lane dispatched from a subdirectory silently writes a fresh tree there that no dispatch ever reads. The bootstrap `.gitignore` therefore carries `**/*/.claude/agent-memory-local/` — the leading `**/*/` requires at least one directory component, so the canonical root tree stays tracked while strays cannot be committed. Do **not** write `.claude/agent-memory-local/*/`, which ignores the root tree's per-agent folders and quietly ends committed memory altogether — the opposite of the intent. Pair the ignore with a detector that classifies **by path, not by `git check-ignore`** (e.g. a small stray-memory detector script run before staging): a detector keyed on ignoredness is made vacuous by the very ignore rule it is meant to complement, and the goal is for strays to be **visible**, not invisible.

**Task folder location (standard going forward).** The taskmd backlog lives **under the documentation folder**, not at the project root: `project-docs/tasks/` for development projects, and `.taskmd.yaml` points at `./project-docs/tasks`. (Ops projects keep their kanban board at `documentation/tasks/`, mirroring their doc-folder name.) Two reasons: now that tasks are git-committed they belong with the rest of the docs rather than as a separate top-level folder, and nesting them under the doc folder means a single sync of the documentation tree (e.g. cloud machine ↔ laptop) carries the backlog too. The bootstrap script does this automatically for `--type development` and `--type ops`.

---

**Option A — New repository (default):**

1. Run `/scripts/new-project.sh` as described above to create and populate the project folder (pass `--parent <parent-dir>` if the parent is not `~/dev`)
2. **Create the remote repository** — a **private** repository named `<project-name>` on the operator's account, e.g. `gh repo create <owner>/<project-name> --private`, or in the GitHub UI if the machine has no credential that can create repositories (a local rule says so where that applies).
3. Once the repo exists, initialize and commit locally:
   ```bash
   git -C <project-path> init -b main
   git -C <project-path> add -A
   git -C <project-path> commit -m "Initial commit"
   ```
   The scaffold is committed in full — the `.gitignore` the script wrote already excludes the only machine-local files (`.claude/settings.local.json`, `.DS_Store`), so a plain `git add -A` stages everything else correctly. Do **not** copy `git-info-exclude` for this option (that file is for Option B upstream clones only). (`init -b main` keeps the default branch explicit; if a repo comes up on `master`, rename with `git branch -m master main` before pushing.)
4. Add the remote and push:
   ```bash
   git -C <project-path> remote add origin https://github.com/<owner>/<project-name>.git
   git -C <project-path> push -u origin main
   ```
5. Report the new repo URL once pushed

---

**Option B — Clone existing repository:**

Use this when the project involves working inside an existing (e.g. upstream OSS) repository that should not have Claude scaffold files committed to it. Do NOT run `new-project.sh` for this option — the scaffold is created manually.

Steps:
1. Ask the operator for the repository URL, which branch to clone, and confirm the project path (default: `~/dev/<project-name>`, or a subdirectory like `~/dev/<group>/<project-name>`)
2. Create an empty project folder and clone into it:
   ```bash
   mkdir -p <project-path>
   git clone --branch <branch> <url> <project-path>
   ```
3. Copy `/meta-team/templates/git-info-exclude` to `.git/info/exclude` — this pre-lists all scaffold files and folders (`CLAUDE.md`, `.claude/`, `project-docs/` — which contains `tasks/` — and `.taskmd.yaml`) so the upstream repo stays clean without touching its `.gitignore`. If any additional files will be added to the project root beyond the defaults, add them to the exclude file before creating them.
4. Create the scaffold folders and copy the library files manually (do not run the script — the folder already exists and the script will abort):
   ```bash
   mkdir -p <project-path>/.claude/agents
   mkdir -p <project-path>/.claude/rules/teams
   mkdir -p <project-path>/project-docs/tasks
   ```
   Then copy agents, orchestrator, rules, and team definition from the library; copy `templates/settings-development.json` to `.claude/settings.json`; and write `CLAUDE.md` and `.taskmd.yaml` (`dir: ./project-docs/tasks`) directly.
5. Verify `git status` in the project folder shows no untracked files from the scaffold.

---

**Option C — Existing local repository (no clone needed):**

Use this when the operator already has the repo checked out locally and owns it (single-developer mode — the scaffold is committed, as in Option A).

1. Run `/scripts/new-project.sh` with `--parent <parent-dir>` if the project is not directly under `~/dev`, or copy files manually as in Option B
2. Ensure `.gitignore` excludes only `.claude/settings.local.json` and `.DS_Store` — the script writes this for a fresh project; if the repo already has a `.gitignore`, add those two lines if missing. Do **not** add scaffold files to `.git/info/exclude` — the scaffold is meant to be committed.
3. `git add -A` and commit; verify `git status` shows the scaffold staged (not ignored)

### Default skills (all project types)

Two skills are included in **every** bootstrapped project — development, research, ops, or custom — unconditionally by `new-project.sh`, independently of the agent-frontmatter skill auto-collection. Do **not** pass either via `--skills`; the script handles both.

- **`markdown-diagrams-tables`** — generates aligned ASCII/Unicode diagrams from committed D2 sources and normalizes pipe tables with Prettier, solving the recurring "boxes misaligned / tables don't render" problem. Every project writes markdown docs, so this is general infrastructure rather than a per-team opt-in. Its dependencies are D2 (the skill auto-installs it user-local under `~/.local/bin` if missing) and Prettier (run via `npx`, no install). The mandatory `documentation-structure` rule points at this skill for any doc containing a diagram or table.
- **`team-messaging`** — the file-based cross-team messaging channel (machine-wide infrastructure, shared by every team on the machine). On each run the script also:
- registers the team in the shared channel (single flat `inbox/` + a `teams` registry) under the channel root (`$MESSAGING_ROOT`, else the skill's default location), team name = project name;
- writes `env.MESSAGING_TEAM=<project-name>` into the committed `.claude/settings.json`, so the team knows its own identity (this is project identity, stable across machines — it belongs in `settings.json`, not `settings.local.json`). The settings template also wires the inbox **hooks** that auto-surface unread mail to the orchestrator before each turn and at session start (deliberately no blocking Stop hook — mid-turn mail surfaces on the next turn).

The channel spec **and** implementation — the channel-root layout, the `team-messaging` skill, and the inbox hooks — are **maintained in this library**. Changes to the channel model or the messaging/hook implementation are made here and propagated out. The sender a team stamps on a message **must** be a registered team — the `send` helper rejects an unknown sender so replies stay deliverable. If the channel root does not yet exist on a new machine, create it (`inbox/` + `teams`) and register the team before the skill can be used.

### Post-bootstrap: MCP servers

After the project folder and git repo are set up (any option), register the standard MCP servers for the project by running these commands with the new project as the working directory:

```bash
claude mcp add playwright npx @playwright/mcp@latest
```

This registers Playwright at the local user-config level scoped to the project (not committed). Add any other project-specific MCP servers the same way. For development projects using the interaction-designer or svelte-ui-engineer agents, Playwright is mandatory.

### Post-bootstrap: pin `env.PATH` (toolchain-heavy projects)

Fresh subagent shells are non-login and do not source the operator's shell profile, so they lose PATH entries for toolchains installed outside the system path — `cargo`/`rustc` (`~/.cargo/bin`, `~/.rustup/toolchains/.../bin`), `taskmd` and other Homebrew tools (`/opt/homebrew/bin`), `emsdk`/`node` for WASM. The symptom is agents prepending an `export PATH=…` preamble to every Bash call (hundreds of redundant retries over a project).

For development projects that build with such toolchains (anything Rust/WASM/C++, in particular), pin a full PATH superset in `.claude/settings.local.json` (machine-specific, **not** the checked-in `settings.json`):

```json
{ "env": { "PATH": "<full PATH superset incl. ~/.cargo/bin, toolchain bin, /opt/homebrew/bin, emsdk, node>" } }
```

Capture the operator's current PATH (`echo $PATH` in their login shell) as the basis. This fixes the toolchain-not-found problem once for all shells and subagents. Do **not** put machine-specific paths in `settings.json`.

---

### One team, several repos (the scaffold lives in the session root)

A team may own more than one repository. A second repo does **not** imply a second team: a team is a
**session, a backlog, and an operator relationship**, not a repo. Split a team only when the work has a
different cadence or a different person steering it — not because the code moved to a new remote.

The arrangement:

- **One session**, started in the **primary repo**, with the second repo added as a working directory
  (`permissions.additionalDirectories`, or `--add-dir` at launch). Set this explicitly rather than
  discovering it mid-task.
- **The full scaffold lives in the session root only** — `.claude/agents/`, `.claude/rules/`,
  `.claude/skills/`, `.claude/settings.json`. Agents, rules and skills resolve from the **session's**
  project directory, so a `.claude/` in the secondary repo is loaded by nobody. The hazard is not that it
  is inert, it is that it **looks authoritative**: a future session or reader finds agent and rule files
  there and reasons from them while the live ones are elsewhere and have moved on.
- **One messaging identity, belonging to the session** (`env.MESSAGING_TEAM` in the session root's
  `settings.json`). Do **not** register the secondary repo as a team: that creates a mailbox no session
  ever reads, so mail to it either dead-letters or sits unread with nothing telling the sender which.
- **One taskmd backlog**, in the session root, with a per-repo tag (`repo:<name>`) on every task.
- **The secondary repo gets**: a `README.md` with module-level context (the low-coupling rule applies per
  repo), its **own gates and CI** (gates are repo-local by design — per-repo CI is distinct from
  cross-repo integration), and a `.gitignore` including `**/*/.claude/agent-memory-local/`.
- **CLAUDE.md in the secondary repo: omit it, or make it a one-line pointer** ("worked from the `<primary>`
  session — instructions live there"). Whether a CLAUDE.md in an *added* working directory is auto-loaded
  is version-dependent and should not be depended on either way; a file that might or might not load is
  worse than none.
- **Never run a second session in the secondary repo.** Two sessions sharing one backlog is where this
  arrangement breaks. Reaching for that is a team split, and it needs a capacity tripwire with an owner
  and a check moment (the PM, at sprint planning) rather than a drift into it.

**Record the decision where the other teams look.** An arrangement settled over a live cross-session
message leaves no artifact. Write it into a committed record — this file, or the team definition — so
that other teams find it there, rather than relying on whoever relayed it or on a stale description
that happens to be in place.

### Development projects (mandatory rules)
Any project using a development team MUST always include these rules, regardless of the agents or orchestrator chosen:
- `ways-of-working` — defines sprint workflow, phases, and subagent signals
- `documentation-structure` — defines project documentation standards

These are non-negotiable for development projects. Do not ask the operator about them — just include them.

The bootstrap script also auto-includes the `git-history` rule for **development and ops** projects (merge, never rewrite pushed history — several agents, worktrees and CI runs share one remote). Do not pass it via `--rules`. Research projects do not get it.

The bootstrap script automatically sets up taskmd for development projects: a `project-docs/tasks/` folder (nested under the documentation folder and committed to git — the backlog travels with the repo), a `.taskmd.yaml` config pointing tasks there, and the `taskmd-cli` rule (an authoritative CLI cheatsheet that prevents agents from guessing at wrong flags). No additional taskmd configuration is needed.

### Research projects
Research projects MUST NOT include `ways-of-working` or `documentation-structure` rules. Do not add them even if they seem generally useful — they are development-specific and will add irrelevant overhead.

Research projects have a fixed default setup — do not ask the operator about agents, orchestrators, or skills. Just confirm the project name and a short research description (used for the project CLAUDE.md), then run the script:
- Orchestrator: `research-orchestrator`
- Agent: `researcher`
- Rules: none
- Skills: none

**Git setup**: Research projects default to **Option A** (new private GitHub repo). Proceed directly — do not ask the operator which option they want unless they indicate otherwise.

Unlike development projects, research project files (CLAUDE.md, `.claude/`, research subdirectories and findings) ARE the content and should all be committed. Do NOT use a `git-info-exclude` or exclude any project files. The only `.gitignore` entry to include is `.DS_Store`.

After running the script, create the private `<owner>/<project-name>` repository as in Option A above. Once it exists, set up the repo — note that unlike development projects, research projects commit **all** files:
```bash
git -C <project-path> init -b main
printf ".DS_Store\n" > <project-path>/.gitignore
git -C <project-path> add .
git -C <project-path> commit -m "Initial commit"
git -C <project-path> remote add origin https://github.com/<owner>/<project-name>.git
git -C <project-path> push -u origin main
```

The only things to confirm with the operator are the project name and research description. Everything else is fixed.

### Ops projects

Ops projects stand up a **standing operations / platform team** that runs and evolves a build-and-deploy pipeline plus managed servers. They are runbook-shaped, not sprint-shaped.

Ops projects MUST NOT include the development `ways-of-working` rule or any sprint scaffolding — the script omits `project-docs/` for `--type ops`. The operating model lives in the ops-specific rules below. Ops work flows **kanban-style**: the script creates `documentation/tasks/` as a taskmd board (`.taskmd.yaml` → `./documentation/tasks`, plus the `taskmd-cli` rule), with statuses as columns and no sprint tags.

Ops projects have a **fixed default team** — do not walk the operator through agent/orchestrator/skill selection. Confirm the project name, a short purpose, and the **deploy target context** (what is being deployed and to which server(s) — this seeds the operator's understanding, not a config value), then run the script:
- Orchestrator: `ops-orchestrator`
- Agents: `release-engineer`, `platform-engineer`, `sre`, `security-engineer`
- Team: `ops-platform-team`
- Rules (all mandatory): `ops-ways-of-working`, `ops-documentation-structure`, `deploy-safety`, `secrets-handling` (plus `git-history`, auto-included by the script — do not pass it)
- Skills: auto-collected from agent frontmatter (deploy/rollback/health/smoke + `log-pattern-scan`) — do not pass them via `--skills`. Provider adapters are opt-in: pass e.g. `--skills hcloud-inventory` for a Hetzner Cloud fleet, and add its permissions (see the skill)

Example invocation:
```bash
./scripts/new-project.sh \
  --name <project-name> \
  --type ops \
  --purpose "<short purpose>" \
  --team ops-platform-team \
  --orchestrator ops-orchestrator \
  --agents "release-engineer,platform-engineer,sre,security-engineer" \
  --rules "ops-ways-of-working,ops-documentation-structure,deploy-safety,secrets-handling"
```

The `--type ops` script run creates `documentation/{runbooks,incidents,change-log,infra,metrics,tasks}/`, seeds a minimal `metrics/build-deploy-metrics.md` and `infra/environments.md`, writes `.taskmd.yaml`, and applies `templates/settings-ops.json` (ops-shaped permissions: `ssh/scp/rsync/docker/curl/taskmd`, Playwright for web smoke-tests, and a deny floor for irreversible actions — see `deploy-safety` → permission template notes).

**Topology note**: ops projects are typically intended to run as a persistent control node on a server (24/7, full permissions). The bootstrapped folder is the control-plane repo; it does not contain the deployed application.

**Git setup**: Ops projects default to **Option A** (new private GitHub repo) — the control-plane repo is its own repo and its files (CLAUDE.md, `.claude/`, `documentation/`) ARE the content and should be committed. Use the standard Option A flow but adjust the `.gitignore`: the script already writes one (`.DS_Store` + `.claude/settings.local.json`), so do not overwrite it, and do not use `git-info-exclude`. If instead the ops control plane lives inside an existing repo/host, use Option C.

**Post-bootstrap**: register Playwright MCP (used for web smoke-tests) as for development projects. Pin `env.PATH` in `.claude/settings.local.json` only if the control node's toolchain lives outside the system path.

### Custom projects

Custom projects have no fixed defaults. The goal is to fully tailor the project through extensive conversation before running the script.

**Discovery conversation — cover all of the following:**

1. **Purpose and domain** — what is the project for? What problem does it solve? Who will use it?
2. **Ways of working** — will this project have sprints and structured deliverables (development-style), open-ended exploration (research-style), or something else entirely?
3. **Folder structure** — does the operator want `project-docs/` (with the `tasks/` backlog nested under it) (development-style), a minimal layout (research-style), a `documentation/` runbook layout (ops-style), or a custom layout? This determines whether to pass `--type development`, `--type research`, or `--type ops` to the script.
4. **Orchestrator** — browse `/library/orchestrators/` and present the options; recommend the best fit based on the project domain and ways of working.
5. **Agents** — browse `/library/agents/` and walk through the available roles; ask which ones are relevant. Be specific: name each agent and explain what it does, so the operator can make an informed decision.
6. **Skills** — browse `/library/skills/` and present any that are relevant to the project's domain; let the operator opt in.
7. **Rules** — browse `/library/rules/` and discuss which apply; `ways-of-working` and `documentation-structure` are optional here — include them only if the operator's workflow warrants them.
8. **Team definition** — based on the above, propose a team file from `/library/teams/` or offer to draft a new one.
9. **Git setup** — ask which of Options A / B / C (new repo, clone existing, existing local repo) applies.

Once all questions are answered, present a full proposed composition (orchestrator, agents, skills, rules, team, git option) and confirm with the operator before running the script. Treat this confirmation step as mandatory — do not proceed until the operator explicitly approves the proposed setup.

After confirmation, run the script with `--type development`, `--type research`, or `--type ops` based on what was agreed for the folder structure, passing all selected components. Then proceed with git setup per the chosen option.

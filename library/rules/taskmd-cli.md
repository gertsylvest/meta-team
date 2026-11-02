# taskmd CLI Reference

Agents that use the `taskmd` CLI directly MUST follow this reference. **Never guess at flags** — if a command is not listed here, run `taskmd <command> --help` before using it.

## Installation

taskmd is [`github.com/driangle/taskmd`](https://github.com/driangle/taskmd) (MIT) — a markdown-based task management CLI and web dashboard. If `taskmd` is not installed on the machine:

```bash
# Option 1 — Homebrew (macOS or Linuxbrew)
brew tap driangle/tap
brew install taskmd

# Option 2 — direct binary download (no brew needed)
# Assets are versioned (taskmd-<tag>-<os>-<arch>.tar.gz); resolve the latest tag first (needs jq).
OS=$(uname -s | tr '[:upper:]' '[:lower:]')                    # darwin | linux
ARCH=$(uname -m); case "$ARCH" in x86_64) ARCH=amd64;; aarch64) ARCH=arm64;; esac
TAG=$(curl -s https://api.github.com/repos/driangle/taskmd/releases/latest | jq -r .tag_name)
curl -L "https://github.com/driangle/taskmd/releases/download/$TAG/taskmd-$TAG-$OS-$ARCH.tar.gz" | tar xz
mkdir -p ~/.local/bin && mv "taskmd-$OS-$ARCH" ~/.local/bin/taskmd   # or any dir on your PATH

taskmd --version   # verify
```

The extracted binary is named per-platform (e.g. `taskmd-linux-amd64`, `taskmd-darwin-arm64`) — rename it to `taskmd` when moving it onto the PATH, as above. The resolve step needs `jq`; without it, read the tag off the releases page. If a URL 404s, list the assets on the [releases page](https://github.com/driangle/taskmd/releases).

**Per-project setup**: taskmd needs a `.taskmd.yaml` at the project root pointing at the tasks folder. The tasks folder lives **under the documentation folder** — `project-docs/tasks` for development projects (or `documentation/tasks` if the project's doc folder is named `documentation`):

```bash
printf "dir: ./project-docs/tasks\n" > .taskmd.yaml && mkdir -p project-docs/tasks
```

The `project-docs/tasks/` folder is committed to git in development projects (single-developer mode — the task backlog travels with the repo); the bootstrap script sets this up automatically. Nesting tasks under the documentation folder keeps the whole doc+backlog tree together as one git-tracked subtree. Only `.claude/settings.local.json` and `.DS_Store` are gitignored.

taskmd also ships a `taskmd init` command, but it writes its own agent config files and a `TASKMD_SPEC.md` — do **not** use it in projects that already have Claude scaffolding (this rule, skills, task folder); prefer the manual two-liner above.

## Critical: taskmd availability

If `taskmd` is not available (command not found, or errors on every invocation), **this is a stop-the-line blocker**. Raise a `notify` signal to the orchestrator immediately and do not proceed with any sprint work. Sprint planning and execution depend entirely on taskmd being functional.

## Listing tasks

```bash
# All tasks
taskmd list

# Filter by tag
taskmd list --filter tag=sprint-1

# Filter by status
taskmd list --filter status=pending

# Filter by priority
taskmd list --filter priority=high

# Multiple filters (AND logic)
taskmd list --filter status=pending --filter priority=high

# Filter by scope (directory/group)
taskmd list --scope cli
taskmd list --scope "web*"

# Limit results
taskmd list --limit 10

# JSON output
taskmd list --format json
```

There is **no `--tag` flag** — use `--filter tag=<value>` instead.

## Standing-backlog tag convention (development projects)

Reported-but-unscheduled work lives in taskmd under the tag `backlog`, with a type tag (`bug`/`enhancement`/`chore`/`spike`) and severity as `--priority`. The whole pool is `taskmd list --filter tag=backlog`. On scheduling, `taskmd set <id> --remove-tag backlog --add-tag sprint-NN`. See ways-of-working.md → Standing Backlog and `project-docs/project/issue-backlog.md`.

## Getting a specific task

```bash
taskmd get <task-id>          # exact ID match
taskmd get "Task title"       # exact title match
taskmd get cli-037 --format json
```

**Do not rely on fuzzy matching.** When there is no exact match, `get` (and `status <query>`) opens an *interactive* "Did you mean" selection prompt, which fails with an error in non-interactive agent shells. Always pass the exact task ID or exact title; add `--exact` to force a clean not-found error instead of a prompt.

## Updating a task

```bash
# Change status
taskmd set <task-id> --status in-progress
taskmd set <task-id> --status completed
taskmd set <task-id> --status pending
taskmd set <task-id> --status blocked
taskmd set <task-id> --status cancelled
taskmd set <task-id> --status in-review

# Change priority
taskmd set <task-id> --priority high

# Add or remove tags
taskmd set <task-id> --add-tag sprint-2
taskmd set <task-id> --remove-tag sprint-1

# Mark done (shorthand)
taskmd set <task-id> --done
```

Valid statuses: `pending`, `in-progress`, `completed`, `in-review`, `blocked`, `cancelled`.  
`done` is **not** a valid status — use `completed`.

Valid priorities: `low`, `medium`, `high`, `critical`.

## Finding the next task to work on

```bash
taskmd next
taskmd next --limit 3
taskmd next --filter tag=sprint-1
taskmd next --filter priority=high
```

## Searching by text

```bash
taskmd search "authentication"
taskmd search "deploy" --filter status=pending
```

## Checking in-progress tasks

```bash
taskmd status
taskmd status <task-id>      # metadata for a specific task
```

## Creating a task

The title is a **positional argument** — there is no `--title` flag.

```bash
# Basic task
taskmd add "Fix the login bug"

# With metadata
taskmd add "Implement OAuth" --priority high --tags backend,auth,sprint-1

# With parent task
taskmd add "Sub-task title" --parent 001 --tags sprint-1

# Capture file path (required to add body content)
TASK_FILE=$(taskmd add "Task title" --priority high --tags sprint-1 --format json | jq -r .file_path)
```

### Adding body content (acceptance criteria, context)

`taskmd add` creates a task file with placeholder content. Sprint tasks MUST have real acceptance criteria — never leave the placeholder `TODO` content. After creating a task, immediately edit the file:

```bash
# Step 1: create the task — the JSON output includes file_path
taskmd add "Implement login flow" --priority high --tags sprint-1 --format json
```

Read the `file_path` value from the JSON output above.

```bash
# Step 2: use the Edit tool to open that file_path and replace the placeholder sections
# (## Objective, ## Tasks, ## Acceptance Criteria) with real content
```

The task file is plain markdown — write real content directly into the `## Acceptance Criteria` and `## Objective` sections. Do not leave `TODO` placeholders in any sprint task body.

## Validate tasks

```bash
taskmd validate
```

## Unknown flags

If you need a flag or command not listed above, **run `taskmd <command> --help` first** and read the output before constructing your command.

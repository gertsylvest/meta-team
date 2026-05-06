# taskmd CLI Reference

Agents that use the `taskmd` CLI directly MUST follow this reference. **Never guess at flags** — if a command is not listed here, run `taskmd <command> --help` before using it.

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

## Getting a specific task

```bash
taskmd get <task-id>          # exact ID match
taskmd get "Task title"       # title match
taskmd get sho                # fuzzy match
taskmd get cli-037 --format json
```

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

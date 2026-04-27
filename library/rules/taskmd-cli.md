# taskmd CLI Reference

Agents that use the `taskmd` CLI directly MUST follow this reference. **Never guess at flags** — if a command is not listed here, run `taskmd <command> --help` before using it.

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

```bash
taskmd add --title "Task title" --status pending --priority medium
```

## Validate tasks

```bash
taskmd validate
```

## Unknown flags

If you need a flag or command not listed above, **run `taskmd <command> --help` first** and read the output before constructing your command.

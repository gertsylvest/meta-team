# Deploy Safety

This rule defines the preconditions and contract for any deploy to a managed environment. It complements the autonomy guardrails in `ops-ways-of-working.md` — that rule says *what may fire autonomously*; this one says *what makes a deploy safe to attempt at all*.

## Pre-deploy preconditions

A deploy MUST NOT begin unless all of these hold:
1. **The target environment is known** — it exists in `@/documentation/infra/environments.md`, and its current state is understood.
2. **A rollback path exists** — there is a known-good release to roll back to, and the rollback is itself a runbook step. **It is verified executable, not merely named**: the artifact it points at has been confirmed still present (the image is still resident on the host or pullable from the registry; the config backup exists and matches the live file). A restored compose file pointing at an evicted image is a *nominal* rollback that fails at the moment it is needed. Check the artifact, not the reference to it. No deploy without a way back.
3. **Success criteria are defined** — the health check and smoke check that determine *true* success are specified for this environment.
4. **The deploy is idempotent** — re-running a half-completed deploy converges, never double-applies.

If any precondition is unmet, do not deploy — raise `clarify` (missing information) or `notify` (missing capability, e.g. no rollback path) to the orchestrator.

## The deploy contract

Every deploy:
- Is judged successful only when the **health check and smoke check pass** — never on exit code alone.
- Leaves the environment in a **known, recorded state**: healthy on the new release, or cleanly rolled back. Never half-deployed.
- Records a **change-log entry** (what, when, runbook, outcome, autonomous vs. operator-initiated).
- Leaves **`environments.md` naming the version that is actually live**. The change log records what *happened*; the registry records what *is*. A registry naming a superseded release does not merely omit information — it asserts something false to the next agent that reads it on startup, and that agent has no way to know. A deploy is not finished until the registry matches the running artifact. This holds when another team ran the deploy too: its own record does not update this registry, and a reader of this one cannot know another exists.

A record step that nothing checks is a suggestion. Make the registry write a verified step of the deploy runbook, not a closing reminder.

## Maintenance / freeze windows (attended + bounded)

A freeze, maintenance page, or half-flipped edge is a **self-inflicted outage timer** — the environment is degraded for as long as the window stays open. Therefore:

1. **Never leave a live edge frozen/half-flipped across an async boundary** — a subagent completing, a hand-off to another team, or any wait. Run freeze → import/migrate → flip as **one unbroken synchronous sequence** with a live actor throughout; open the freeze only when the very next step can immediately follow.
2. **Bound every freeze with an auto-unfreeze/abort** — if the next step does not proceed within a small N minutes, automatically revert to the known-good state rather than sit in maintenance.
3. **Run time-critical live-edge steps (and their rollback) where prompts get cleared fast** — prefer the attended main session over a background/subagent that can silently hang on a permission prompt; do the rollback inline, not via another agent that might hang the same way. Pre-clear likely permission prompts on the freeze/flip/rollback path before starting.

Example: a freeze held by a subagent across an asynchronous hand-off turned a window of minutes into an outage of hours.

## Approval gates

Deploys to a **user-facing environment** (external users) and any action beyond a rollback follow the autonomy guardrails in `ops-ways-of-working.md`. Autonomous remediation is limited to rollback, retry, and restart; anything destructive, externally-visible beyond rollback, non-reversible, or touching secrets/infrastructure requires an explicit operator signal (`approval-needed`).

## Permission scoping (requirement)

Because agents run with broad permissions on the control node, deploy-capable agents MUST operate under scoped permissions: `.claude/settings.json` allow-lists limited to the tools and hosts each agent needs, a deny list for irreversible and history-rewriting commands, SSH restricted to known hosts, and run-mode jobs limited to declared environments. The concrete permission spec is produced and owned by the security-engineer; this rule establishes that it is mandatory.

### Permission template notes

The ops settings template is a starting point for that spec, not the spec itself. What it assumes:

- **Floor in the project, full list at user level.** The project `.claude/settings.json` carries a short deny floor: `rm -rf` of `/` and home, the core force-push forms, `compose down -v` in every spelling, volume removal and system prune, `curl`/`wget` piped to a shell or interpreter, `--dangerously-skip-permissions`, and reads of SSH keys, Claude credentials and `~/.secrets/**`. The fuller generic list ships as `templates/deny-list-user.json`: merge its `deny` array into your user-level `~/.claude/settings.json`. The bootstrap does not write user settings for you. Deny rules are a union across scopes, so the second copy cannot weaken the first; the user-level copy is the stronger home, because the project file is editable under `Edit(**)` while user settings are not. `rm -rf ~/.*` also blocks `~/.cache` and `~/.npm` cleanups; that cost is accepted.
- **Branch protection is required alongside the deny list.** On the default branch, turn off force push and deletion at the repo host. It is the only control that catches server-side rebases, API ref updates, pushes from other machines, and the force-push spellings no pattern list covers (combined flags, config- or alias-driven force, `git send-pack`). Remote deletion of other branches stays allowed: cleaning up merged branches is routine. Where the host plan does not offer branch protection (for example private repos on some free tiers), record that gap explicitly in `@/documentation/infra/` rather than assuming the protection exists.
- **SSH to known hosts is enforced in `~/.ssh/config`, not in permissions.** Set `Host *` with `StrictHostKeyChecking yes`; `Bash(ssh:*)` cannot express a host list. The deny list refuses `StrictHostKeyChecking=no` and `=accept-new` on the command line.
- **`sudo` only through named wrappers.** For each privileged action, the operator adds one `Bash(sudo /usr/local/bin/<wrapper>:*)` rule to `.claude/settings.local.json` (not committed). The wrapper is owned by `root:root`, mode `0755`. This rule removes a prompt; it is not a boundary, because deny matching strips `sudo` and the agent user may have broader sudo rights. On production-grade machines the boundary is a sudoers entry scoped to the wrapper.
- **Run-mode (headless) settings are environment-specific, so none ship.** When you write one, give it this shape: `defaultMode: dontAsk` (not `auto`), one allow rule per named wrapper instead of broad tools, and a declared host list. Validate it before the first headless job relies on it.
- **Narrow `bash` allows need absolute forms too.** The template allows `bash .claude/skills/*` and `bash documentation/runbooks/assets/*`, but subagents call scripts by absolute path. The bootstrap should add the same two rules with the project's absolute path. Never widen them with a leading `*`: that also matches `bash -c '…' …/.claude/skills/x`.
- **Pattern hygiene.** A Bash rule with a leading `*` that also ends in `:*` is silently dead; for mount targets write `:/*`. In user settings, a `Read` or `Edit` path with a single leading `/` anchors at `~/.claude/`; write `//` for absolute paths (`Edit(//etc/sudoers)`).
- **Bash deny rules match anywhere in the command text**, including heredocs, `grep` patterns and commit messages. Expect occasional false refusals; reword the text rather than weakening the rule. A deny list is a backstop, not a boundary: `rm -fr`, `/bin/rm` or `--` still slip past it.

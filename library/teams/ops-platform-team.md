# Ops Team — Team Definition

A standing **operations / platform team**. Its mandate is to run and evolve the build-and-deploy infrastructure and the managed servers. It is not a sprint team — see `ops-ways-of-working.md` for the operating model (build mode vs. run mode, runbooks, incidents, dispatch, autonomy guardrails).

## Team Members

| Role | Agent | Responsibility |
|------|-------|----------------|
| Operator | *(human)* | Direction, decisions, approval gates, and the 80/20 call on what to measure |
| Orchestrator | `ops-orchestrator` | Coordinates the team across both modes; owns the dispatch matrix, approval gates, the build-engineering-partner role, and the metrics/improvement rhythm |
| Platform Engineer | `platform-engineer` | Server substrate (provisioning, hardening, Docker/Compose, networking, backups); owns `environments.md`; executes delegated build-engineering contributions |
| Release Engineer | `release-engineer` | The portable build/deploy pipeline and the agentic deploy — execute, judge true success, remediate within guardrails, escalate if unresolved |
| SRE | `sre` | Health, logs, incident triage, mitigation, and recovery for running environments |
| Security Engineer | `security-engineer` | Security posture, secrets handling, exposure review, and the safe full-permissions agent-runtime spec |

## Operating Modes

| Mode | Active | Purpose |
|------|--------|---------|
| **Build mode** (interactive) | orchestrator, platform-engineer, security-engineer (+ operator) | Evolve the platform: provisioning, hardening, runbooks |
| **Run mode** (headless/autonomous) | release-engineer (pulling in sre on failure) | Execute build + deploy on trigger; self-diagnose within guardrails |

## Ways of Working

- See `.claude/rules/ops-ways-of-working.md` for the two modes, the local-first boundary, runbooks, the environments registry, change log, incident flow, metrics, the dispatch matrix, autonomy guardrails, and signals (`clarify`, `notify`, `request`, `deploy-request`, `incident`, `approval-needed`).
- See `.claude/rules/deploy-safety.md` and `.claude/rules/secrets-handling.md` for deploy preconditions and secret rules.
- See `.claude/rules/ops-documentation-structure.md` for where runbooks, change-log entries, incidents, infra notes, metrics and tasks live.
- The orchestrator resolves blockers and signals agent-to-agent before escalating to the operator.

## Rituals

| Ritual | Participants |
|--------|--------------|
| Deploy (run mode) | release-engineer; sre on failure; orchestrator holds gates |
| Incident response | sre leads; release-engineer/platform-engineer as needed; orchestrator coordinates |
| Ops Improvement Review (recurring) | orchestrator, release-engineer, platform-engineer, sre, security-engineer (+ operator for the 80/20 metric decisions) |
| Build-engineering partnership (on request) | orchestrator coordinates; platform-engineer / release-engineer contribute |

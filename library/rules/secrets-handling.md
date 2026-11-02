# Secrets Handling

Rules for how the ops team handles secrets (credentials, tokens, keys, connection strings) across the managed environments and the control node. Owned and enforced by the security-engineer.

## Core rules

1. **Never in the repo, never in images.** No secret is committed to any repository or baked into a container image. This includes example/default values that are real.
2. **One defined location.** Secrets live in a single, documented location per environment (e.g. an env-file on the host or a secret store — the exact mechanism is recorded in `@/documentation/infra/`). On the control node, the default location is `~/.secrets/`, which the ops permission template denies agents from reading or editing directly — scripts and services load secrets from it by name. Agents never invent a second copy.
3. **Never echo secret values.** Agents must not print, log, or write secret values into change-log entries, incident notes, runbooks, metrics, or task output. Reference secrets by name, never by value.
4. **Least exposure.** A secret is available only to the service/agent that needs it, on the environment that needs it.
5. **Rotation has an owner.** Secret rotation is an operator-signalled action (`approval-needed`) carried out per a runbook; the security-engineer owns the rotation process and the operator authorises it.

## In runbooks and scripts

- Runbooks and pipeline scripts reference secrets **by name / from the defined location**, never inline.
- A deploy that requires a missing secret is a precondition failure (see `deploy-safety.md`) — raise `clarify`, do not improvise.

## On suspected exposure

If a secret may have leaked (committed, logged, echoed), treat it as an incident: raise `incident`, rotate the secret (operator-signalled), and record a note in `@/documentation/incidents/` without reproducing the secret value.

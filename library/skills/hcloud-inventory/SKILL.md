---
name: hcloud-inventory
description: Read-only inventory of a Hetzner Cloud project via the hcloud CLI — servers, volumes, firewalls, networks, and floating/primary IPs with their state — formatted to feed the environments registry. Single entry point so the agent never hand-rolls hcloud queries and gets a consistent, registry-ready snapshot.
allowed-tools: Bash
argument-hint: "[--context <hcloud-context>]"
---

# hcloud Inventory

A read-only snapshot of what actually exists in a Hetzner Cloud project (CX/CAX/CCX-class instances and the resources around them). Its purpose is to keep `@/documentation/infra/environments.md` honest — run it on startup and after any infrastructure change to reconcile the registry against reality.

This is an **optional provider adapter** for ops projects whose fleet runs on Hetzner Cloud; ops agents mention it as "a provider inventory skill, if installed". Install it with `--skills hcloud-inventory` at bootstrap and add the permissions below. Other providers can follow the same shape.

This skill is **read-only**: it never creates, changes, or deletes Hetzner resources. Provisioning and teardown are operator-signalled runbook actions, not this skill.

## Requirements

- **hcloud CLI** — `brew install hcloud` (macOS/Linux with Homebrew), or a release binary from https://github.com/hetznercloud/cli/releases.
- **Authentication** — an active context (`hcloud context active`) or `HCLOUD_TOKEN` in the environment. The token is a secret: it lives outside the repo per `secrets-handling.md` and is never echoed.
- Pass `--context <name>` to select a specific hcloud context; otherwise the active context is used.

## What it does

Runs the read-only `list` commands and presents them as a registry-ready snapshot:

```bash
hcloud server list   -o columns=id,name,server_type,status,ipv4,location
hcloud volume list    -o columns=id,name,server,size,location
hcloud firewall list  -o columns=id,name,rules_count,applied_to_count
hcloud network list   -o columns=id,name,ip_range,servers
hcloud primary-ip list -o columns=id,name,ip,assignee_name 2>/dev/null || true
```

## Permissions

Add to the project's `.claude/settings.json` when installing this adapter:

```json
{ "permissions": { "allow": ["Bash(hcloud:*)", "Skill(hcloud-inventory)"],
                   "deny": ["Bash(*hcloud server delete*)", "Bash(*hcloud server rebuild*)",
                            "Bash(*hcloud server disable-protection*)", "Bash(*hcloud volume delete*)",
                            "Bash(*hcloud volume detach*)", "Bash(*hcloud image delete*)",
                            "Bash(*hcloud firewall delete*)", "Bash(*hcloud firewall delete-rule*)",
                            "Bash(*hcloud firewall remove-from-resource*)", "Bash(*--allow-sensitive*)"] } }
```

`--allow-sensitive` is denied so `hcloud config get token --allow-sensitive` cannot print the token.

## Output sections

| Section | Reports |
|---|---|
| `CONTEXT` | Which hcloud context/project the snapshot is from |
| `SERVERS` | Each instance: name, type (e.g. CX23), status, IPv4, location |
| `VOLUMES` | Attached/detached volumes and sizes |
| `FIREWALLS` | Firewalls and how many resources they apply to |
| `NETWORKS` | Private networks and ranges |
| `IPS` | Primary/floating IPs and assignment |

## Feeding the registry

After running, reconcile the snapshot against `@/documentation/infra/environments.md`: add any environment that exists but is unregistered, and flag any registered environment that no longer exists or whose host/IP/stack has drifted. The registry remains the source of truth; this skill is how you keep it true.

## Headless-safety

Read-only, non-interactive, no side effects. Safe to run autonomously at any time. Never prints the `HCLOUD_TOKEN` or any secret value.

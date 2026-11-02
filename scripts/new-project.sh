#!/usr/bin/env bash
# new-project.sh — scaffold a new Claude Code project from the meta-team library
#
# Usage (called by Claude after team composition is agreed):
#   ./scripts/new-project.sh \
#     --name my-project \
#     --type development \
#     --purpose "A short description of the project" \
#     --team dev-team \
#     --orchestrator dev-team-orchestrator \
#     --agents "pm,architect,developer" \
#     --skills "log-pattern-scan" \
#     --rules "ways-of-working,documentation-structure"
#
# --type:   "development", "research", or "ops" (default: development)
# --purpose: short project description written into the root CLAUDE.md
# --parent: parent directory for the new project (default: ~/dev)
#           Use this to create projects in subdirectories, e.g. --parent ~/dev/<group>
#           creates the project at ~/dev/<group>/<project-name>
#
# The script creates <parent>/<project-name> with the following structure:
#   .claude/
#     agents/       <- selected agent files
#     rules/teams/  <- team-definition.md (renamed from library team file)
#   project-docs/   <- development projects only
#   CLAUDE.md       <- from templates/CLAUDE.md, customized with project name

set -euo pipefail

LIBRARY_DIR="$(cd "$(dirname "$0")/.." && pwd)/library"
TEMPLATES_DIR="$(cd "$(dirname "$0")/.." && pwd)/templates"
PROJECTS_BASE="$HOME/dev"

# --- Argument parsing ---
PROJECT_NAME=""
PROJECT_TYPE="development"
PROJECT_PURPOSE=""
TEAM=""
ORCHESTRATOR=""
AGENTS=""
SKILLS=""
RULES=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --name)         PROJECT_NAME="$2"; shift 2 ;;
    --type)         PROJECT_TYPE="$2"; shift 2 ;;
    --purpose)      PROJECT_PURPOSE="$2"; shift 2 ;;
    --parent)       PROJECTS_BASE="${2/#\~/$HOME}"; shift 2 ;;
    --team)         TEAM="$2"; shift 2 ;;
    --orchestrator) ORCHESTRATOR="$2"; shift 2 ;;
    --agents)       AGENTS="$2"; shift 2 ;;
    --skills)       SKILLS="$2"; shift 2 ;;
    --rules)        RULES="$2"; shift 2 ;;
    *) echo "Unknown argument: $1"; exit 1 ;;
  esac
done

# --- Validation ---
if [[ -z "$PROJECT_NAME" ]]; then
  echo "Error: --name is required"
  exit 1
fi

PROJECT_DIR="$PROJECTS_BASE/$PROJECT_NAME"

if [[ -d "$PROJECT_DIR" ]]; then
  echo "Error: $PROJECT_DIR already exists. Choose a different name or remove it first."
  exit 1
fi

echo "Scaffolding project: $PROJECT_NAME ($PROJECT_TYPE)"
echo "  Location: $PROJECT_DIR"

# --- Create folder structure ---
mkdir -p "$PROJECT_DIR/.claude/agents"
mkdir -p "$PROJECT_DIR/.claude/rules"

if [[ "$PROJECT_TYPE" == "development" ]]; then
  mkdir -p "$PROJECT_DIR/project-docs"
  echo "  [+] project-docs/"

  # taskmd: tasks folder lives UNDER the documentation folder (project-docs/tasks) —
  # committed (see .gitignore note); nesting it under project-docs keeps the whole
  # doc+backlog tree together for a single sync and one git-tracked subtree.
  mkdir -p "$PROJECT_DIR/project-docs/tasks"
  echo "  [+] project-docs/tasks/"

  cat > "$PROJECT_DIR/.taskmd.yaml" <<'EOF'
dir: ./project-docs/tasks
EOF
  echo "  [+] .taskmd.yaml"

  # Single-developer mode: commit the whole scaffold (CLAUDE.md, .claude/, project-docs/,
  # tasks/, memory/). Only genuinely machine-local / ephemeral state is excluded.
  cat > "$PROJECT_DIR/.gitignore" <<'EOF'
.DS_Store
.claude/settings.local.json

# STRAY agent-memory trees at NON-ROOT paths. Agent memory resolves against the
# DISPATCH's cwd, so a lane dispatched from a subdirectory writes a fresh tree there
# that NO dispatch ever reads. The leading `**/*/` requires at least one directory
# component, so the canonical ROOT `.claude/agent-memory-local/` is NOT matched and
# root memory stays tracked — which is the point: memory IS committed, strays are not.
**/*/.claude/agent-memory-local/
EOF
  echo "  [+] .gitignore"

  # Always include the taskmd CLI reference rule for development projects
  TASKMD_CLI_SRC="$LIBRARY_DIR/rules/taskmd-cli.md"
  if [[ -f "$TASKMD_CLI_SRC" ]]; then
    cp "$TASKMD_CLI_SRC" "$PROJECT_DIR/.claude/rules/taskmd-cli.md"
    echo "  [+] Rule: taskmd-cli (auto-included for development projects)"
  else
    echo "  [!] taskmd-cli rule not found in library — skipping"
  fi

  # Seed the standing-backlog convention doc (project-docs/project/issue-backlog.md)
  mkdir -p "$PROJECT_DIR/project-docs/project"
  ISSUE_BACKLOG_SRC="$TEMPLATES_DIR/issue-backlog.md"
  if [[ -f "$ISSUE_BACKLOG_SRC" ]]; then
    cp "$ISSUE_BACKLOG_SRC" "$PROJECT_DIR/project-docs/project/issue-backlog.md"
    echo "  [+] project-docs/project/issue-backlog.md (standing-backlog convention)"
  else
    echo "  [!] issue-backlog template not found in templates/ — skipping"
  fi
fi

if [[ "$PROJECT_TYPE" == "ops" ]]; then
  # Ops projects are runbook-shaped, not sprint-shaped: documentation/ subfolders,
  # no project-docs/. Work flows kanban-style on a taskmd board under documentation/tasks.
  for sub in runbooks incidents change-log infra metrics tasks; do
    mkdir -p "$PROJECT_DIR/documentation/$sub"
  done
  echo "  [+] documentation/{runbooks,incidents,change-log,infra,metrics,tasks}/"

  cat > "$PROJECT_DIR/.taskmd.yaml" <<'EOF'
dir: ./documentation/tasks
EOF
  echo "  [+] .taskmd.yaml (kanban board)"

  TASKMD_CLI_SRC="$LIBRARY_DIR/rules/taskmd-cli.md"
  if [[ -f "$TASKMD_CLI_SRC" ]]; then
    cp "$TASKMD_CLI_SRC" "$PROJECT_DIR/.claude/rules/taskmd-cli.md"
    echo "  [+] Rule: taskmd-cli (auto-included for ops projects)"
  else
    echo "  [!] taskmd-cli rule not found in library — skipping"
  fi

  # Seed minimal artifacts so they always exist (per ops-ways-of-working.md)
  cat > "$PROJECT_DIR/documentation/metrics/build-deploy-metrics.md" <<'EOF'
# Build & Deploy Metrics

Minimal build/deploy metrics log (80/20 — only measure what would change a decision).
Maintained by the orchestrator; the metric set is revised in the Ops Improvement Review.

| Date | Event | Environment | Build time | Retries | Outcome |
|------|-------|-------------|-----------|---------|---------|
EOF
  cat > "$PROJECT_DIR/documentation/infra/environments.md" <<'EOF'
# Environments Registry

Canonical record of the environments this team manages — the source of truth agents read on startup.

| Name | Purpose | Host / access | Stack | Current version |
|------|---------|---------------|-------|-----------------|
EOF
  echo "  [+] seeded metrics/build-deploy-metrics.md + infra/environments.md"

  cat > "$PROJECT_DIR/.gitignore" <<'EOF'
.DS_Store
.claude/settings.local.json

# STRAY agent-memory trees at NON-ROOT paths. Agent memory resolves against the
# DISPATCH's cwd, so a lane dispatched from a subdirectory writes a fresh tree there
# that NO dispatch ever reads. The leading `**/*/` requires at least one directory
# component, so the canonical ROOT `.claude/agent-memory-local/` is NOT matched and
# root memory stays tracked — which is the point: memory IS committed, strays are not.
**/*/.claude/agent-memory-local/
EOF
  echo "  [+] .gitignore"
fi

# --- Copy team definition (placed in rules/teams/ subfolder, always named team-definition.md) ---
if [[ -n "$TEAM" ]]; then
  TEAM_SRC="$LIBRARY_DIR/teams/$TEAM.md"
  if [[ -f "$TEAM_SRC" ]]; then
    mkdir -p "$PROJECT_DIR/.claude/rules/teams"
    cp "$TEAM_SRC" "$PROJECT_DIR/.claude/rules/teams/team-definition.md"
    echo "  [+] Team: $TEAM -> .claude/rules/teams/team-definition.md"
  else
    echo "  [!] Team not found in library: $TEAM"
  fi
fi

# --- Copy orchestrator ---
if [[ -n "$ORCHESTRATOR" ]]; then
  ORCH_SRC="$LIBRARY_DIR/orchestrators/$ORCHESTRATOR.md"
  if [[ -f "$ORCH_SRC" ]]; then
    cp "$ORCH_SRC" "$PROJECT_DIR/.claude/rules/orchestrator.md"
    echo "  [+] Orchestrator: $ORCHESTRATOR"
  else
    echo "  [!] Orchestrator not found in library: $ORCHESTRATOR"
  fi
fi

# --- Copy agents ---
if [[ -n "$AGENTS" ]]; then
  IFS=',' read -ra AGENT_LIST <<< "$AGENTS"
  for agent in "${AGENT_LIST[@]}"; do
    agent="$(echo "$agent" | tr -d ' ')"
    SRC="$LIBRARY_DIR/agents/$agent.md"
    if [[ -f "$SRC" ]]; then
      cp "$SRC" "$PROJECT_DIR/.claude/agents/$agent.md"
      echo "  [+] Agent: $agent"
    else
      echo "  [!] Agent not found in library: $agent"
    fi
  done
fi

# --- Auto-collect skills declared in agent frontmatter ---
if [[ -n "$AGENTS" ]]; then
  _agent_skills=""
  IFS=',' read -ra _agent_list <<< "$AGENTS"
  for _agent in "${_agent_list[@]}"; do
    _agent="$(echo "$_agent" | tr -d ' ')"
    _src="$LIBRARY_DIR/agents/$_agent.md"
    if [[ -f "$_src" ]]; then
      _found="$(awk 'BEGIN{f=0;s=0} /^---/{f++;next} f==1&&/^skills:/{s=1;next} f==1&&s&&/^  - /{print substr($0,5);next} f==1&&s&&!/^  - /{s=0} f==2{exit}' "$_src")"
      if [[ -n "$_found" ]]; then
        _agent_skills="${_agent_skills}$(echo "$_found" | tr '\n' ','),"
      fi
    fi
  done
  # Merge explicit --skills with agent-declared skills, deduplicate
  _combined="${SKILLS:+$SKILLS,}${_agent_skills%,}"
  if [[ -n "$_combined" ]]; then
    SKILLS="$(echo "$_combined" | tr ',' '\n' | grep -v '^$' | sort -u | tr '\n' ',' | sed 's/,$//')"
    echo "  [i] Skills (including agent-declared): $SKILLS"
  fi
fi

# --- Copy skills ---
if [[ -n "$SKILLS" ]]; then
  mkdir -p "$PROJECT_DIR/.claude/skills"
  IFS=',' read -ra SKILL_LIST <<< "$SKILLS"
  for skill in "${SKILL_LIST[@]}"; do
    skill="$(echo "$skill" | tr -d ' ')"
    SRC="$LIBRARY_DIR/skills/$skill"
    if [[ -d "$SRC" ]]; then
      cp -r "$SRC" "$PROJECT_DIR/.claude/skills/$skill"
      echo "  [+] Skill: $skill"
    else
      echo "  [!] Skill not found in library: $skill"
    fi
  done
fi

# --- git-history rule: auto-included for development and ops projects (both push to shared remotes) ---
if [[ "$PROJECT_TYPE" == "development" || "$PROJECT_TYPE" == "ops" ]]; then
  GIT_HISTORY_SRC="$LIBRARY_DIR/rules/git-history.md"
  if [[ -f "$GIT_HISTORY_SRC" ]]; then
    cp "$GIT_HISTORY_SRC" "$PROJECT_DIR/.claude/rules/git-history.md"
    echo "  [+] Rule: git-history (auto-included for $PROJECT_TYPE projects)"
  else
    echo "  [!] git-history rule not found in library — skipping"
  fi
fi

# --- Copy rules ---
if [[ -n "$RULES" ]]; then
  IFS=',' read -ra RULE_LIST <<< "$RULES"
  for rule in "${RULE_LIST[@]}"; do
    rule="$(echo "$rule" | tr -d ' ')"
    SRC="$LIBRARY_DIR/rules/$rule.md"
    if [[ -f "$SRC" ]]; then
      cp "$SRC" "$PROJECT_DIR/.claude/rules/$rule.md"
      echo "  [+] Rule: $rule"
    else
      echo "  [!] Rule not found in library: $rule"
    fi
  done
fi

# --- Copy .claude/settings.json from template ---
case "$PROJECT_TYPE" in
  research) SETTINGS_TEMPLATE="$TEMPLATES_DIR/settings-research.json" ;;
  ops)      SETTINGS_TEMPLATE="$TEMPLATES_DIR/settings-ops.json" ;;
  *)        SETTINGS_TEMPLATE="$TEMPLATES_DIR/settings-development.json" ;;
esac
if [[ -f "$SETTINGS_TEMPLATE" ]]; then
  cp "$SETTINGS_TEMPLATE" "$PROJECT_DIR/.claude/settings.json"
  echo "  [+] .claude/settings.json (from $PROJECT_TYPE template)"
else
  echo "  [!] Settings template not found: $SETTINGS_TEMPLATE — skipping"
fi

# --- Default skill: team-messaging (every project gets the cross-team channel) ---
# Included for ALL project types regardless of agents/orchestrator selected — the
# file-based messaging channel is machine-wide infrastructure, not a per-team opt-in.
TM_SRC="$LIBRARY_DIR/skills/team-messaging"
if [[ -d "$TM_SRC" ]]; then
  mkdir -p "$PROJECT_DIR/.claude/skills"
  cp -r "$TM_SRC" "$PROJECT_DIR/.claude/skills/team-messaging"
  echo "  [+] Skill: team-messaging (default — all projects)"

  # Resolve the shared channel root with the SAME precedence as the skill helper,
  # then register this team in the channel so it can send and receive mail (v2:
  # a single flat inbox/ + a `teams` registry; team name = project name). The
  # inbox hooks that surface mail around each turn come from the settings template.
  # Precedence: $MESSAGING_ROOT -> ~/.messaging (if it exists) -> ~/dev/messaging
  # (if it exists; legacy) -> ~/.messaging (default). The root is never created here.
  MSG_ROOT="${MESSAGING_ROOT:-}"
  if [[ -z "$MSG_ROOT" ]]; then
    if [[ -e "$HOME/.messaging" ]]; then MSG_ROOT="$HOME/.messaging"
    elif [[ -d "$HOME/dev/messaging" ]]; then MSG_ROOT="$HOME/dev/messaging"
    else MSG_ROOT="$HOME/.messaging"; fi
  fi
  TM_MSG="$PROJECT_DIR/.claude/skills/team-messaging/scripts/msg.sh"
  if [[ -d "$MSG_ROOT" ]]; then
    mkdir -p "$MSG_ROOT/inbox"; touch "$MSG_ROOT/teams"
    grep -qxF "$PROJECT_NAME" "$MSG_ROOT/teams" || printf '%s\n' "$PROJECT_NAME" >> "$MSG_ROOT/teams"
    echo "  [+] messaging: registered '$PROJECT_NAME' in $MSG_ROOT/teams"
  else
    echo "  [!] messaging channel root not found ($MSG_ROOT) — skill copied, but the team is NOT registered."
    echo "      Create the channel and register this team with:"
    echo "        MESSAGING_ROOT=\"$MSG_ROOT\" bash \"$TM_MSG\" init"
    echo "        MESSAGING_ROOT=\"$MSG_ROOT\" bash \"$TM_MSG\" register $PROJECT_NAME"
  fi

  # Record team identity so the skill knows who it is. This is project identity
  # (stable across machines), so it belongs in the committed settings.json env,
  # not settings.local.json — a fresh clone must still know its own team name.
  SETTINGS_FILE="$PROJECT_DIR/.claude/settings.json"
  if [[ ! -f "$SETTINGS_FILE" ]]; then
    echo "  [!] no $SETTINGS_FILE — env.MESSAGING_TEAM not set; add \"env\": {\"MESSAGING_TEAM\": \"$PROJECT_NAME\"} once it exists"
  elif ! command -v jq >/dev/null 2>&1; then
    echo "  [!] jq not found — env.MESSAGING_TEAM NOT written. Add"
    echo "      \"env\": {\"MESSAGING_TEAM\": \"$PROJECT_NAME\"} to $SETTINGS_FILE by hand (or install jq first)"
  elif _tmp="$(jq --arg t "$PROJECT_NAME" '.env = ((.env // {}) + {MESSAGING_TEAM: $t})' "$SETTINGS_FILE")"; then
    printf '%s\n' "$_tmp" > "$SETTINGS_FILE"
    echo "  [+] settings.json: env.MESSAGING_TEAM=$PROJECT_NAME"
  else
    echo "  [!] jq could not update $SETTINGS_FILE — env.MESSAGING_TEAM NOT written"
  fi
else
  echo "  [!] team-messaging skill not found in library — skipping default skill"
fi

# --- Default skill: markdown-diagrams-tables (every project gets aligned diagrams/tables) ---
# Included for ALL project types: any project writes markdown docs, and the recurring
# "boxes misaligned / tables don't render" problem is universal. Depends on D2 (auto-installs
# user-local if missing) and Prettier (via npx, no install).
MDT_SRC="$LIBRARY_DIR/skills/markdown-diagrams-tables"
if [[ -d "$MDT_SRC" ]]; then
  mkdir -p "$PROJECT_DIR/.claude/skills"
  cp -r "$MDT_SRC" "$PROJECT_DIR/.claude/skills/markdown-diagrams-tables"
  echo "  [+] Skill: markdown-diagrams-tables (default — all projects)"
else
  echo "  [!] markdown-diagrams-tables skill not found in library — skipping default skill"
fi

# --- Write CLAUDE.md ---
CLAUDE_TEMPLATE="$TEMPLATES_DIR/CLAUDE.md"
if [[ -f "$CLAUDE_TEMPLATE" ]]; then
  PURPOSE_TEXT="${PROJECT_PURPOSE:-TODO short project description}"
  # Pass values as env vars so special characters in purpose never break the regex
  PROJECT_NAME="$PROJECT_NAME" PURPOSE_TEXT="$PURPOSE_TEXT" \
    perl -pe 's/\{\{project_name\}\}/$ENV{PROJECT_NAME}/g; s/\{\{purpose\}\}/$ENV{PURPOSE_TEXT}/g' \
    "$CLAUDE_TEMPLATE" > "$PROJECT_DIR/CLAUDE.md"
  echo "  [+] CLAUDE.md"
else
  echo "  [!] No CLAUDE.md template found — skipping"
fi

echo ""
echo "Done. Project created at: $PROJECT_DIR"
echo "Next: cd $PROJECT_DIR && claude"

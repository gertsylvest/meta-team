#!/usr/bin/env bash
# new-project.sh — scaffold a new Claude Code project from the meta-team library
#
# Usage (called by Claude after team composition is agreed):
#   ./scripts/new-project.sh \
#     --name my-project \
#     --type development \
#     --purpose "A short description of the project" \
#     --team dev-team \
#     --orchestrator dev-orchestrator \
#     --agents "pm,architect,developer" \
#     --skills "log-pattern-scan" \
#     --rules "ways-of-working,documentation-structure"
#
# --type:   "development" or "research" (default: development)
# --purpose: short project description written into the root CLAUDE.md
# --parent: parent directory for the new project (default: ~/dev)
#           Use this to create projects in subdirectories, e.g. --parent ~/dev/audiospace
#           creates the project at ~/dev/audiospace/<project-name>
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

  # taskmd: tasks folder (gitignored, local-only) + config
  mkdir -p "$PROJECT_DIR/tasks"
  echo "  [+] tasks/"

  cat > "$PROJECT_DIR/.taskmd.yaml" <<'EOF'
dir: ./tasks
EOF
  echo "  [+] .taskmd.yaml"

  cat > "$PROJECT_DIR/.gitignore" <<'EOF'
# Task files are local-only and not committed
/tasks
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
if [[ "$PROJECT_TYPE" == "research" ]]; then
  SETTINGS_TEMPLATE="$TEMPLATES_DIR/settings-research.json"
else
  SETTINGS_TEMPLATE="$TEMPLATES_DIR/settings-development.json"
fi
if [[ -f "$SETTINGS_TEMPLATE" ]]; then
  cp "$SETTINGS_TEMPLATE" "$PROJECT_DIR/.claude/settings.json"
  echo "  [+] .claude/settings.json (from $PROJECT_TYPE template)"
else
  echo "  [!] Settings template not found: $SETTINGS_TEMPLATE — skipping"
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

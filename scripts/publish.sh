#!/usr/bin/env bash
# publish.sh — snapshot manifested files from the private meta-team repo into
#              the public meta-team worktree, commit, and push.
#
# Usage:
#   ./scripts/publish.sh                          # commit + push (default message)
#   ./scripts/publish.sh "Promote post-editor"    # commit + push (custom message)
#   ./scripts/publish.sh --diff                   # show what would change, do not commit
#   ./scripts/publish.sh --no-push                # commit but skip push
#
# Configuration:
#   META_TEAM_PUBLIC_ROOT environment variable overrides the public worktree
#   location (default: $HOME/dev/meta-team-public).
set -euo pipefail

PRIVATE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PUBLIC_ROOT="${META_TEAM_PUBLIC_ROOT:-${HOME}/dev/meta-team-public}"
MANIFEST="${PRIVATE_ROOT}/.publish-manifest"

MODE="publish"
COMMIT_MSG=""

for arg in "$@"; do
    case "${arg}" in
        --diff) MODE="diff" ;;
        --no-push) MODE="no-push" ;;
        --help|-h)
            sed -n '/^# Usage:/,/^set/p' "$0" | sed '$d' | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *) COMMIT_MSG="${arg}" ;;
    esac
done

COMMIT_MSG="${COMMIT_MSG:-Publish: $(date +%Y-%m-%d)}"

if [[ ! -d "${PUBLIC_ROOT}/.git" ]]; then
    echo "ERROR: Public worktree not found at ${PUBLIC_ROOT}" >&2
    echo "       Set META_TEAM_PUBLIC_ROOT or clone the public repo to that path." >&2
    exit 1
fi
if [[ ! -f "${MANIFEST}" ]]; then
    echo "ERROR: Manifest not found at ${MANIFEST}" >&2
    exit 1
fi

echo "Private:  ${PRIVATE_ROOT}"
echo "Public:   ${PUBLIC_ROOT}"
echo "Manifest: ${MANIFEST}"
echo

# Sync public worktree with its remote so we start from the latest published state.
git -C "${PUBLIC_ROOT}" fetch origin --quiet
git -C "${PUBLIC_ROOT}" reset --hard origin/main --quiet

# Wipe everything in the public worktree except .git, so the snapshot is exact.
find "${PUBLIC_ROOT}" -mindepth 1 -maxdepth 1 ! -name '.git' -exec rm -rf {} +

# Copy manifested files into the public worktree.
cd "${PRIVATE_ROOT}"
shopt -s nullglob dotglob

copied=0
missing=()
while IFS= read -r line; do
    # Strip inline comments and surrounding whitespace.
    line="${line%%#*}"
    # shellcheck disable=SC2001
    line="$(echo "${line}" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
    [[ -z "${line}" ]] && continue

    matched=0
    for src in ${line}; do
        if [[ -e "${src}" ]]; then
            matched=1
            dest="${PUBLIC_ROOT}/${src}"
            if [[ -d "${src}" ]]; then
                mkdir -p "${dest}"
                cp -R "${src}/." "${dest}/"
            else
                mkdir -p "$(dirname "${dest}")"
                cp "${src}" "${dest}"
            fi
            copied=$((copied + 1))
        fi
    done
    if [[ "${matched}" == "0" ]]; then
        missing+=("${line}")
    fi
done < "${MANIFEST}"

if [[ "${#missing[@]}" -gt 0 ]]; then
    echo "WARNING: manifest entries with no matching files in private:"
    printf '  %s\n' "${missing[@]}"
    echo
fi

# Stage and check changes in the public worktree.
cd "${PUBLIC_ROOT}"
git add -A

if git diff --cached --quiet; then
    echo "No changes to publish."
    exit 0
fi

echo "Pending publish:"
git diff --cached --stat
echo

case "${MODE}" in
    diff)
        echo "(--diff mode: not committing)"
        # Restore the public worktree so this dry run leaves no trace.
        git reset --hard origin/main --quiet
        exit 0
        ;;
    no-push|publish)
        git commit -m "${COMMIT_MSG}" --quiet
        echo "Committed: ${COMMIT_MSG}"
        if [[ "${MODE}" == "publish" ]]; then
            git push origin main
            echo "Pushed to public origin."
        else
            echo "(--no-push: skipping push)"
        fi
        ;;
esac

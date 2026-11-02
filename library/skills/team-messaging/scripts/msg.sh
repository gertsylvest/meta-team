#!/usr/bin/env bash
# team-messaging helper — file-based cross-team channel (v2, single flat inbox).
# Portable: GNU (Linux) and BSD/macOS userland, bash 3.2+ (no `find -printf`,
# no bash-4 features like mapfile/associative arrays).
#
# LAYOUT (v2):
#   <root>/teams        registry — one active team name per line (source of truth
#                       for "who exists"; drives dead-letter detection)
#   <root>/inbox/       ALL messages, flat. One file per message:
#                       <ts>__from-<sender>__to-<recipient>__<slug>.md
#                       marked read by renaming the tail to .READ.md
#   <root>/README.md    short channel description (created by `init`)
# There are NO per-team folders in v2 — recipient lives in the filename + the
# frontmatter `to:`. A message has exactly one recipient, so read-marking stays a
# plain rename.
#
# Timestamps are UTC to the second (2026-01-31T142305Z). Older files carry
# minute resolution (2026-01-31T1423Z); both parse the same way. If a filename is
# already taken, `send` appends _2, _3, ... to the slug instead of overwriting.
#
# Names: team names and slugs are limited to [A-Za-z0-9._-] and may not contain
# "/", ".." or "__" ("__" is the filename field separator). Slugs are sanitised
# (other characters become "-"); invalid team names are rejected.
#
# Path resolution (keeps the skill free of a baked-in location):
#   $MESSAGING_ROOT  ->  ~/.messaging (if it exists)
#                    ->  ~/dev/messaging (if it exists; legacy location)
#                    ->  ~/.messaging (default, created by `init`)
# Sender/own-team:  $MESSAGING_TEAM  or  --from <team>
#
# DEAD LETTERS: an unread inbox message whose recipient is empty or not in the
# `teams` registry (typo, renamed, or terminated team). It matches no team's
# inbox filter, so it would sit invisible forever — instead `dead-digest`
# surfaces it (the inbox hook shows it to whichever orchestrator is active, to
# flag to the operator). Marking it read stops it resurfacing for everyone.
#
# Subcommands:
#   root                 print the resolved channel root
#   init                 create <root>, inbox/, an empty teams file and README.md
#                        (only what is missing; never overwrites)
#   teams                list the active-team registry
#   register   <team>    add a team to the registry (idempotent)
#   unregister <team>    remove a team (its pending mail then reads as dead-letter)
#   inbox [team]         list unread messages addressed to team (oldest first)
#   unread-count [team]  print the number of such unread messages (0 if none)
#   digest [team]        compact one-line-per-message digest of team's unread
#   dead-digest          compact digest of unroutable (dead-letter) unread mail
#   peek  <file>         print a message WITHOUT marking it read
#   read  <file>         print a message and mark it read (rename -> .READ.md)
#   readdress <file> <to>  re-point a (dead-letter) message at a valid team
#   send  <to> <slug> [--from T] [--subject S] [--priority normal|high]
#                        body is read from stdin
set -euo pipefail

die() { echo "msg: $*" >&2; exit 1; }

resolve_root() {
  if [ -n "${MESSAGING_ROOT:-}" ]; then echo "$MESSAGING_ROOT"; return; fi
  if [ -e "$HOME/.messaging" ]; then echo "$HOME/.messaging"; return; fi
  if [ -d "$HOME/dev/messaging" ]; then echo "$HOME/dev/messaging"; return; fi
  echo "$HOME/.messaging"
}
ROOT="$(resolve_root)"
INBOX="$ROOT/inbox"
REGISTRY="$ROOT/teams"

# --- helpers ---------------------------------------------------------------
# frontmatter value for a key (first match)
_field() { grep -m1 -E "^$2:" "$1" 2>/dev/null | sed -E "s/^$2:[[:space:]]*//" || true; }
# recipient encoded in a filename: <...>__to-<recipient>__<slug>.md  ("" if absent)
_recip_of() {
  case "$1" in
    *__to-*__*) rest="${1#*__to-}"; echo "${rest%%__*}" ;;
    *) echo "" ;;
  esac
}
# is <name> a registered active team?
_is_team() { [ -f "$REGISTRY" ] && grep -qxF "$1" "$REGISTRY"; }
# is <name> a safe team name / slug? [A-Za-z0-9._-], no "..", no "__", not empty,
# no leading "-" or "_" and no trailing "_" (either would blur the "__" separators)
_valid_name() {
  case "$1" in
    ""|*/*|*..*|*__*|.|-*|_*|*_) return 1 ;;
    *[!A-Za-z0-9._-]*) return 1 ;;
  esac
  return 0
}
_need_name() { _valid_name "$2" || die "invalid $1 '$2' (allowed: A-Z a-z 0-9 . _ -; no '/', '..' or '__')"; }
# list unread message basenames in inbox (oldest first). $1 optional grep -F filter.
_unread() {
  [ -d "$INBOX" ] || return 0
  ls -1 "$INBOX" 2>/dev/null | grep -E '\.md$' | grep -v -E '\.READ\.md$' \
    | { if [ -n "${1:-}" ]; then grep -F -- "$1"; else cat; fi; } | LC_ALL=C sort || true
}
# first free "<stem>.md" / "<stem>_<n>.md" whose .READ.md twin is also free; claims it
# atomically (noclobber). "_<n>" sorts after "<stem>.md", so oldest-first holds.
_claim() {
  stem="$1"; n=1; cand="$stem.md"
  while :; do
    if [ ! -e "${cand%.md}.READ.md" ] && ( set -C; : > "$cand" ) 2>/dev/null; then
      echo "$cand"; return 0
    fi
    n=$((n+1)); [ "$n" -le 999 ] || return 1
    cand="${stem}_$n.md"
  done
}

cmd="${1:-}"; shift || true
case "$cmd" in
  root|init|""|help|-h|--help) : ;;
  *) [ -d "$ROOT" ] || die "channel root not found: $ROOT (set \$MESSAGING_ROOT, or run: msg.sh init)" ;;
esac

case "$cmd" in
  root) echo "$ROOT" ;;

  init)
    mkdir -p "$INBOX"
    [ -e "$REGISTRY" ] || : > "$REGISTRY"
    if [ ! -e "$ROOT/README.md" ]; then
      cat > "$ROOT/README.md" <<'EOF'
# Team messaging channel

A file-based mailbox between agent teams on this machine. Not under version
control. Managed with the `team-messaging` skill (`scripts/msg.sh`).

- `teams`  — registry of active teams, one name per line.
- `inbox/` — every message, one file each:
  `<UTC-timestamp>__from-<sender>__to-<recipient>__<slug>.md`.
  A message is marked read by renaming it to end in `.READ.md`; read files stay
  as the audit trail.

Unread mail to a name not in `teams` is a dead letter and is surfaced to the
active orchestrator for the operator to resolve.

Everyone who can read this folder can read every message. Never put secrets here,
and keep decisions in git, not in messages.
EOF
    fi
    echo "channel ready: $ROOT"
    ;;

  teams)
    [ -f "$REGISTRY" ] && grep -vE '^[[:space:]]*(#|$)' "$REGISTRY" || true
    ;;

  register)
    name="${1:?usage: msg register <team>}"; _need_name "team name" "$name"
    mkdir -p "$INBOX"; touch "$REGISTRY"
    grep -qxF "$name" "$REGISTRY" || printf '%s\n' "$name" >> "$REGISTRY"
    echo "registered: $name"
    ;;

  unregister)
    name="${1:?usage: msg unregister <team>}"
    [ -f "$REGISTRY" ] || die "no registry: $REGISTRY"
    tmp="$REGISTRY.tmp.$$"; grep -vxF "$name" "$REGISTRY" > "$tmp" || true
    mv "$tmp" "$REGISTRY"; echo "unregistered: $name (its pending mail now reads as dead-letter)"
    ;;

  inbox)
    team="${1:-${MESSAGING_TEAM:-}}"
    [ -n "$team" ] || die "no team given and \$MESSAGING_TEAM unset (usage: msg inbox <team>)"
    _need_name "team name" "$team"
    n=0
    while IFS= read -r base; do
      [ -n "$base" ] || continue
      echo "$INBOX/$base"; n=$((n+1))
    done < <(_unread "__to-${team}__")
    [ "$n" -gt 0 ] || echo "(no unread messages for $team)"
    ;;

  unread-count)
    team="${1:-${MESSAGING_TEAM:-}}"
    { [ -n "$team" ] && _valid_name "$team"; } || { echo 0; exit 0; }
    c=0
    while IFS= read -r base; do [ -n "$base" ] && c=$((c+1)); done < <(_unread "__to-${team}__")
    echo "$c"
    ;;

  digest)
    team="${1:-${MESSAGING_TEAM:-}}"
    { [ -n "$team" ] && _valid_name "$team"; } || exit 0
    n=0; hi=0; out=""
    while IFS= read -r base; do
      [ -n "$base" ] || continue
      f="$INBOX/$base"
      from="$(_field "$f" from)"; subj="$(_field "$f" subject)"; pri="$(_field "$f" priority)"
      [ -n "$pri" ] || pri="normal"; [ "$pri" = high ] && hi=$((hi+1))
      out="${out}- [${pri}] from ${from:-?} — ${subj:-(no subject)}  →  ${f}
"
      n=$((n+1))
    done < <(_unread "__to-${team}__")
    [ "$n" -gt 0 ] || exit 0
    extra=""; [ "$hi" -gt 0 ] && extra=" (${hi} high-priority)"
    printf '%d unread message(s)%s:\n%s' "$n" "$extra" "$out"
    ;;

  dead-digest)
    # unread messages whose recipient is empty or not a registered team.
    [ -f "$REGISTRY" ] || exit 0   # no registry -> can't judge routability; stay silent
    n=0; out=""
    while IFS= read -r base; do
      [ -n "$base" ] || continue
      recip="$(_recip_of "$base")"
      if [ -z "$recip" ] || ! _is_team "$recip"; then
        f="$INBOX/$base"; from="$(_field "$f" from)"; subj="$(_field "$f" subject)"
        out="${out}- to '${recip:-<none>}' (unknown) from ${from:-?} — ${subj:-(no subject)}  →  ${f}
"
        n=$((n+1))
      fi
    done < <(_unread)
    [ "$n" -gt 0 ] || exit 0
    printf '%d unroutable (dead-letter) message(s):\n%s' "$n" "$out"
    ;;

  peek)
    f="${1:?usage: msg peek <file>}"; [ -f "$f" ] || die "no such message: $f"; cat "$f" ;;

  read)
    f="${1:?usage: msg read <file>}"; [ -f "$f" ] || die "no such message: $f"; cat "$f"
    case "$f" in
      *.READ.md) : ;;
      *.md)
        dest="${f%.md}.READ.md"; k=1
        while [ -e "$dest" ]; do k=$((k+1)); dest="${f%.md}-$k.READ.md"; done
        mv "$f" "$dest"; echo "-- marked read: $dest" >&2 ;;
    esac
    ;;

  readdress)
    f="${1:?usage: msg readdress <file> <new-team>}"; newto="${2:?new team required}"
    [ -f "$f" ] || die "no such message: $f"
    _need_name "team name" "$newto"
    _is_team "$newto" || die "not a registered team: $newto (msg register '$newto' first)"
    base="$(basename "$f")"; dir="$(dirname "$f")"
    # rewrite frontmatter to: (reply-to stays); rename __to-<old>__ -> __to-<newto>__
    case "$base" in
      *__to-*__*)
        prefix="${base%%__to-*}"; rest="${base#*__to-}"; rest="${rest#*__}"
        newbase="${prefix}__to-${newto}__${rest}" ;;
      *) newbase="${base%.md}__to-${newto}__readdressed.md" ;;
    esac
    [ ! -e "$dir/$newbase" ] || [ "$dir/$newbase" = "$f" ] || die "target exists: $dir/$newbase"
    tmp="$f.tmp.$$"; sed -E "s/^to:[[:space:]].*/to: ${newto}/" "$f" > "$tmp" && mv "$tmp" "$f"
    [ "$dir/$newbase" = "$f" ] || mv "$f" "$dir/$newbase"
    echo "readdressed -> $dir/$newbase"
    ;;

  send)
    to="${1:?usage: msg send <to-team> <slug> [--from T] [--subject S] [--priority P]}"
    slug="${2:?slug required}"; shift 2 || true
    from="${MESSAGING_TEAM:-}"; subject=""; priority="normal"
    while [ $# -gt 0 ]; do
      case "$1" in
        --from) from="${2:?}"; shift 2;;
        --subject) subject="${2:?}"; shift 2;;
        --priority) priority="${2:?}"; shift 2;;
        *) die "unknown flag: $1";;
      esac
    done
    [ -n "$from" ] || die "sender required: --from <team> or set \$MESSAGING_TEAM (the one hard rule)"
    _need_name "sender" "$from"
    _need_name "recipient" "$to"
    [ -n "$subject" ] || subject="$slug"
    # Slugs are free text from the caller: map anything outside the safe set to "-".
    slug="$(printf '%s' "$slug" | tr -c 'A-Za-z0-9._-' '-')"
    while :; do case "$slug" in [-_]*) slug="${slug#?}" ;; *_) slug="${slug%_}" ;; *) break ;; esac; done
    _need_name "slug" "$slug"
    # Sender must be a registered team: reply-to is set to <from>, so an unknown
    # sender makes replies undeliverable. Reject (as the old model did via folders).
    _is_team "$from" || die "unknown sender: '$from' is not in the registry ($REGISTRY) — msg register '$from' first, or fix --from so replies are deliverable"
    # Unknown recipient is a SOFT failure: deliver anyway so it surfaces as a
    # dead-letter (a typo'd/renamed recipient should be flagged, not silently lost).
    _is_team "$to" || echo "msg: warning: recipient '$to' is not a registered team — delivering as a dead-letter (will be flagged for the operator)" >&2
    mkdir -p "$INBOX"
    ts="$(date -u +%Y-%m-%dT%H%M%SZ)"; dateh="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    body="$(cat || true)"
    file="$(_claim "$INBOX/${ts}__from-${from}__to-${to}__${slug}")" || die "could not allocate a free filename for $slug"
    {
      printf '%s\n' '---'
      printf 'from: %s\n' "$from"
      printf 'to: %s\n' "$to"
      printf 'date: %s\n' "$dateh"
      printf 'subject: %s\n' "$subject"
      printf 'reply-to: %s\n' "$from"
      printf 'priority: %s\n' "$priority"
      printf '%s\n\n' '---'
      printf '%s\n' "$body"
    } > "$file"
    echo "sent: $file"
    ;;

  ""|help|-h|--help)
    grep -E '^#( |$)' "$0" | sed 's/^# \{0,1\}//'
    ;;

  *) die "unknown command '$cmd' (try: msg help)" ;;
esac

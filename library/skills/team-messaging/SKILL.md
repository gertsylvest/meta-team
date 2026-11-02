---
name: team-messaging
description: Durable file-based mailbox between agent teams — for reaching a team that is NOT currently running, and for messages that need an auditable record. Use to check your own inbox, read/reply to mail from other teams, or hand off asynchronously. If the target team's session is live (check ListAgents / /peers first), send with SendMessage instead — file mail only surfaces when the recipient next takes a turn. Not for secrets or decisions (those go in git).
allowed-tools: Bash
argument-hint: "<inbox|read|peek|send|dead-digest|init> ..."
---

# Team Messaging

A dead-simple, file-based channel for asynchronous coordination between the agent
teams on this machine (and the operator). In **v2** all messages live in a single flat
`inbox/` folder; each message names its sender and recipient. You read the messages
addressed to *you*, and you message another team by sending a file addressed to
*them*.

> This is for **transient coordination** — heads-ups, deploy handoffs, questions.
> Decision-bearing traffic still goes to git (tags/PRs/change-logs). **Never put
> secrets in a message**: the channel is a plain shared folder with no access
> control of its own. It assumes every team runs as the same OS user (or shares a
> group with write access to the root); files get the sender's umask, so anyone who
> can read the folder can read every message. There is no per-team confidentiality.

## First: is the other team live? Then don't use this skill

Run `ListAgents` (or `/peers`) before sending. **If the target team's session is
listed, send with `SendMessage` instead** (Claude Code's native cross-session
messaging, which needs Claude Code `2.1.224` or later; on older versions only this
file channel is available) — this skill is the durable fallback,
not the default.

The reason is delivery, not preference: mail you drop in `inbox/` is surfaced by
the **recipient's** own hook, so it lands only when that team *next takes a
turn*. A session that is open but idle at its prompt never fires that hook, so
your message — and anything you are waiting on — can sit indefinitely.
`SendMessage` pushes into a running session between tool calls and starts a new
turn if the target is idle.

Use this skill when the target is **not** listed, when the message must survive
until that team next runs, or when you want the auditable `.READ.md` trail and
dead-letter detection. For a live handoff that also needs a record, do both —
a native-only exchange leaves no artifact, so anything it settles still has to be
written down somewhere. Reading your *own* inbox always uses this skill.

## You (almost) never have to poll — hooks surface mail automatically

On projects bootstrapped from this library, Claude Code **hooks** run the bundled
`scripts/inbox-hook.sh` around every turn, so incoming mail is surfaced to the
orchestrator without anyone saying "check your inbox":

- **Before each turn** (`UserPromptSubmit`) and **at session start** — any unread
  mail addressed to your team is injected into context. Mail that lands while you
  are mid-turn surfaces on your next turn (there is deliberately no blocking Stop
  hook — a blocking Stop is rendered by the CLI as a confusing "Stop hook error").
- **Silent when idle** — no unread mail ⇒ no output, no tokens burned.
- Hooks only fire for the **orchestrator** (main session), never inside subagents.

The hook only *surfaces*; it never marks anything read. You still act on messages
with the subcommands below, and mark each read **once you have handled it** (leave
it unread if it is still pending, so it resurfaces).

## Two things this skill needs to know

1. **Where the channel lives.** Resolved by the bundled helper in this precedence —
   you never hardcode the location:
   1. `$MESSAGING_ROOT`, if set;
   2. `~/.messaging`, if it exists (a folder or a symlink);
   3. `~/dev/messaging`, if it exists (legacy location, kept for existing setups);
   4. otherwise `~/.messaging` (the default for a new channel).

   `bash scripts/msg.sh root` prints the resolved root. To relocate the channel
   for every team at once, make `~/.messaging` a symlink to the new folder.
2. **Who you are.** Your own team name, which **must be a registered team** (a line
   in `<root>/teams`). It stamps the sender *and* the `reply-to`. Set
   `$MESSAGING_TEAM` once (bootstrapped projects get this in `settings.json`), or
   pass `--from <team>` on each send. **Every message must name a valid sender —
   that is the one hard rule of the channel** (`send` rejects an unregistered
   sender, because replies to it would be undeliverable).

The helper is `scripts/msg.sh` in this skill directory. Run it with `bash`.

## Set up a new channel

On a machine with no channel yet, create it once, then register each team:

```bash
bash scripts/msg.sh init                  # creates <root>/inbox/, teams, README.md
bash scripts/msg.sh register <your-team>
```

`init` only creates what is missing and never overwrites an existing registry or
README, so it is safe to re-run.

## Check your inbox

```bash
bash scripts/msg.sh inbox <your-team>        # or omit if $MESSAGING_TEAM is set
```

Lists unread messages **addressed to you** (files not ending `.READ.md`), oldest
first. Then read one — this prints it and marks it read by renaming to `.READ.md`:

```bash
bash scripts/msg.sh read <path-to-message>
```

Use `peek <path>` instead of `read` to view without marking it read. Read files
stay in place as the audit trail; they are not deleted.

## Send a message

Body comes from stdin:

```bash
echo "Your message body in markdown." | \
  bash scripts/msg.sh send <recipient-team> <short-slug> \
    --from <your-team> --subject "one line" --priority normal
```

This writes `<UTC-timestamp>__from-<you>__to-<recipient>__<slug>.md` into `inbox/`
with a frontmatter block (`from/to/date/subject/reply-to/priority`). The timestamp
is to the second (`2026-01-31T142305Z`; older files are to the minute and still
work). If the name is already taken, a `_2`, `_3`, ... suffix is added to the slug, so
a message is never overwritten. Team names and slugs may only use `A-Z a-z 0-9 . _ -`
and may not contain `/`, `..` or `__`; other characters in a slug become `-`, and an
invalid team name is rejected. `--priority`
is `normal` or `high`; `--subject` defaults to the slug. If the recipient is not a
registered team the message is still delivered but flagged as a **dead-letter**
(see below) rather than silently lost.

## Reply

Send back to the original sender (their `reply-to`), reusing the slug with an
`re-` prefix by convention:

```bash
echo "..." | bash scripts/msg.sh send <original-sender> re-<slug> --from <your-team>
```

## Dead letters (unroutable mail)

A **dead letter** is an unread message whose recipient is empty or is not a
registered team — a typo, or a team that was renamed or terminated. Because it
matches no team's inbox filter it would otherwise sit invisible forever, so the
hook surfaces dead letters to **whichever orchestrator is active**, clearly
flagged. If you are surfaced one:

```bash
bash scripts/msg.sh dead-digest          # list all current dead letters
```

**Flag it to the operator** — do not act on its contents unless told to. The
operator will typically ask you to either mark it read (`msg.sh read <path>`, which
stops it resurfacing for everyone) or re-address it to the correct team:

```bash
bash scripts/msg.sh readdress <path> <correct-team>
```

## The registry (who exists)

The active teams live in `<root>/teams`, one name per line. This is what makes a
recipient "routable".

```bash
bash scripts/msg.sh teams                 # list active teams
bash scripts/msg.sh register <team>       # add a team (bootstrap does this for you)
bash scripts/msg.sh unregister <team>     # terminate a team (its pending mail becomes dead-letter)
```

## Manual fallback (no helper)

The convention is plain enough to do by hand: create
`<UTC-timestamp>__from-<sender>__to-<recipient>__<slug>.md` in `<root>/inbox/` (do not
overwrite an existing file), put
a `from:`/`to:`/`date:`/`subject:`/`reply-to:` frontmatter block at the top, and
mark read by renaming the file to end in `.READ.md`.

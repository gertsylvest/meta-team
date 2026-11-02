---
name: figma-review
description: Run a review round on a Figma file — pull the operator's pinned canvas comments (which the Figma MCP server cannot see), resolve each onto the editable node it targets, apply the edits, reply in-thread, and land the decision in git. Use when the operator says they have left comments or finished a review, when asked to act on Figma feedback, or before editing any artboard in a reviewed file.
allowed-tools: Bash, Read
argument-hint: "[list | act | reply <comment_id> <text>]"
---

# Figma review round

The Figma MCP server has **no comments API**, so operator feedback pinned on the canvas is invisible
unless you go and fetch it. The bundled `figma-comments.py` bridges that over the Figma **REST** API.
The useful property: a pinned comment's `client_meta.node_id` is already in the **same `188:3` form the
MCP edit tool takes**, so feedback lands on an editable node with no guessing. That is the whole trick.

Run the script from this skill's directory, e.g.
`python3 .claude/skills/figma-review/figma-comments.py list`.

## Requirements

- **Figma MCP server** connected to Claude Code — the edit side of the loop uses its tools
  (`mcp__figma__*`, e.g. `use_figma`). Without it you can still `list` / `reply`, but not apply edits.
- **A Figma personal access token (PAT)** for the REST API, which is the only way to read comments
  (see Setup below).
- **Python 3.8+** (standard library only).

## Setup (one-off, operator)

1. figma.com → **Settings → Security → Personal access tokens** → generate one.
   Scopes: **`file_comments:write`** (read + reply) and **`file_content:read`** (resolve node names).
2. Store it outside the repo — **never commit a token**:
   ```bash
   mkdir -p ~/.config/figma && install -m 600 /dev/null ~/.config/figma/pat
   $EDITOR ~/.config/figma/pat     # the token as the only line
   ```
   `$FIGMA_PAT` in the environment also works and takes precedence. The token is never printed,
   echoed, or passed as an argument.
3. **Name the file.** The script has no baked-in default: set `env.FIGMA_FILE_KEY` in
   `.claude/settings.json` (the key is the `<KEY>` in `figma.com/design/<KEY>/<name>`), or pass
   `--file KEY` per call.
4. **Grant the permissions** in `.claude/settings.json`, or every round prompts:
   ```json
   "Skill(figma-review)",
   "Bash(python3 .claude/skills/figma-review/figma-comments.py:*)",
   "mcp__figma__*"
   ```

## The loop

0. **Read this project's conventions** — `.claude/skills/figma-review/PROJECT.md` (file key, live vs
   archived pages, the drawing conventions the artboards obey, where the decision record lands). If it
   is missing, ask the operator for those three things and write it before editing anything — see
   [What your project must supply](#what-your-project-must-supply--projectmd).
1. **Pull** — `python3 .claude/skills/figma-review/figma-comments.py list --no-cache`
   Always `--no-cache` at the start of a round: the script caches the file tree ~10 min, and you have
   probably edited structure since.
   `list` shows **threads only** — your own replies are hidden, and a thread the operator resolved is
   gone. An empty list at the end of a round is the round being finished, not the script failing.
2. **Triage before touching anything.** Group the comments by region, and separate:
   - **direct edits** — "this badge is too subtle" → just do it;
   - **decisions** — anything that changes the model (what a surface _is_, where something lives).
     Those go to the operator with a recommendation, and then to git. Do not silently design.
3. **Apply, incrementally.** Load the Figma edit guidance first (below), then one region per edit call,
   screenshotting to verify. Never one giant script.
4. **Reply in-thread** — `… reply <id> "narrowed the cards; dropped links to the pop-up"`
   Say what you changed, not that you agree.
5. **Ask the operator to resolve.** The REST API **cannot** mark a comment resolved — no endpoint. You
   reply; they resolve in the UI.
6. **Land the durable record in git.** A review round that only changed pixels is unfinished — the
   reasoning belongs in the project's design doc, then one commit per round. **Decisions never live in
   a comment thread.**

## Commands

```bash
figma-comments.py list                  # unresolved THREADS, oldest first
figma-comments.py list --all            # include resolved
figma-comments.py list --replies        # include replies too (off by default)
figma-comments.py list --json           # for the agent to parse
figma-comments.py list --no-cache       # refetch the file tree (after structural edits)
figma-comments.py show   <comment_id>   # one thread, replies included
figma-comments.py nodes  <comment_id>   # just the node id, for piping
figma-comments.py reply  <comment_id> "picked this up — narrowed the cards"
```

What `list` gives you:

```
#1  [2025-01-15 09:12]  reviewer
    node  188:7  "Header — status badges"  [FRAME]  pinned
    path  Home · desktop ▸ Header ▸ right group ▸ Header — status badges
    | the active badge is too subtle
    id    1234567890
```

`node` is directly usable in an edit script: `getNodeByIdAsync("188:7")`.

## Before any Figma edit call

Load the Figma guidance or you will hit avoidable failures: prefer a local `/figma-use` skill; if
absent, read the MCP resource `skill://figma/figma-use/SKILL.md` and pass
`skillNames: "resource:figma-use"`.

## Limits worth knowing

- **Cannot mark a comment resolved.** The REST API has no resolve endpoint (GET / POST / DELETE only).
  `list` hides resolved threads by default; **resolve them in the UI**. Replying is supported, so the
  agent answers in-thread and the operator resolves.
- **`list` shows threads, not comments.** Figma stamps `resolved_at` on the **thread root only**, and a
  reply carries no pin of its own — so the script makes a reply inherit both from its root. Without
  that, a finished round comes back looking like an open one: the replies survive the resolved-filter
  and get hit-tested onto whatever node sits under (0,0). Use `--replies` when you actually want the
  answers back; `show <id>` always includes them.
- **Replies post as the token's owner** — the operator. The PAT is theirs, so an agent's reply appears
  in the thread under their handle. Write replies that read as the round's record, not as first-person
  notes.
- **Unpinned comments** (dropped on empty canvas) carry only `x`/`y`. Those are hit-tested against the
  file's node boxes and reported as **`~approx`** with the deepest containing node — treat as a hint,
  not a fact. **Pinning onto the element gives an exact node id**, so ask the operator to pin.
- The file tree is fetched to resolve names/paths and **cached ~10 min** (mode 600) in
  `~/.cache/figma-comments/`. Pass `--no-cache` after structural edits.
- **MCP edit calls are rate-limited, and the limit depends on your Figma plan and seat** (on the order
  of a couple of hundred calls a day has been seen; check your plan's current limits). Batch a region
  per call; do not redraw a whole artboard to change one label.

## Edit gotchas seen in practice

| Symptom                                         | Cause                                                       | Fix                                                                      |
| ----------------------------------------------- | ----------------------------------------------------------- | ------------------------------------------------------------------------ |
| `no such property 'strokeDashPattern' on FRAME` | wrong property name                                         | it is **`node.dashPattern`**                                             |
| a bubble/caption above a band is invisible      | parent frames clip absolute overflow                        | `clipsContent = false` on **every** ancestor, not just the immediate one |
| a glyph renders as tofu (`⤴`, exotic arrows)    | **Inter has no U+2934** and little of Supplemental Arrows-B | use `↗` (U+2197); Inter covers U+2190–2199                               |
| columns leave a wide gap at the right           | hardcoded widths surviving a resize                         | recompute from the parent's width, and return the right edge to check    |
| edits land on the wrong page                    | page context resets per call                                | `await figma.setCurrentPageAsync(page)` **once** per call                |

## What your project must supply — `PROJECT.md`

This skill is the mechanism; the conventions are yours. They go in a **`PROJECT.md` beside this file**
(`.claude/skills/figma-review/PROJECT.md`), which step 0 of the loop reads. Three things belong there:

- the **file key** and which pages are live vs archived (never resume an archived page's edit queue);
- the **drawing conventions** the artboards obey (palette or grey-box, fonts and weights, fill/border
  values, what dashed means, whether every artboard carries a legend);
- **where the decision record lands** in git, and the rule that Figma is canonical for pixels while git
  is canonical for decisions — point to Figma by reference, never mirror pixels into the repo.

**Why a separate file, and why that name.** Do not put project conventions in this SKILL.md: propagating
a library update to an existing project overwrites it, and the loss is silent. `PROJECT.md` is safe
because **the library deliberately ships no `PROJECT.md`** — there is no file of that name to copy over
yours. Two rules keep it that way:

- **Never add a `PROJECT.md` to `library/skills/figma-review/`.** An example belongs in this section, not
  in a shippable file.
- **Propagate by merge, never by replace.** `cp -r library/skills/figma-review/. <proj>/.claude/skills/figma-review/`
  — note the trailing `/.`, which also avoids `cp -r` nesting a second copy inside an existing directory.
  Never `rm -rf` the project's skill folder first.

Bootstrap itself is not a clobber risk: `new-project.sh` aborts if the project directory already exists,
so it only ever writes into a fresh tree. Hand-propagation to a live project is the case to be careful
about.

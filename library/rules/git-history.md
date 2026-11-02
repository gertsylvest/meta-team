# Git History — merge, never rewrite what is pushed

This rule covers every repository this team owns and pushes to. It exists because several agents, worktrees
and CI runs work against the same remote at the same time. In that setting, rewriting shared history fails
silently and loses work, while merging never loses anything.

## The rules

These bind **whoever writes the instruction**, not only whoever runs git. A dispatch prompt, task body or plan
must not tell an agent to rebase or amend a pushed branch. Say "bring it up to date with main", which by rule 2
means a merge. (A dispatch that said "rebase on" another PR for an already-pushed lane branch is how this
rule came about.)

1. **Never rewrite history that has been pushed.** No `rebase`, `commit --amend`, `reset` + push, or force push
   (including `--force-with-lease`) on commits that are already on a remote. This applies to every pushed
   branch, including lane and feature branches that only you have worked on.
2. **To bring a branch up to date with main, merge.** Run `git fetch origin` then
   `git merge --no-edit origin/main` on the branch and push normally. Resolve conflicts once, in the merge
   commit. (`--no-edit`: agents have no terminal, so a command that opens an editor can hang or fail.)
   - When GitHub does the update (the "Update branch" button, `gh pr update-branch`, an MCP update-branch tool),
     choose the **merge** option, never the rebase one. The rebase option rewrites the branch on the server and
     no local deny list sees it.
   - If a conflict cannot be resolved with confidence, run `git merge --abort` and raise `clarify`. Never push a
     guessed resolution.
3. **Rebasing is fine on your own unpushed local commits.** For example, `git pull --rebase` before your first push
   of a branch, or tidying local commits before they leave the machine. `git pull --rebase` stays safe even on
   a pushed branch, because it replays only your unpushed commits on top of the remote. The trap is
   `git rebase origin/main` on a pushed branch: that rewrites commits already on the remote. Once a commit has
   been pushed, rule 1 applies. **Check before assuming a commit is unpushed**: tooling may push for you (a commit helper that
   auto-pushes, for example). Before any rebase, run `git status -sb` (ahead/behind) or
   `git branch -r --contains <sha>`. If the commit is on any remote, rule 1 applies.
4. **Where work lands through pull requests, PRs land by squash merge.** The merge commits rule 2 adds to a branch
   disappear when the PR lands, so main stays linear. Teams that commit straight to main have no PR step, and
   rules 1, 2, 3 and 5 still apply to them.
5. **To undo something already pushed, add a revert commit.** Use `git revert --no-edit <sha>` (a merge commit
   needs `-m 1`), never reset and force push. A revert is itself a normal commit, so it goes through the same path as any change (a PR where PRs are
   used). Under squash landing, revert the **squash commit on main**, not the individual branch commits.

## A merge changes the tree — gate results move with it

A gate or review result is valid only for the tree it ran on. After `git merge origin/main`, re-run the checks
on the merged head. Where CI runs on every push, pushing the merge does this; that combined-code run is the point
of merging.

**Never merge with a required check red or pending, and never bypass branch protection or required checks.** A
revert is a change like any other and goes through CI too.

To carry a **review** across a merge without re-reviewing, prove that resolving the merge added nothing of its
own. Compare `git diff <old-base> origin/main` with `git diff <gated-head> <merged-head>`. If they are
byte-identical, the merge brought in exactly main's changes and nothing else. This proves there was no hand-edit
during conflict resolution. It does **not** prove that main's changes and yours pass together, so automated gates
still run on the merged head.

## Recovering when a rewrite was refused

If an agent has already rebased or amended locally and the push is denied:

1. Keep the rewritten head on a **local** backup branch (`git branch <branch>-rewrite-backup`).
2. Reset the branch to what is pushed: `git checkout -B <branch> origin/<branch>`.
3. Merge main (rule 2), re-apply the intended content, prove equivalence with the rewritten head as above, and
   push normally.
4. If that does not work, push a new branch and open a replacement PR.

**Never retry with another force form.** The denial is the answer, not an obstacle.

## Why merge, with agents in particular

- **`--force-with-lease` protects less than it seems.** Without an explicit expected value, it checks the
  remote branch against your remote-tracking ref (`origin/<branch>`), which any `git fetch` updates, including
  the one you run yourself before rebasing. Commits that fetch brought in are not protected: the lease checks
  against the fresh value, passes, and overwrites a peer's commit. It gives no protection for anything the last
  fetch saw. Remote-tracking refs are shared by all worktrees of a repo, so a fetch by another agent in another
  worktree has the same effect. Concurrent agents in worktrees are exactly where the lease fails quietly.
- **Rewritten history breaks other agents' starting points.** Another lane or a CI run may have started from the
  old commits. After a rebase and force push those commits are gone from the remote. A person would notice; an
  agent usually does not, until something fails later.
- **Merge never loses anything.** A bad merge is undone with a revert, and the pushed history shows what happened.
  A rebase resolves conflicts once per commit, which gives more chances to resolve one wrongly without noticing,
  and its undo record (the reflog) exists only on that machine.
- **CI and reviews follow commits.** A force push leaves earlier CI runs pointing at commits that no longer exist
  and marks review comments outdated. A merge commit gets a CI run on the actual combined code, which is the check
  that matters.

## Exceptions — the operator's call, never an agent's

- **Repositories you do not own (upstream / open-source clones) follow the upstream's conventions.** Many
  upstream projects require a rebased PR branch. Updating your own fork branch that way is acceptable when the
  upstream asks for it, but a force push still needs the operator's explicit approval each time, and the
  operator runs it.
- **A pushed history that must be rewritten** (for example a secret committed by mistake — see
  `secrets-handling.md` where present) is an operator action, coordinated with everyone who has the branch. An
  agent that finds such a case raises it (`notify`) and does not attempt the rewrite.

## Enforcement

Two backstops sit under this rule. Neither is the rule.

- **The deny list.** If you maintain a user-level `permissions.deny` list that blocks the common spellings of a
  force push, know that it has gaps: combined short flags (`-uf`), global options before `push` (`git -c …`,
  `--git-dir=…`), some `git -C` forms, and server-side rebases (GitHub's "Update branch → rebase",
  `gh pr update-branch --rebase`, a forced ref update through the API). It also only exists on the machines
  where it is configured.
- **Branch protection.** Protect the default branch with force pushes and deletion disabled. This is what covers
  the deny list's gaps: it also catches a push from a script, another machine, or the server-side forms above.
  Where the host's plan lacks branch protection (e.g. private repos on some free tiers), record that gap rather
  than claim the protection. An agent never turns that protection off.

The rule binds where neither backstop reaches. Do not work around a denial: a denied force push means the plan
needs a merge or a revert instead.

# Dev Team — Team Definition

## Team Members

| Role | Agent | Responsibility |
|------|-------|----------------|
| Operator | *(human)* | Direction, decisions, and final approval |
| Orchestrator | *(Claude Code)* | Coordinates agents, manages workflow, resolves blockers |
| Architect | `architect` | Owns technical design, tech stack, and environment. Advises on testability and iteration scope. Conducts peer reviews. |
| PM | `pm` | Sprint planning, task breakdown, sprint execution, and retrospective. Ensures sprint results meet the standard. |
| Developer | `developer` | Full-stack implementation and testing. Acts on peer reviews. May request task breakdown during planning. |
| Designer | `designer` | Defines look-and-feel. Creates UI elements and graphical assets. |
| Improvement Analyst | `improvement-analyst` | Analyses session transcripts at sprint end. Writes optimization suggestions to the self-improvement log. **Only consulted at the operator's explicit suggestion — do not invoke automatically.** |
| Mascot | `mascot-budgie` | Kiwi the budgie. Optional — may be consulted during planning or retrospectives for a fresh perspective, at oracle-worthy moments. Interpretation required. |

## Ways of Working

- See `.claude/rules/ways-of-working.md` for workflow signals (`clarify`, `notify`, `request`) and orchestrator responsibilities.
- The orchestrator coordinates all agents and resolves blockers before escalating to the operator.

## If this team owns more than one repo

A second repository does **not** imply a second team — a team is a session, a backlog, and an operator
relationship. Keep it as one team, and fix these three things:

- **One control plane.** The `.claude/` scaffold, the backlog, and all orchestration live in the
  **primary** repo; the secondary repo is added as a working directory and gets **no `.claude/` of its
  own** (not a "minimal" one — a partial scaffold there is loaded by nobody and still reads as
  authoritative). It keeps its own `README.md`, gates and CI.
- **One messaging identity**, belonging to the session, if you use cross-team messaging. Do not register the
  secondary repo as a team: it would be a mailbox no session ever reads.
- **One backlog, one planning cadence, one review lane**, with a per-repo tag (`repo:<name>`) on every
  task. The PM, architect and orchestrator span both repos.

**Split trigger** — give the secondary repo its own control plane when its **release cadence naturally
diverges** from the primary's, not when its volume of work grows. Volume is absorbed by lanes; diverging
cadence is what makes one backlog hurt. Name the trigger, give it an owner, and check it at sprint
planning, or it will not fire.

Setup mechanics:

- Start **one session** in the primary repo and add the secondary repo as a working directory
  (`permissions.additionalDirectories`, or `--add-dir` at launch). Never run a second session there.
- Keep the full scaffold (`.claude/agents/`, `rules/`, `skills/`, `settings.json`) in the session root only;
  agents, rules and skills resolve from the session's project directory.
- If you use cross-team messaging, set the team identity once, in the session root's settings.
- Keep one taskmd backlog in the session root, with a `repo:<name>` tag on every task.
- Give the secondary repo its own `README.md`, gates and CI, and no `.claude/` — at most a one-line
  `CLAUDE.md` pointing to the primary repo's session.

## Sprint Rituals

| Ritual | Required Participants |
|--------|-----------------------|
| Sprint Planning | Orchestrator, PM, Architect, Developer, Designer |
| Sprint Retrospective | All agents — Kiwi optional (oracle-worthy moments only) |
| Peer Review | Architect reviews Developer output |
| Sprint-end Analysis | Improvement Analyst reviews session transcripts and files findings — **operator must explicitly request this** |

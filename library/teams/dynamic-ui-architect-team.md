# Dynamic UI Architect Team — Team Definition

## Team Members

| Role | Agent | Responsibility |
|------|-------|----------------|
| Operator | *(human)* | Direction, decisions, and final approval |
| Orchestrator | *(Claude Code)* | Coordinates agents, manages workflow, resolves blockers |
| Architect | `architect` | Owns overall architecture, tech stack selection, interface design between layers, testability strategy, and peer review. Leads the planning phase and consults at major milestones. |
| PM | `pm` | Sprint planning, task breakdown, sprint execution, and retrospective. Ensures sprint results meet the standard. |
| Dynamic UX Designer | `dynamic-ux-designer` | Owns the design vision and motion language. Designs interfaces as physical systems — fields, inertia, attractors, impulse/decay. Produces motion tokens, control interaction models, and field/space designs. |
| Svelte UI Engineer | `svelte-ui-engineer` | Implements Svelte 5 components, Threlte 3D scenes, and Canvas/WebGL rendering layers. Owns the 60fps rendering pipeline and data paths from WASM/AudioWorklet sources. |

## Ways of Working

- See `.claude/rules/ways-of-working.md` for workflow signals (`clarify`, `notify`, `request`) and orchestrator responsibilities.
- The Architect leads the planning phase and defines interface boundaries before implementation begins. No implementation agent starts work until the architecture and API contracts are agreed.
- The Dynamic UX Designer and Svelte UI Engineer collaborate closely — motion ideas must be validated for 60fps feasibility with the engineer before being committed to the design vision.
- The Architect performs peer review on interface definitions, component architecture, and any cross-boundary contracts.

## If this team owns more than one repo

A second repository does **not** imply a second team — a team is a session, a backlog, and an operator
relationship. Keep it as one team, and fix these three things:

- **One control plane.** The `.claude/` scaffold, the backlog, and all orchestration live in the
  **primary** repo; the secondary repo is added as a working directory and gets **no `.claude/` of its
  own** (not a "minimal" one — a partial scaffold there is loaded by nobody and still reads as
  authoritative). It keeps its own `README.md`, gates and CI.
- **One messaging identity**, if you use cross-team messaging: it belongs to the session. Do not
  register the secondary repo as a team: it would be a mailbox no session ever reads.
- **One backlog, one planning cadence, one review lane**, with a per-repo tag (`repo:<name>`) on every
  task. The PM, architect and orchestrator span both repos.

**Split trigger** — give the secondary repo its own control plane when its **release cadence naturally
diverges** from the primary's, not when its volume of work grows. Volume is absorbed by lanes; diverging
cadence is what makes one backlog hurt. Name the trigger, give it an owner, and check it at sprint
planning, or it will not fire.

Setup mechanics:

- Run **one session**, started in the primary repo, with the other repo added as a working directory
  (`permissions.additionalDirectories`, or `--add-dir` at launch).
- The scaffold (`.claude/agents/`, `rules/`, `skills/`, `settings.json`) lives **only in the session root**.
- Keep **one backlog**, in the session root, with a `repo:<name>` tag on every task.
- The secondary repo gets its own `README.md` and CI, and **no `.claude/`**.

## Sprint Rituals

| Ritual | Required Participants |
|--------|-----------------------|
| Planning Phase | Orchestrator, Architect, PM, Dynamic UX Designer, Svelte UI Engineer |
| Sprint Planning | Orchestrator, PM, Architect (for architectural tasks), Dynamic UX Designer, Svelte UI Engineer |
| Sprint Retrospective | All agents |
| Peer Review | Architect reviews interface definitions and cross-boundary contracts; Dynamic UX Designer reviews Svelte UI Engineer output for visual/motion correctness |
| Architecture Review | Architect consulted at project start and at each major milestone |

## Skills Available

| Skill | Used by | Purpose |
|-------|---------|---------|
| `dembrandt` | Dynamic UX Designer | Extract design tokens (colours, typography, spacing) from reference interfaces to use as a starting point |

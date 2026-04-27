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
| Mascot | `mascot-budgie` | Kiwi the budgie. Consulted during planning and retrospectives for a fresh perspective. Interpretation required. |

## Ways of Working

- See `.claude/rules/ways-of-working.md` for workflow signals (`clarify`, `notify`, `request`) and orchestrator responsibilities.
- The orchestrator coordinates all agents and resolves blockers before escalating to the operator.

## Sprint Rituals

| Ritual | Required Participants |
|--------|-----------------------|
| Sprint Planning | Orchestrator, PM, Architect, Developer, Designer |
| Sprint Retrospective | All agents — Kiwi **must** be consulted |
| Peer Review | Architect reviews Developer output |
| Sprint-end Analysis | Improvement Analyst reviews session transcripts and files findings — **operator must explicitly request this** |

# Ways of Working
The main mode of working is interactive collaboration between the operator and the orchestrator. The orchestrator may engage subagents to complete requests. 

## Subagent Workflow Signals
Any subagent may return these pre-defined signals to the orchestrator. Based on the signal, the orchestrator should first attempt to work with agents to handle the signal, but may eventually decide to involve the operator for direction. 

These are the pre-defined signals: 

1. "clarify": Any agent may return a "clarify" signal to the orchestrator, alongside additional information, if they encounter something that requires additional information to complete a task.
    - The orchestrator should first try to resolve the question with relevant subagents. For example, an agent focused on coding may request clarification from an agent focused on UX design.
2. "notify": Any agent may return a "notify" signal to the orchestrator, alongside additional information, if they encounter a decision, a learning or a blocker that they believe might impact sprint tasks, future decisions
3. "request": At the end of a task, any agent may request input or work to be done by another agent, through the orchestrator

## Project Root is Off-Limits

**Agents MUST NOT create or write any files directly in the project root.** The project root belongs to the upstream codebase and must remain unmodified except by explicit developer commits.

All agent output must go into designated subfolders:
- Documentation → `@/documentation` (per `documentation-structure.md`)
- Sprint results and retrospectives → `@/project-docs/sprint-outcomes/`
- Plans, architecture notes → `@/project-docs`
- Tasks → `@/tasks`

If an agent believes it needs to write to the project root, it MUST raise a `clarify` signal to the orchestrator instead of proceeding. The orchestrator must confirm the correct target path before the agent writes anything.

## FOR ORCHESTRATOR ONLY
- If agents are blocked or raise the "clarify" or "notify" signals, try to resolve by yourself or through agents, before involving the operator.
- **Capturing operator direction signals**: Whenever the operator provides significant directional input outside of a sprint doc — a product decision, a correction to the team's understanding, a priority shift, an architectural preference, or a vision statement — write a one-line entry to the Signal Capture Log table in `project-docs/operator-profile.md`. If the file does not exist, create it with just this section:
  ```markdown
  ## Signal Capture Log
  | Date | Signal | Context |
  |------|--------|---------|
  ```
  Then add the entry: `| YYYY-MM-DD | <one-sentence summary> | <brief context — what prompted it> |`
  This log is a long-running record of the operator's intent and is valuable regardless of which agents are active in the project. Do not log routine status checks, approvals of already-written plans, or administrative instructions — only record input that reveals something about the operator's direction or priorities that is not already in a project doc.
- **End-of-sprint git commit**: After the sprint result file is written and accepted, ask the operator whether to commit and push the sprint's changes. If the operator agrees, delegate to the developer agent to stage relevant files, write a concise commit message summarising the sprint deliverables, and push to the remote branch. Do not commit or push without explicit operator approval.

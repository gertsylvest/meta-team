# Ways of Working
The project is executed iteratively in sprint + retrospective pairs, following an initial planning and research phase which documents the overall objectives, outcomes, and sequencing with key milestones. 
Sprints may result in requests for "spikes", which are research or testing spikes that will inform future decisions. 

## Project Phases
0. "Exploration Phase": Ad-hoc research that may or may not lead into a formal planning phase. 
    - This phase can be invoked at any time — including from within a running sprint or any other phase.
    - Conduct or delegate research as needed (technologies, competitors, open questions)
    - Before moving forward from exploration into any other phase, confirm with the operator that it is ok to proceed
    - If jumping back into exploration from another phase (e.g. mid-sprint), confirm with the operator before resuming that phase
1. "Planning phase": Orchestrator works with relevant agents and the operator to create the initial project plan in "plan mode", which is the most interactive phase. 
    - It may include research of existing development environment, relevant technologies, or competing projects, depending on the project needs.
    - The outcome is the "project plan" documents, see below.
    - The architect MUST define a **Testing and Feedback Strategy** as a planning-phase deliverable, documented in `@/project-docs/architecture.md`. This strategy must address how agents will actively observe and diagnose the running system — not only prevent failures through unit tests. For projects where automated test execution is constrained (e.g. visual output, audio, hardware platforms, external runtimes), the strategy MUST specify instrumentation approaches that allow agents to observe runtime state without relying on the operator's verbal descriptions. Examples: configurable log levels that agents can toggle without code changes, structured state-dump logs (positions, values, timestamps) suitable for agent post-processing, debug modes that expose internal state, and other observable output artifacts. The aim is to maximise agent-driven diagnosis and minimise operator-mediated feedback loops. This strategy must be reviewed and updated at the start of each sprint if the platform or observability approach has changed.
    - Also, the first "sprint" must be defined and numbered, and broken down into tasks — all taskmd tasks for all agents must be created before the sprint begins.
2. "Sprint": The project is delivered iteratively in sprints which have specific objectives, linked to the "project plan" milestones.
    - A sprint MUST be preceded by a "sprint planning" phase, which may involve relevant agents and the operator to produce the sprint goals and the full sprint backlog.
    - **Complete backlog before work begins**: sprint planning MUST produce a taskmd task for every unit of work, for every agent, covering the full sprint. No agent may begin any work until all sprint tasks exist in taskmd. Creating tasks after the fact — to describe work already done — is explicitly forbidden.
    - The sprint MUST NOT begin until: (1) all sprint tasks are created in taskmd, and (2) the operator has accepted the sprint goals.
    - **Task status discipline**: Valid taskmd statuses are `pending`, `in-progress`, `completed`, `in-review`, `blocked`, and `cancelled` — `done` is NOT a valid status. Any agent MUST mark a task as `in-progress` before beginning work on it, and MUST use `completed` (not `done`) when finishing. A task MUST NOT be marked `completed` without first having been marked `in-progress`. The PM must flag any task that skips `in-progress` or uses an invalid status as a process violation and reopen it.
    - A sprint must always deliver something testable or demonstratable, including the "sprint result" file. The sprint result file is produced by the PM as the final step of the Sprint End Workflow — no other agent is responsible for it. The orchestrator MUST explicitly invoke the PM to run the Sprint End Workflow when sprint tasks appear complete; the sprint is not self-closing.
    - **Definition of Done — acceptance criteria**: before a sprint can close, the PM MUST explicitly verify every acceptance criterion for every completed task. Verification means checking actual output or evidence — not re-reading the task description. A task is not done until all its criteria are demonstrably met. If any criterion is unmet, the PM must either extend the sprint to address it or escalate to the operator — silently closing a task with unmet criteria is forbidden.
    - **Definition of Done — sprint goal**: after all tasks are verified, the PM MUST confirm that the sprint goal as a whole is met. Individual tasks passing does not automatically mean the sprint goal is achieved. If there is a gap, the PM must raise it with the operator before closing the sprint.
    - **Definition of Done — testing**: every sprint that delivers new functionality MUST include tests written for that functionality. The sprint cannot close until, for every piece of new functionality: (1) tests have been written, (2) tests have been executed, and (3) results have been validated. All three steps are required — a sprint cannot close with untested new functionality.
    - **Test infrastructure failures are hard blockers**: if an automated test exists but could not be executed due to an infrastructure problem (missing environment variable, broken toolchain, missing path, misconfigured tool), this counts as a test failure — not as grounds to skip the test or substitute manual validation. The sprint cannot close until the infrastructure issue is resolved and the automated test executes and passes. An agent reporting "tests couldn't run" is reporting a blocker, not a completed task.
    - **Browser testing with Playwright**: every task that delivers UI components or changes visual behaviour MUST be validated using the Playwright MCP tools (`mcp__playwright__*`) as part of its acceptance criteria. This is a hard requirement — it is not optional and cannot be deferred. The agent responsible for a UI task must: (1) navigate to the running dev server, (2) take a screenshot or use `browser_snapshot` to inspect the rendered output, and (3) interact with the component (click, double-click, keyboard) to verify behaviour. The task is not done until Playwright confirms the component renders and behaves correctly. Playwright validation replaces the need to escalate routine UI checks to the operator — only novel or ambiguous visual decisions require operator input.
    - **Manual validation**: if any acceptance criterion or test requires manual execution *by nature* (e.g. UI flows, user-facing behaviour, hardware interaction), the PM MUST raise a `notify` signal to the orchestrator. The orchestrator MUST then ask the operator to perform the validation and confirm the result. The sprint cannot close until the operator has confirmed all manual validation results. This is a hard requirement — it cannot be skipped or deferred. **Manual validation is not a fallback for automated tests that failed to run** — it applies only to tests that are inherently manual.
    - **Definition of Done — no avoidable operator delegation**: Before a sprint can close, the PM MUST verify that no acceptance criterion or delivery step delegates to the operator work that an agent could perform automatically (e.g. build steps, file copies, deployment commands, script execution). If any such step is found, the PM MUST raise a `notify` signal so the responsible agent automates it before the sprint closes. Only work that is genuinely impossible to automate (e.g. physical hardware interaction requiring human presence, account logins with no available credentials) may be delegated to the operator, and this must be explicitly justified in the sprint result file.
    - It is ok to add a "spike" to a running sprint — but the spike tasks must be created in taskmd before spike work begins
3. "Peer review": A sprint must include and pass at least one "peer review" if code has been produced, before the sprint can be concluded.
4. "Retrospective": At the end of each sprint, a retrospective is conducted by the PM, who involves the other agents to gather feedback. The orchestrator's role is to ensure the retrospective happens — not to facilitate it directly. The PM presents the retrospective outcome to the orchestrator and operator.
    - If a mascot subagent is present in the team, any member of the team may ask it for opinions and advice. This step is only applicable when a mascot agent is part of the team — it is not a required retrospective step otherwise.
5. "Spike": Based on the retrospective or other insights, a "spike" may be conducted as an isolated research or prototyping phase. It MUST be defined as a set of tasks associated with a specific sprint (current or future).

## Subagent Workflow Signals
Any subagent may return these pre-defined signals to the orchestrator. Based on the signal, the orchestrator should first attempt to work with agents to handle the signal, but may eventually decide to involve the operator for direction. 
These are the pre-defined signals: 

- "clarify": Any agent may return a "clarify" signal to the orchestrator, alongside additional information, if they encounter something that requires additional information to complete a task.
    - The orchestrator should first try to resolve the question with relevant subagents. For example, an agent focused on coding may request clarification from an agent focused on UX design.
- "notify": Any agent may return a "notify" signal to the orchestrator, alongside additional information, if they encounter a decision, a learning or a blocker that they believe might impact sprint tasks, future decisions. This signal MUST be raised when manual testing is required — include what needs to be tested and what the expected result is. **Sprint closed**: when the PM completes the Sprint End Workflow (all tasks verified, sprint result written, retrospective done), the PM MUST send a `notify` signal to the orchestrator confirming the sprint is officially closed and stating the path of the sprint result file.
- "request": At the end of a task, any agent may request input or work to be done by another agent, through the orchestrator. **Sprint work done**: when an agent believes they have completed all their sprint tasks, they MUST send a `request` signal to the PM (not the orchestrator) stating their sprint work is complete, so the PM can verify and track overall sprint progress.

## Project Root is Off-Limits

**Agents MUST NOT create or write any files directly in the project root.** The project root belongs to the upstream codebase and must remain unmodified except by explicit developer commits.

All agent output must go into designated subfolders:
- Documentation → `@/documentation` (per `documentation-structure.md`)
- Sprint results and retrospectives → `@/project-docs/sprint-outcomes/`
- Plans, architecture notes → `@/project-docs`
- Tasks → `@/tasks`

If an agent believes it needs to write to the project root, it MUST raise a `clarify` signal to the orchestrator instead of proceeding. The orchestrator must confirm the correct target path before the agent writes anything.

## Ensure Low Coupling
- Agents MUST each contribute to ensure that logically separated modules of the solution (i.e. code sections that can be worked on with limited need for context outside of the module or the "project plan") are described in a **README.md** at their root, that provides enough context to quickly for an agent to understand the module structure, key folders, and key dependencies to entities outside of the module.
- Agents MUST iteratively update this at least at the end of each sprint

## FOR ORCHESTRATOR ONLY
- During the "Planning Phase", ensure that the documentation folder structure is set up as described in the "documentation-structure.md" rule file.
- If agents are blocked or raise the "clarify" or "notify" signals, try to resolve by yourself or through agents, before involving the operator.
- **Sprint closure handoff**: When all sprint tasks appear complete (agents have sent `request: sprint work done` signals to the PM, or all tasks show `completed` in taskmd), the orchestrator MUST explicitly invoke the PM to run the Sprint End Workflow. Do NOT assume the sprint is closed because tasks are marked completed — only the PM's `notify: sprint closed` signal counts as official closure. Do NOT start the next sprint or move to retrospective until the PM has confirmed sprint closure and presented to the operator.
- **End-of-sprint git commit**: After the sprint result file is written and accepted, ask the operator whether to commit and push the sprint's changes. If the operator agrees, delegate to the developer agent to stage relevant files, write a concise commit message summarising the sprint deliverables, and push to the remote branch. Do not commit or push without explicit operator approval.

### Orchestrator Logging Requirements
- **Capturing operator direction signals**: Whenever the operator provides significant directional input outside of a sprint doc — a product decision, a correction to the team's understanding, a priority shift, an architectural preference, or a vision statement — write a one-line entry to the Signal Capture Log table in `project-docs/operator-profile.md`. If the file does not exist, create it with just this section:
  ```markdown
  ## Signal Capture Log
  | Date | Signal | Context |
  |------|--------|---------|
  ```
  Then add the entry: `| YYYY-MM-DD | <one-sentence summary> | <brief context — what prompted it> |`
  This log is a long-running record of the operator's intent and is valuable regardless of which agents are active in the project. Do not log routine status checks, approvals of already-written plans, or administrative instructions — only record input that reveals something about the operator's direction or priorities that is not already in a project doc.

## Other advice
- If a mascot agent is part of the team: the team will need to pay attention to the mascot's vocalizations and body language to fully understand its responses. Its responses are always valuable, even if they are not in human language.
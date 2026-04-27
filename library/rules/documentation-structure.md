# Documentation Structure

## The "documentation folder"
1. The "documentation folder" holds written documentation created by any subagent, and MUST BE stored in the folder @/project-docs
2. Any product documentation created, which is not the "project plan", should be created under the subfolder @/project-docs/project-documentation
3. It is ok for the orchestrator or subagents to create sub-folders under @/project-docs/project-documentation to improve the structure

## Sprint Definition
"Sprints" are defined using a special "sprint task" using add-task, which must include:
- the **sprint number**
- a **sprint objective**
- a set of **desired outcomes** or deliverables
- a **definition of done** which could include e.g. the fidelity of the solution
- a short **sprint description**
- a tag "sprint-{{sprint_number}}", to enable searching and filtering within a specific sprint

## Tasks
"Tasks" (including the "sprint" tasks) MUST be documented taskmd skills (add-task, complete-task, do-task, get-task-status, get-task, list-tasks, import-todos, next-task, split-task, update-task, validate-tasks and verify-task). They MUST NOT use the claude internal task system. 

## Project Plan
The "Project plan" MUST have the following documents, stored under @/project-docs
    - @/project-docs/development-environment.md holds key decisions on the development environment, updated continuously.
    - @/project-docs/architecture.md holds key decisions on architecture, technical design (such as interface design), tech stack, and the project's **Testing and Feedback Strategy** (see ways-of-working.md).
    - @/project-docs/milestone-plan.md holds high-level design- and implementation milestone plan, which is iteratively be updated.
    - @/project-docs/design-vision.md holds ´he design vision, goals and anti-goals

## Project Documentation
- Information that backs up or is important for understanding key decisions must be written in a very short and concise way to a markup file under the @/project-docs/documentation subfolder. 
- Logically separated modules of the solution (i.e. code sections that can be worked on with limited need for context outside of the module or the "project plan") MUST have a **README.md** at their root, that provides enough context to quickly for an agent to understand the module structure, key folders, and key dependencies to entities outside of the module.

## Sprint Results
Sprint result and retrospective files MUST be stored in `@/project-docs/sprint-outcomes/`. Create this folder if it does not yet exist.

1. "sprint result" files, named "sprint-{{sprint_number}}-result.md" which MUST be stored in `@/project-docs/sprint-outcomes/`, and include:
    - A short description of the outcomes of the sprint
    - List any shortcomings (tasks that were deferred, achieved only partially, or that did not meet their completion criteria, and so on)
    - A short description of how to demonstrate the outcomes of the sprint, e.g. via an automatic test or manual test file, or user instructions on how to validate the outcome.
2. "Retrospective files" are markdown files written by the orchestrator by taking input from each agent after the completion **of each sprint**, named "retrospective-sprint-{{sprint_number}}.md", MUST be stored in `@/project-docs/sprint-outcomes/`, and should include:
    - The title "retrospective {{sprint_number}}"
    - "start": Things (if any) the team should start doing, i.e. suggesting improvements that the subagent or orchestrator believes would improve the effectiveness of the agent or the team, such as process changes, requesting access to tools etc. 
    - "stop": Things (if any) that the subagent believes the team should stop doing in order to increase effectiveness
    - "skill": Suggestion by any agent of a skill that could have sped up a repetitive 'trial-and-error' process, or significantly have reduced the effort or number of steps required to complete a subtask.
    - "suggestion": The orchestrator should synthesize 1-3 specific, actionable change recommendations based on the agent feedback for implementation in the next sprint.

## Project Root README
Every project folder MUST have a `README.md` at the project root that:
- Briefly describes the top-level folder structure (what each folder is for)
- Points out key documents (e.g. architecture, design vision, milestone plan, latest sprint outcome)
- Notes any separate compilation units or significant submodules
- Is written for an audience of Claude or a developer wanting a quick structural orientation — not end-user documentation

The PM MUST review this file as part of the Sprint End Workflow and update it if and only if:
- The project's top-level folder structure has changed (new or removed folders)
- New key technical design documents or architectural decisions have been added

Routine sprint activity (new sprint result files, task changes, minor code additions) does NOT warrant updating the README.


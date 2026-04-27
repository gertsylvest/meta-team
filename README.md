# meta-team

A curated library of AI agent definitions, orchestrators, skills, and rules — plus a bootstrapping workflow for assembling them into project teams. The goal is to capture effective ways of working for human-AI collaboration in a single place, and to make spinning up a well-structured AI team as low-friction as possible.

---

## Motivation

AI teams need effective ways of working. It is a collaboration between a human operator and a team of agents.

AI teams have some **unique characteristics** related to the **nature of the technology**:
- Exceptional breadth and depth of knowledge, but paired with model-specific limitations, hallucination risks
- Floating and sometimes unpredictable costs
- Somewhat opaque inter-agent collaboration and communication protocols, very different than human protocols
- Alternative and limited senses (agent harness, toolset, limited vision, limited auditory and tactile capabilities)

But they share an even **longer list of challenges with regular human teams**:
- Intent and objective drift
- Communication challenges between participants with different professional, knowledge, and personality backgrounds
- Cognitive overload, 'context rot', process fatigue, and forgetting conventions and agreements
- Misunderstandings, guessing, over-confidence
- Constantly changing context, insights and objectives

The tools to address most of these already exist in the agile toolbox: quick value-release cycles, clear roles, recurring alignment between team and stakeholders, decoupling of intent and implementation (user stories), self-improvement loops (retrospectives), and a set of backlog and priority management practices that have been battle-tested on human teams.

This is what the meta-team is about:
- Capturing those ways of working in a form that agent teams understand, in a single place
- Providing a flexible mechanism for bootstrapping projects that assemble teams, skills, and ways of working, while minimising human error in the process

A conversation with the meta-team is about bootstrapping new projects with the right teams and the right guidance — and continuously capturing learnings from running those teams in a way that benefits all future projects.

---

## How it works

The meta-team operates in two modes:

**Library mode** — defining and refining agents, skills, rules, and orchestrators, and promoting them to the library when ready. Learnings from one project feed back into the library for all future teams.

**Bootstrap mode** — a guided conversation that understands a new project's needs, selects the right agents and rules from the library, and scaffolds the project folder, CLAUDE.md, and git repository via a single script.

---

## How bootstrapped projects run

Projects follow a lightweight agile model: an initial planning phase produces a milestone plan and sprint backlog, then the team executes in sprint cycles — planning → sprint → peer review → retrospective. Sprints are tracked with taskmd, with every unit of work defined as a task before any agent begins.

Agents communicate back to the orchestrator using three signals: **clarify** (needs information to proceed), **notify** (a decision, learning, or blocker worth surfacing), and **request** (asking for work from another agent). The orchestrator resolves most signals without operator involvement — the operator's role is to approve sprint goals, provide direction when the team is genuinely blocked, and confirm manual validation results. Day-to-day execution is fully delegated.

---

## Reducing operator bottleneck

Working with AI teams makes one thing viscerally clear: **the operator is the bottleneck**. The agent team can execute in minutes; the operator spends 10–50× that time on reviews, direction, and decisions. Two agents in this library are specifically designed to shrink that gap:

**operator-proxy** builds and maintains a structured profile of the operator — decisions made, non-negotiables, patterns, sensitivities — synthesised from sprint docs and conversation history. Agents use this to make proxy decisions without interrupting the operator.

**operator-interviewer** closes direction gaps efficiently: rather than asking open questions, it reads what is already known, identifies the genuine gaps, and presents structured option-led questions the operator can answer in minutes. It then synthesises the response into an actionable brief the team can execute against immediately.

The underlying motivation is twofold: to learn practically how to reduce the operator's time-in-loop, and to crystallise more clearly where the operator's intuition is truly irreplaceable — versus where the team can independently decide and act.

---

## Repository structure

```
/library        — promoted, reviewed definitions (agents, orchestrators, skills, rules, teams)
/workspace      — staging area for drafts under review
/templates      — CLAUDE.md and settings templates used when bootstrapping
/scripts        — new-project.sh, the bootstrap scaffolding script
/documentation  — internal notes
```

---

## Prerequisites

- **taskmd** — task and sprint backlog management. Requires `.taskmd.yaml` at the project root pointing to `/tasks`. To view backlogs in the browser: `taskmd web start --open --port 8080`
- **GitHub MCP** — structural code search across GitHub-hosted repos without cloning. Install via the [GitHub MCP guide](https://github.com/github/github-mcp-server/blob/main/docs/installation-guides/install-claude.md); requires a fine-grained PAT with public repositories read-only scope.
- **ast-grep** — structural code search (finds all calls to a function, all implementations of an interface, etc.). Install: `brew install ast-grep`
- **universal-ctags** — builds a symbol index across a repo for instant file/line lookup. Install: `brew install universal-ctags`
- **jq** — query JSON configs (package.json, tsconfig, etc.) without reading the whole file. Install: `brew install jq`

# Faust Exploration Team — Team Definition

## Team Members

| Role | Agent | Responsibility |
|------|-------|----------------|
| Operator | *(human)* | Direction, decisions, and final approval |
| Orchestrator | *(Claude Code)* | Coordinates agents, manages workflow, resolves blockers |
| Audio Architect | `audio-architect` | Owns technical design — framework selection (Faust architecture files, DSP/driver split), layer boundaries, cross-platform strategy. Reviews implementation for architectural correctness. |
| PM | `pm` | Sprint planning, task breakdown, sprint execution, and retrospective. Ensures sprint results meet the standard. |
| C Audio Engineer | `c-audio-engineer` | Implements and reviews C DSP code generated from Faust, cross-platform build configuration, and the DSP/driver layer boundary. |
| WASM Audio Engineer | `wasm-audio-engineer` | Compiles Faust-generated C/C++ to WebAssembly via Emscripten; manages AudioWorklet signal chains. Not active in early sprints — brought in when the project moves to browser targets. |
| Codebase Analyst | `codebase-analyst` | Analyses the Faust compiler and library repos to produce targeted orientation documents. Primarily active in the first sprint to map the Faust codebase for the rest of the team. |

## Ways of Working

- See `.claude/rules/ways-of-working.md` for workflow signals (`clarify`, `notify`, `request`) and orchestrator responsibilities.
- The orchestrator coordinates all agents and resolves blockers before escalating to the operator.
- The Codebase Analyst analyses the Faust repos at `~/dev/audiospace/faust/` and `~/dev/audiospace/faustlibraries/` and writes findings to `project-docs/codebase-analysis/`.
- The C Audio Engineer and WASM Audio Engineer collaborate on any code that crosses the Faust-generated DSP / driver boundary.

## Sprint Rituals

| Ritual | Required Participants |
|--------|-----------------------|
| Sprint Planning | Orchestrator, PM, Audio Architect, C Audio Engineer |
| Sprint Retrospective | All agents |
| Peer Review | Audio Architect reviews C Audio Engineer output |
| Architecture Review | Audio Architect consulted at project start and at each major milestone |
| Codebase Analysis | Codebase Analyst — first sprint only (unless new repos need mapping) |

## Skills Available

| Skill | Used by | Purpose |
|-------|---------|---------|
| `audio-fft-sanity` | C Audio Engineer | FFT-based sanity checks on synthesizer output — fundamental frequency, THD, SNR, clipping |
| `wasm-module-inspect` | WASM Audio Engineer | Validates compiled `.wasm` binaries when the project moves to browser targets |

# Dynamic UI Team — Team Definition

## Team Members

| Role | Agent | Responsibility |
|------|-------|----------------|
| Operator | *(human)* | Direction, decisions, and final approval |
| Orchestrator | *(Claude Code)* | Coordinates agents, manages workflow, resolves blockers |
| PM | `pm` | Sprint planning, task breakdown, sprint execution, and retrospective. Ensures sprint results meet the standard. |
| Dynamic UX Designer | `dynamic-ux-designer` | Owns the design vision and motion language. Designs interfaces as physical systems — fields, inertia, attractors, impulse/decay. Produces motion tokens, control interaction models, and field/space designs. |
| Svelte UI Engineer | `svelte-ui-engineer` | Implements Svelte 5 components, Threlte 3D scenes, and Canvas/WebGL rendering layers. Owns the 60fps rendering pipeline and data paths from WASM/AudioWorklet sources. |

## Ways of Working

- See `.claude/rules/ways-of-working.md` for workflow signals (`clarify`, `notify`, `request`) and orchestrator responsibilities.
- The orchestrator coordinates all agents and resolves blockers before escalating to the operator.
- The Dynamic UX Designer and Svelte UI Engineer collaborate closely — motion ideas must be validated for 60fps feasibility with the engineer before being committed to the design vision.

## Sprint Rituals

| Ritual | Required Participants |
|--------|-----------------------|
| Sprint Planning | Orchestrator, PM, Dynamic UX Designer, Svelte UI Engineer |
| Sprint Retrospective | All agents |
| Peer Review | Dynamic UX Designer reviews Svelte UI Engineer output for visual/motion correctness; Svelte UI Engineer reviews Designer output for rendering feasibility |

## Skills Available

| Skill | Used by | Purpose |
|-------|---------|---------|
| `dembrandt` | Dynamic UX Designer | Extract design tokens (colours, typography, spacing) from reference interfaces to use as a starting point |
| `audio-fft-sanity` | Svelte UI Engineer | FFT-based validation of audio output — confirms rendered signal chain is producing correct output before visual display is built on top |

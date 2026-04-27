# Audio Prototype Team — Team Definition

## Team Members

| Role | Agent | Responsibility |
|------|-------|----------------|
| Operator | *(human)* | Direction, decisions, and final approval |
| Orchestrator | *(Claude Code)* | Coordinates agents, manages workflow, resolves blockers |
| Audio Architect | `audio-architect` | Owns technical design — framework selection, layer boundaries, engine/UI split, cross-platform strategy. Reviews implementation for architectural correctness. |
| PM | `pm` | Sprint planning, task breakdown, sprint execution, and retrospective. Ensures sprint results meet the standard. |
| C Audio Engineer | `c-audio-engineer` | Implements and reviews C DSP code, cross-platform build configuration, and the DSP/driver layer boundary. |
| WASM Audio Engineer | `wasm-audio-engineer` | Compiles C audio libraries to WebAssembly via Emscripten, manages AudioWorklet signal chains, and handles dynamic WASM module loading. |

## Ways of Working

- See `.claude/rules/ways-of-working.md` for workflow signals (`clarify`, `notify`, `request`) and orchestrator responsibilities.
- The orchestrator coordinates all agents and resolves blockers before escalating to the operator.
- The C Audio Engineer and WASM Audio Engineer collaborate closely — changes to the C DSP layer must be coordinated with the WASM Audio Engineer before the Emscripten build is updated.

## Sprint Rituals

| Ritual | Required Participants |
|--------|-----------------------|
| Sprint Planning | Orchestrator, PM, Audio Architect, C Audio Engineer, WASM Audio Engineer |
| Sprint Retrospective | All agents |
| Peer Review | Audio Architect reviews C Audio Engineer and WASM Audio Engineer output |
| Architecture Review | Audio Architect consulted at project start and at each major milestone |

## Skills Available

| Skill | Used by | Purpose |
|-------|---------|---------|
| `audio-fft-sanity` | C Audio Engineer, WASM Audio Engineer | FFT-based sanity checks on audio output — fundamental frequency, THD, SNR, clipping, silence |
| `wasm-module-inspect` | WASM Audio Engineer | Validates a compiled `.wasm` binary — exports, SIMD, threading, binary size |

---
name: wasm-worklet-smoke
description: Headless Playwright smoke test for an Emscripten + AudioWorklet WASM build. Builds the WASM target, serves it locally, launches headless Chrome, clicks Start Audio, verifies the engine initialises without console errors, and checks for non-silent audio output.
allowed-tools: Bash
argument-hint: "[--build-dir DIR] [--port N] [--freq HZ] [--make-target TARGET] [--no-rebuild] [--no-audio-check]"
---

# WASM Worklet Smoke Test

Automated headless verification of an Emscripten + AudioWorklet build. Catches the class of failures that require a browser to surface: worklet registration failures, Emscripten runtime errors (`self is not defined`, `fetch is not a function`), WASM instantiation failures, and silent audio output.

Covers the gaps in a basic log-message-only smoke test: verifies actual audio output is non-silent, verifies the parameter message path, and catches all `console.error` / unhandled rejection events.

## Requirements

- **Node.js** 18+ and **npm**
- **Playwright** with Chromium: `npm install playwright && npx playwright install chromium`
- **Python 3** (for the HTTP server)
- **make** with a WASM build target (default: `synth-wasm`)
- **Project setup**: `main.js` must expose `window.__audioCtx` and `window.__synthNode` for audio verification (see Project Setup below)

## Project setup

The audio verification step reads `audioCtx` and `synthNode` from `window`. The IIFE in `main.js` hides these by default. Add the following lines inside the IIFE after the `AudioWorkletNode` is connected and ready:

```js
// Expose for automated testing (safe: AudioWorkletGlobalScope is isolated)
if (typeof window !== 'undefined') {
    window.__audioCtx  = audioCtx;
    window.__synthNode = synthNode;
}
```

Guard with `window.__TEST_MODE` if you prefer to enable this only during tests:

```js
if (window.__TEST_MODE) {
    window.__audioCtx  = audioCtx;
    window.__synthNode = synthNode;
}
```

If the audio check is not needed, pass `--no-audio-check` to skip this step and the project setup requirement.

## Instructions

Arguments are in `$ARGUMENTS`. Pass them directly to the smoke test script:

```bash
node "$(dirname "$0")/smoke.js" $ARGUMENTS
```

## What the test verifies

| Check | What it catches |
|-------|-----------------|
| Build succeeds | Compilation errors in any source file, missing include paths |
| Server starts | Broken asset copy, missing `synth.js` / `synth.wasm` |
| `WASM engine initialised` log | Worklet registered, WASM instantiated, `onRuntimeInitialized` fired |
| Zero `console.error` events | Any runtime JS error in the worklet or main thread |
| Zero `pageerror` events | Uncaught exceptions |
| Non-silent audio (AnalyserNode) | Silent engine (stuck envelope, null DSP output, broken `computeSynth` call) |
| Expected fundamental frequency | Wrong oscillator frequency, detuning bug, wrong default param |

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `--build-dir DIR` | `build/web` | Directory containing `synth.js` and `synth.wasm` |
| `--port N` | `8001` | Port for the local HTTP server |
| `--freq HZ` | `440` | Expected fundamental frequency in Hz. Set to `0` to skip frequency check. |
| `--make-target TARGET` | `synth-wasm` | Make target to build (skipped with `--no-rebuild`) |
| `--no-rebuild` | off | Skip `make <target>`, use existing build artifacts |
| `--no-audio-check` | off | Skip AnalyserNode audio capture step |
| `--timeout MS` | `15000` | Timeout waiting for engine initialisation |
| `--capture-delay MS` | `200` | Delay after engine ready before capturing audio (allows envelope decay tail) |

## Exit codes

- `0` — all checks passed
- `1` — build failed, engine did not initialise, console errors detected, or audio checks failed

## Examples

```bash
# Standard run: build, serve, test
node smoke.js

# Skip rebuild (fast re-check after a CSS-only change)
node smoke.js --no-rebuild

# Different expected pitch, custom build dir
node smoke.js --freq 880 --build-dir dist/web

# Minimal check without audio verification
node smoke.js --no-audio-check
```

## Adding to make

```makefile
test-wasm: synth-wasm
	node tests/smoke_wasm.js --no-rebuild
```

## Notes

- **`ENVIRONMENT=worker` limitation**: Emscripten has no `audioworklet` environment. `ENVIRONMENT=worker` is the closest option but still assumes `self`, `self.location`, and `fetch()` are available. These are absent in `AudioWorkletGlobalScope`. The known-working mitigation is a `--pre-js` polyfill for `self`/`self.location` and main-thread WASM compilation passed via `processorOptions`. This test will surface failures caused by missing polyfills.
- **`MODULARIZE=1` incompatibility**: With `MODULARIZE=1`, `--post-js` content (including `registerProcessor()`) is wrapped inside the factory function and never executes at top level. This causes `DOMException: AudioWorkletProcessor 'synth-processor' is not defined`. This test catches that failure.
- **Audio timing**: The default capture delay of 200 ms assumes an envelope with ~10 ms attack, ~100 ms decay, ~300 ms release. Adjust `--capture-delay` if the synth's envelope shape differs significantly.
- **Frequency resolution**: At `sampleRate=48000` and `fftSize=2048`, each FFT bin is ≈23.4 Hz wide. Frequency verification checks the peak bin and its two neighbours, so the tolerance is approximately ±1 bin (±23 Hz). For tight tuning verification use the `audio-fft-sanity` skill on a longer capture.

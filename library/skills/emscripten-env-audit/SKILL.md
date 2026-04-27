---
name: emscripten-env-audit
description: Static analysis of Emscripten build flags targeting AudioWorkletGlobalScope. Parses a Makefile or build script, extracts emcc flags, and cross-references against a known list of APIs unavailable in the worklet environment. Flags configuration patterns that will cause runtime failures in the browser.
allowed-tools: Bash
argument-hint: "<Makefile|build-script> [--var WASM_FLAGS] [--env audioworklet|worker|web|node]"
---

# Emscripten Environment Audit

Parse Emscripten build flags and flag configuration patterns that cause runtime failures in `AudioWorkletGlobalScope`. Designed to catch the class of errors that require a full browser session to surface otherwise — `self is not defined`, `fetch is not a function`, `registerProcessor` not called — before any code is written or rebuilt.

This skill encodes the compatibility research that took ~3–4 hours of iterative debugging in Sprint 5 of faust-poc1. A 30-minute research session reading the Emscripten GitHub issues and MDN AudioWorkletGlobalScope docs would have identified all five failure modes before the first `make synth-wasm`.

## Requirements

- Python 3.8+ (for the audit script)
- The Makefile or shell script containing the `emcc` invocation

## Instructions

Arguments are in `$ARGUMENTS`. Pass them directly to the audit script:

```bash
python3 "$(dirname "$0")/audit.py" $ARGUMENTS
```

## Checks performed

| Check | Severity | Pattern detected |
|-------|----------|-----------------|
| `MODULARIZE=1` | **ERROR** | Wraps `--post-js` content inside the factory function body. `registerProcessor()` never executes at top level. |
| `ENVIRONMENT=web` or `ENVIRONMENT=node` | **ERROR** | Wrong environment for a worklet target. Emscripten will emit DOM access code or Node.js-specific code. |
| No `--pre-js` with `self` polyfill | **WARN** | `ENVIRONMENT=worker` assumes `self` is defined. `AudioWorkletGlobalScope` does not expose it. |
| No `--pre-js` with `self.location` polyfill | **WARN** | Emscripten reads `self.location.href` for WASM path resolution. Absent in worklet scope. |
| No `instantiateWasm` hook pattern | **WARN** | Emscripten's default WASM loading calls `fetch()`. `fetch` is unavailable in `AudioWorkletGlobalScope`. |
| `ALLOW_MEMORY_GROWTH=1` without buffer re-read note | **INFO** | `HEAPF32.buffer` is invalidated on memory growth. Safe if `HEAPF32.buffer` is re-read on each `process()` call. |
| `EXPORT_NAME` without `MODULARIZE` | **INFO** | `EXPORT_NAME` is only meaningful with `MODULARIZE=1`. Has no effect without it. |
| Missing `--pre-js` or `--post-js` for worklet target | **WARN** | Both are typically needed: `--pre-js` for polyfills, `--post-js` to bundle the `AudioWorkletProcessor` class. |

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `--var NAME` | auto-detect | Makefile variable name holding the emcc flags (e.g. `WASM_FLAGS`). Auto-detected by scanning for `emcc` invocations if omitted. |
| `--env TYPE` | `audioworklet` | Target environment (`audioworklet`, `worker`, `web`, `node`). Determines which checks apply. Use `audioworklet` for Emscripten + AudioWorklet targets. |

## Exit codes

- `0` — no errors (warnings and infos do not fail)
- `1` — one or more ERROR-level findings

## Examples

```bash
# Audit a Makefile with default auto-detection
python3 audit.py Makefile

# Specify the variable name explicitly
python3 audit.py Makefile --var WASM_FLAGS

# Audit a shell build script
python3 audit.py build_wasm.sh
```

## Known limitations

- **Static analysis only**: The audit reads flag strings. It cannot evaluate Make variables that are computed dynamically (e.g. `$(shell ...)`), variables defined in included files, or flags set by environment variables at build time.
- **`--pre-js` content not inspected**: The audit detects the presence of `--pre-js` but does not parse its content to verify the polyfills are correct. After the audit, verify the `pre.js` file includes `self`, `self.location`, and a `Module.instantiateWasm` hook.
- **No cross-file analysis**: If `emcc` is invoked in a script that sources another file for flags, only the top-level file is inspected.

## AudioWorkletGlobalScope quick reference

APIs that differ from a standard Worker (the closest `ENVIRONMENT` option):

| API | Worker | AudioWorkletGlobalScope | Emscripten impact |
|-----|--------|------------------------|-------------------|
| `self` | Yes | **No** | Runtime crash; polyfill in `--pre-js` |
| `self.location.href` | Yes | **No** | Path resolution crash; polyfill in `--pre-js` |
| `fetch()` | Yes | **No** | WASM loading fails; use main-thread compile + `processorOptions` |
| `XMLHttpRequest` | Yes | **No** | WASM loading fallback fails; same fix as `fetch` |
| `setTimeout` / `setInterval` | Yes | **No** | Cannot use for timing in worklet |
| `registerProcessor()` | No | Yes | Must run at top-level scope; `MODULARIZE=1` prevents this |
| `WebAssembly.instantiate(module, imports)` | Yes | Yes | Works; requires pre-compiled module (no fetch for bytes) |
| `console.log` / `console.error` | Yes | Yes | Works normally |
| `performance.now()` | Yes | **No** | Emscripten may reference; not confirmed as a failure in testing |

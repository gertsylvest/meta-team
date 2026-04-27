---
name: wasm-module-inspect
description: Inspect a compiled .wasm binary — validates structure, lists exports and imports, detects SIMD and threading opcodes, and reports binary size. Requires wabt; wasm-opt (Binaryen) is optional.
allowed-tools: Bash
argument-hint: "<module.wasm>"
---

# WASM Module Inspect

Inspect a compiled `.wasm` binary to verify it is valid, understand its public API surface, and detect compilation features (SIMD, threads).

## Requirements

- **wabt** (`wasm-validate`, `wasm2wat`) — install via `brew install wabt` (macOS), `apt install wabt` (Linux), or from https://github.com/WebAssembly/wabt/releases
- **wasm-opt** (optional, Binaryen) — install via `brew install binaryen` for feature reporting

## Instructions

The argument is in `$ARGUMENTS`. Pass it directly to the inspection script:

```bash
bash "$(dirname "$0")/inspect.sh" $ARGUMENTS
```

## Output sections

| Section | What it reports |
|---|---|
| `SIZE` | Binary size in bytes and KB |
| `VALID` | Pass/fail from `wasm-validate` |
| `EXPORTS` | All exported functions, memories, tables, globals |
| `IMPORTS` | All imported functions (JS host functions the module depends on) |
| `SIMD` | Whether `v128` (WASM SIMD) opcodes are present |
| `THREADS` | Whether `atomic` instructions are present (requires `SharedArrayBuffer`) |
| `FEATURES` | Full feature list from `wasm-opt --print-features` (if available) |

## Typical usage

```bash
# After an Emscripten build — confirm exports match expected API
bash inspect.sh build/my-dsp.wasm

# Before deploying — confirm SIMD is present in the optimised build
bash inspect.sh dist/processor.wasm
```

## What to look for

- **Exports** should be minimal — only the functions the JS/worklet layer calls (e.g. `_init`, `_process`, `_destroy`). Unexpected exports indicate `-s EXPORTED_FUNCTIONS` was not set correctly.
- **SIMD present** confirms `-msimd128` was applied and the WASM binary actually contains vectorised code.
- **Threads present** means the page must be served with `COOP`/`COEP` headers — flag this if the deployment environment does not support them.
- **Large binary size** may indicate the Emscripten filesystem (`-s FILESYSTEM=0` not set) or C++ RTTI/exceptions were not disabled.

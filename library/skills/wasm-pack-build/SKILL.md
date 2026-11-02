---
name: wasm-pack-build
description: Opinionated wasm-pack wrapper that builds a Rust crate to wasm32-unknown-unknown with project-pinned flags (SIMD, LTO, panic=abort), applies a wasm-opt post-pass, and auto-invokes wasm-module-inspect on the result. Single entry point so the agent never reaches for raw wasm-pack and forgets a flag.
allowed-tools: Bash
argument-hint: "<crate-path> [--dev]"
---

# wasm-pack Build

The canonical Rust→WASM build path for browser audio. Builds with `wasm-pack` against `wasm32-unknown-unknown`, applies `wasm-opt` for size and performance, and runs `wasm-module-inspect` on the output to confirm exports are minimal, SIMD is present, and the module validates.

The flag set is fixed by this skill so every Rust WASM build in the project produces a binary with the same characteristics — no ad-hoc differences between developer machines or CI.

## Requirements

- **rustup** with stable toolchain and the `wasm32-unknown-unknown` target:
  ```bash
  rustup target add wasm32-unknown-unknown
  ```
- **wasm-pack** — install via `cargo install wasm-pack` or from https://rustwasm.github.io/wasm-pack/installer/.
- **wasm-opt** (Binaryen) — install via `brew install binaryen` (macOS), `apt install binaryen` / `dnf install binaryen` (Linux), or a prebuilt binary from https://github.com/WebAssembly/binaryen/releases. Distro packages can lag; if `--enable-simd` is rejected, use the release binary.
- The `wasm-module-inspect` skill from this library (the script invokes it for the final verification step).

## What it does

1. Verifies prerequisites (`wasm-pack`, `wasm-opt`, target installed).
2. Sets `RUSTFLAGS="-C target-feature=+simd128"` (appended to any `RUSTFLAGS` you already exported) so WASM SIMD is enabled. **Setting `RUSTFLAGS` makes cargo ignore all `rustflags` in `.cargo/config.toml`** (`build.rustflags`, `target.<triple>.rustflags`) — the env var wins outright, it does not merge. If the project keeps flags there, export them in `RUSTFLAGS` before calling the script.
3. Runs `wasm-pack build --target web --release` (or `--dev` if `--dev` is passed) on the crate.
4. Runs `wasm-opt -O3 --enable-simd <pkg>/<crate>_bg.wasm -o <same>` over the wasm-bindgen-emitted module. Note that **wasm-pack already runs wasm-opt itself on release builds** (default `-O`, configurable via `[package.metadata.wasm-pack.profile.release] wasm-opt = [...]` in `Cargo.toml`), so this is a **second pass**. It pins the final optimisation level and SIMD flag regardless of that metadata. If you prefer a single pass, set `wasm-opt = false` in the metadata and let this step do it.
5. Invokes `wasm-module-inspect` on the optimised `.wasm`.

Release builds also implicitly use the project's `[profile.release]` settings — the crate is expected to declare `panic = "abort"`, `lto = "fat"`, `codegen-units = 1`, `opt-level = 3` per the rust-audio-engineer agent's standards.

## Instructions

The arguments are in `$ARGUMENTS`. Pass them directly to the build script:

```bash
bash .claude/skills/wasm-pack-build/build.sh $ARGUMENTS
```

Argument 1 is the crate directory. Optional second argument `--dev` switches to a debug build with source maps for browser debugging.

## Output sections

| Section | What it reports |
|---|---|
| `PREREQ` | Whether wasm-pack, wasm-opt, and the wasm32 target are present |
| `BUILD` | wasm-pack invocation result |
| `OPTIMISE` | wasm-opt size reduction |
| `INSPECT` | Full output of `wasm-module-inspect` |

## Typical usage

```bash
# Release build
bash build.sh ./rust/audio-wasm

# Debug build with DWARF source maps for browser debugging
bash build.sh ./rust/audio-wasm --dev
```

## What to look for

- **`PREREQ` failing** — the script tells you exactly what to install.
- **`BUILD` failing** — usually a Rust compile error or a missing `[lib] crate-type = ["cdylib", "rlib"]` in the crate's `Cargo.toml`.
- **`INSPECT` showing unexpected exports** — review the `#[wasm_bindgen]` and `#[no_mangle] extern "C"` exports in the Rust source. The worklet should only see the minimal API surface (`init`, `process`, `destroy`, and any control-plane functions).
- **`INSPECT` showing no SIMD** despite a release build — `RUSTFLAGS` did not propagate. Check that the script ran in an environment where it can set env vars. (`.cargo/config.toml` rustflags cannot override it — they are ignored once `RUSTFLAGS` is set — but that also means flags the project relies on there are silently dropped.)
- **`OPTIMISE` showing little reduction** is expected: wasm-pack's own wasm-opt pass has already run.

## Why a wrapper instead of raw wasm-pack

The flag set matters: `+simd128`, `--target web`, the wasm-opt post-pass, and the inspect step are all easy to forget individually. A wrapper makes the build reproducible across the team and CI without each caller having to remember the recipe.

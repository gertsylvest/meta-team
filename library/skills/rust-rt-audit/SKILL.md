---
name: rust-rt-audit
description: Audit a Rust DSP crate for real-time-safety violations — verifies `#![no_std]`, no `alloc` dependency, `panic = "abort"`, runs targeted clippy lints, greps for banned constructs in the hot path, and scans the compiled LLVM-IR for allocator symbols. Designed to be run on any Rust DSP crate before merge.
allowed-tools: Bash
argument-hint: "<crate-path>"
---

# Rust Real-Time Audit

Verify that a Rust DSP crate respects the real-time-safety rules:

1. The crate is `#![no_std]` and does not depend on `alloc`.
2. The crate uses `panic = "abort"` so panics cannot unwind across an FFI or worklet boundary.
3. No clippy-detectable panic-prone constructs (`unwrap`, `expect`, slice indexing, integer overflow) are present.
4. No banned heap/blocking constructs (`Vec::`, `Box::`, `Mutex`, `format!`, `println!`, etc.) appear in the source.
5. The compiled LLVM-IR contains no calls to `__rust_alloc` / `__rust_realloc` / `__rust_dealloc`.

The first four are cheap and run in seconds. The fifth is the strongest check, but it is **not a proof**: it scans only the IR of this crate's library, built fresh into a temp file. Generic functions are not monomorphised there — they are instantiated in the *caller's* crate — so an allocation inside a generic (or an `#[inline]` function only expanded downstream) can be absent from this IR and still reach the hot path. For full coverage, also run the scan on the final consumer (the binary, cdylib or wasm module), e.g. by inspecting its symbols for `__rust_alloc`.

## Requirements

- **rustup** with a stable toolchain.
- **cargo** (bundled with rustup).
- The crate being audited must compile.

Optional but recommended:
- `clippy` component (`rustup component add clippy`) for the lint pass. The script skips clippy cleanly if it is missing.

## Instructions

The argument is in `$ARGUMENTS`. Pass it directly to the audit script:

```bash
bash .claude/skills/rust-rt-audit/audit.sh $ARGUMENTS
```

The argument is the path to the crate directory (the one containing `Cargo.toml`).

## Output sections

| Section | What it reports |
|---|---|
| `NO_STD` | Whether `#![no_std]` is declared in `src/lib.rs` |
| `NO_ALLOC_DEP` | Whether the crate has any dependency on `alloc` (direct or via Cargo.toml) |
| `PANIC_ABORT` | Whether `panic = "abort"` is set in the release profile |
| `CLIPPY` | Lint results from a curated set of panic/allocation-detecting lints |
| `HOT_PATH_GREP` | Grep hits for banned constructs in `src/**.rs` |
| `LLVM_IR_ALLOC` | Whether `__rust_alloc*` symbols appear in this crate's freshly emitted release LLVM-IR (generics excluded — see above) |

## Typical usage

```bash
# Audit a single DSP crate
bash audit.sh ./rust/audio-dsp

# Audit every DSP crate in a workspace
for crate in rust/dsp-*; do bash audit.sh "$crate"; done
```

## What to look for

- **`NO_STD` failing** is a structural problem — the crate should be split so DSP code lives in a `no_std` crate and any `std`-dependent code moves to a sibling crate.
- **`NO_ALLOC_DEP` failing** means a transitive dependency pulled in `alloc`. Use `cargo tree -e features` to find the culprit and either gate it behind a feature flag or replace it.
- **`PANIC_ABORT` failing** is a one-line `Cargo.toml` fix.
- **`CLIPPY` or `HOT_PATH_GREP` hits** require code changes — see the agent profile's Real-Time-Safe Rust section for the rationale and the safe replacements.
- **Hits from test code** — `HOT_PATH_GREP` scans every file under `src/` textually, and clippy lints the lib target, so `Vec::`, `println!` or `unwrap()` inside `#[cfg(test)] mod tests` blocks will be reported. Move tests to `tests/` (integration tests, not scanned), or treat hits inside test modules as false positives.
- **`CLIPPY` hit count** counts individual diagnostics; cargo's "generated N warnings" summary line is excluded.
- **`LLVM_IR_ALLOC` failing despite a clean source grep** usually means a third-party crate is allocating. `cargo tree` + the IR's call site (look at the function name preceding `call __rust_alloc`) identify the source.

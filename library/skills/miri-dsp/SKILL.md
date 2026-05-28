---
name: miri-dsp
description: Run `cargo +nightly miri test` against a Rust DSP crate to detect undefined behaviour the compiler missed — out-of-bounds access, use-after-free, uninitialised memory reads, invalid pointer arithmetic. Miri is the cheapest sound UB detector for Rust; this skill wraps it with the right isolation flags for audio DSP crates.
allowed-tools: Bash
argument-hint: "<crate-path>"
---

# Miri DSP

`miri` interprets Rust's mid-level IR and catches a large class of undefined behaviour that `cargo test` will silently miss: out-of-bounds slice access, use-after-free, reads of uninitialised memory, invalid `unsafe` pointer arithmetic, and aliasing violations under the Stacked Borrows / Tree Borrows models.

Miri is most valuable on `no_std` DSP crates — they tend to contain hand-written `unsafe` for SIMD and ringbuffers where the compiler cannot prove safety. The cost is runtime speed (Miri is an interpreter, not a compiler), so this skill targets the unit tests of a single crate rather than a whole workspace.

## Limitations

- **Miri does not target `wasm32`.** It runs on the host triple. UB-free under Miri does not guarantee UB-free under wasm32 — but in practice the UB classes Miri catches are target-independent.
- **Floating-point intrinsics are slow under Miri.** Heavy DSP benchmark suites will time out. Focus tests on correctness invariants and `unsafe` boundaries, not on full audio renders.
- **`cargo bench` does not run under Miri** — use the `cargo-bench-rt` skill on native instead.

## Requirements

- **Rust nightly toolchain** with the miri component:
  ```bash
  rustup toolchain install nightly
  rustup +nightly component add miri
  ```

The script bootstraps both if missing.

## Instructions

The argument is in `$ARGUMENTS`. Pass it directly to the run script:

```bash
bash "$(dirname "$0")/run.sh" $ARGUMENTS
```

The argument is the path to the crate directory.

## Output sections

| Section | What it reports |
|---|---|
| `TOOLCHAIN` | Whether nightly + miri are installed |
| `MIRI` | Result of `cargo +nightly miri test` |

## Typical usage

```bash
# Run miri on a single DSP crate
bash run.sh ./rust/audio-dsp

# Run on every DSP crate in a workspace
for crate in rust/dsp-*; do bash run.sh "$crate"; done
```

## What to look for

- **`MIRI` failing with "Undefined Behavior"** — read the report carefully. Miri pinpoints the exact statement and explains the violation (e.g. "reading uninitialised bytes", "out-of-bounds pointer offset", "stacked borrows violation").
- **`MIRI` timing out** — narrow the test set. Mark long-running renders with `#[cfg(not(miri))]` so they are skipped under Miri while still running under `cargo test`.
- **`MIRI` reporting "unsupported operation"** — Miri does not support every libc or syscall. If the offending call is in a third-party dep, gate that path behind a feature flag the DSP crate does not enable; if it is in your own code, the operation probably should not be in a DSP crate at all.

## How often to run

Run on every change to an `unsafe` block in a DSP crate. Optional but valuable in CI on a nightly schedule.

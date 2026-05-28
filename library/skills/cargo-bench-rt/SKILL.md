---
name: cargo-bench-rt
description: Run a Criterion benchmark on a Rust DSP crate and assert against a checked-in baseline. Establishes whether the implementation fits the real-time budget and catches performance regressions — the Rust equivalent of `perf stat` against the audio buffer time.
allowed-tools: Bash
argument-hint: "<crate-path> <bench-name> [--save-baseline | --budget-pct N]"
---

# Cargo Bench RT

Audio DSP correctness is not enough — the implementation must also fit within the real-time buffer budget. At 48 kHz with a 128-sample block (the AudioWorklet quantum), a `process()` call has roughly 2.67 ms to complete; on a typical native build with 256-sample blocks at 48 kHz the budget is ~5.33 ms.

This skill wraps Criterion in two modes:
1. **First run / baseline mode** — establishes a baseline measurement of a named bench and commits it.
2. **Regression mode** — compares the current measurement against the committed baseline and fails if the regression exceeds a configurable percentage.

The intent mirrors the c-audio-engineer's "profile the callback against the real-time budget" rule, applied to Rust DSP crates.

## Requirements

- A `[[bench]]` entry in the crate's `Cargo.toml` for the named benchmark.
- The `criterion` crate as a `dev-dependency`.
- A bench source file at `benches/<bench-name>.rs` using the Criterion harness.

Typical Criterion bench skeleton:

```rust
use criterion::{black_box, criterion_group, criterion_main, Criterion};

fn bench_process(c: &mut Criterion) {
    let mut state = my_dsp::Processor::new(48_000.0);
    let mut buf = [0.0_f32; 128];
    c.bench_function("process_128", |b| {
        b.iter(|| state.process(black_box(&mut buf)));
    });
}

criterion_group!(benches, bench_process);
criterion_main!(benches);
```

## Instructions

The arguments are in `$ARGUMENTS`. Pass them directly to the bench script:

```bash
bash "$(dirname "$0")/bench.sh" $ARGUMENTS
```

- Argument 1: crate directory.
- Argument 2: bench name (matches the `[[bench]] name = "..."` in Cargo.toml).
- Optional `--save-baseline`: overwrite the baseline with the current measurement. Use after a deliberate performance change.
- Optional `--budget-pct N` (default `5`): regression budget in percent. The bench fails if the new measurement is more than N% slower than the baseline.

## Output sections

| Section | What it reports |
|---|---|
| `BENCH` | Criterion run summary (mean, std dev, throughput) |
| `BUDGET` | Pass/fail vs the baseline, with the actual delta |

## Typical usage

```bash
# Establish a baseline after a deliberate optimisation
bash bench.sh ./rust/audio-dsp process_128 --save-baseline

# Regression check on every CI run (default budget: 5%)
bash bench.sh ./rust/audio-dsp process_128

# Tighter budget for hot-path benches
bash bench.sh ./rust/audio-dsp process_128 --budget-pct 2
```

## What to look for

- **`BENCH` mean exceeding the real-time budget** — the implementation cannot keep up with real time even on the development machine. Profile (Instruments / `perf`), find the hot function, optimise. Do not commit a baseline that is already over budget.
- **`BUDGET` failing** — the change made the bench slower than tolerable. Inspect the diff for the cause: extra branching, unintentional bounds checks, a `#[inline]` removed, SIMD path disabled.
- **High standard deviation** — the measurement is noisy. Run with the machine under low load, close browsers and heavy processes, or use `taskset`/`nice` to pin the bench to a quiet CPU.

## Where the baseline lives

Criterion stores baselines under `target/criterion/<bench-name>/<baseline>/`. This skill uses baseline name `rt-baseline` and expects projects to commit it under `benches/baselines/<bench-name>/` — see the script for the exact mapping.

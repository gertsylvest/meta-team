---
name: cbindgen-verify
description: Regenerate a C header from a Rust crate via cbindgen and diff it against the committed header. Fails if the generated output differs — catches "Rust signature changed but the C header was not regenerated" before it reaches the C side.
allowed-tools: Bash
argument-hint: "<crate-path> <committed-header-path>"
---

# cbindgen Verify

When a Rust crate exposes a C ABI for use by a C/C++ host (the audio driver, a JUCE plugin shell, an Emscripten-built worklet host), the C header is generated from the Rust source by `cbindgen` and committed to the repo so C consumers do not need Cargo installed.

This skill regenerates the header from the current Rust source and diffs it against the committed file. Any drift means the Rust ABI has been changed without updating the header — a class of bug that otherwise surfaces only when the C side fails to link or, worse, links against a stale header and produces UB at runtime.

## Requirements

- **cbindgen** — install via `cargo install --force cbindgen`.
- A `cbindgen.toml` config file in the crate directory (cbindgen's standard convention).
- The committed C header to compare against.

## Instructions

The arguments are in `$ARGUMENTS`. Pass them directly to the verify script:

```bash
bash "$(dirname "$0")/verify.sh" $ARGUMENTS
```

Argument 1 is the crate directory (containing `Cargo.toml` and `cbindgen.toml`). Argument 2 is the path to the committed header.

## Output sections

| Section | What it reports |
|---|---|
| `CBINDGEN` | Whether cbindgen ran successfully |
| `DIFF` | Unified diff between regenerated and committed headers, or PASS if identical |

## Typical usage

```bash
# Verify a single crate's header
bash verify.sh ./rust/audio-dsp ./include/audio_dsp.h

# As a pre-commit hook
bash verify.sh ./rust/audio-dsp ./include/audio_dsp.h || {
  echo "C header out of date — regenerate with: cbindgen --config rust/audio-dsp/cbindgen.toml --crate audio-dsp --output include/audio_dsp.h"
  exit 1
}
```

## What to look for

- **DIFF showing added/removed functions** — the Rust public ABI changed; either the change is intentional (regenerate and commit the new header, notify the c-audio-engineer) or accidental (revert the Rust change).
- **DIFF showing changed signatures** — a parameter type, return type, or struct field changed. This is a breaking change for the C side regardless of whether the new layout is binary-compatible. Coordinate with the c-audio-engineer before regenerating.
- **DIFF showing only comment or whitespace changes** — usually a cbindgen version mismatch between the developer who committed the header and the CI environment. Pin cbindgen's version in the project (e.g. `cargo install --version X.Y.Z cbindgen`) to eliminate the drift.

## When to skip

Do not skip. The cost of running it is sub-second; the cost of a stale header is silent UB.

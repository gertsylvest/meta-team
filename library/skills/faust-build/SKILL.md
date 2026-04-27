---
name: faust-build
description: Compile a Faust DSP source file to C, verify the API surface (function names, I/O counts, struct name), and optionally compile the result with clang. Runs a parameter smoothing audit before compilation. Use after any change to a .dsp file.
allowed-tools: Bash
argument-hint: "<input.dsp> <output.c> [--cn ClassName] [-I path ...] [--faust BIN] [--faust-arch DIR] [--ftz N] [--clang] [--inputs N] [--outputs N]"
---

# Faust Build

Compile a Faust DSP source file to C and verify the result is structurally correct. Combines three steps that were performed manually on every DSP change: parameter audit, compilation, and API surface verification. Optionally adds a clang compile step to catch type errors early.

## Requirements

- **Faust compiler** on `PATH` (or specify binary with `--faust`). Tested against Faust 2.85.x.
  - Known issue: `-ftz 2` generates broken C in Faust 2.85.5. This script defaults to `-ftz 0` (see `--ftz` option).
- **clang** (optional, only needed for `--clang` step)
- **Faust architecture headers** (optional, only needed for `--clang`): the directory containing `faust/gui/CInterface.h`. Pass via `--faust-arch`.

## Instructions

Arguments are in `$ARGUMENTS`. Pass them directly to the build script:

```bash
bash "$(dirname "$0")/build.sh" $ARGUMENTS
```

## Steps performed

| Step | What it does |
|------|--------------|
| **0 — Param audit** | Scans the `.dsp` source for `hslider`/`vslider`/`nentry` parameters not followed by `si.smoo` or `si.smooth` on the same line. Flags as warnings (heuristic; does not catch multi-line smoothing). |
| **1 — Faust compile** | Runs `faust -lang c -cn <ClassName> -single -ftz <N> <include paths> -o <output.c> <input.dsp>`. Aborts on compiler failure. |
| **2 — API surface check** | Greps the generated C for all 14 expected public function names (suffix = class name). Checks that `FAUSTCLASS` macro matches. Optionally verifies `getNumInputs` and `getNumOutputs` return values. |
| **3 — Clang compile** (optional) | Runs `clang -std=c11 -O2 -Wall -Wextra -include faust/gui/CInterface.h -Wno-unused-parameter -c <output.c>`. The force-include is required because Faust-generated C references `UIGlue`, `MetaGlue`, and `Soundfile` without including their definitions. |

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `--cn NAME` | `mydsp` | Faust class name (`-cn` flag). All generated function names are suffixed with this. |
| `-I PATH` | — | Include path for Faust library resolution (repeatable). Typically needs `dsp/modules` and the `faustlibraries` path. |
| `--faust BIN` | `faust` | Faust compiler binary path. |
| `--faust-arch DIR` | — | Directory containing `faust/gui/CInterface.h`. Required for `--clang`. |
| `--ftz N` | `0` | Faust denormal flushing mode. Use `0` for Faust 2.85.x (the default); `-ftz 2` is broken in that version. |
| `--clang` | off | Run `clang -c -Wall` on the generated C as a final verification step. |
| `--inputs N` | — | Expected `getNumInputs` return value. Fails if the generated code disagrees. |
| `--outputs N` | — | Expected `getNumOutputs` return value. Fails if the generated code disagrees. |

## Exit codes

- `0` — all checks passed (warnings do not fail the build)
- `1` — Faust compilation failed, or one or more API surface checks failed, or clang failed

## Examples

```bash
# Minimal: compile and verify API surface
bash build.sh src/dsp/synth.dsp src/generated/synth.c --cn Synth

# With library paths and expected I/O counts
bash build.sh src/dsp/synth.dsp src/generated/synth.c \
  --cn Synth \
  -I dsp/modules \
  -I ~/faust/faustlibraries \
  --inputs 0 --outputs 1

# Full verification including clang
bash build.sh src/dsp/synth.dsp src/generated/synth.c \
  --cn Synth \
  -I dsp/modules \
  -I ~/faust/faustlibraries \
  --faust-arch ~/faust/architecture \
  --clang \
  --inputs 0 --outputs 1
```

## Notes

- `-ftz 0` means no Faust-level denormal flushing. Move denormal protection to the driver layer (FTZ/DAZ CPU flags on the audio thread). This is better separation of concerns anyway.
- The param audit checks only within single lines. A parameter smoothed on the next line (e.g. `freq = hslider(...)\n  : si.smoo`) will be flagged as a warning even though it is correctly smoothed. Treat warnings as review prompts, not definitive failures.
- The public API for `-cn Synth` is: `newSynth`, `deleteSynth`, `metadataSynth`, `getSampleRateSynth`, `getNumInputsSynth`, `getNumOutputsSynth`, `classInitSynth`, `instanceResetUserInterfaceSynth`, `instanceClearSynth`, `instanceConstantsSynth`, `instanceInitSynth`, `initSynth`, `buildUserInterfaceSynth`, `computeSynth`. All 14 must be present for a valid build.

---
name: faust-header-gen
description: Generate a matching extern "C" header from a Faust-generated C file. Extracts public function signatures, applies the opaque-typedef pattern, and emits a correctly guarded header. Eliminates the manual header maintenance step and prevents header/implementation drift.
allowed-tools: Bash
argument-hint: "<synth.c> [-o output.h] [--guard GUARD_NAME] [--exports exports.exp]"
---

# Faust Header Gen

Read a Faust-generated C file and produce a matching `extern "C"` header. Eliminates the manual step of writing and maintaining a `synth.h`, which was historically a source of errors whenever the Faust class name (`-cn`) changed or new functions were added.

## Requirements

- Python 3.8+

## Instructions

Arguments are in `$ARGUMENTS`. Pass them directly to the generator:

```bash
python3 "$(dirname "$0")/gen_header.py" $ARGUMENTS
```

## What the generated header contains

| Element | Detail |
|---------|--------|
| Include guard | `#ifndef CLASSNAME_H` / `#define CLASSNAME_H` (or custom via `--guard`) |
| `FAUSTFLOAT` default | `#ifndef FAUSTFLOAT` / `#define FAUSTFLOAT float` guard so the header can be included without the generated C |
| Dependency note | Comment stating `faust/gui/CInterface.h` must be included before this header (it defines `UIGlue`, `MetaGlue`, `FAUSTFLOAT`) |
| `extern "C"` wrapping | Guarded by `#ifdef __cplusplus` so the header works for both C and C++ consumers |
| Opaque forward declaration | `typedef struct ClassName ClassName;` — declares a named struct tag even though the generated C uses an anonymous struct typedef. This is the correct pattern for C++ consumers who hold only opaque pointers. |
| Public function prototypes | All non-`static` functions whose names end with the class name, grouped into: Lifecycle, Metadata, Query, Initialisation, User Interface, DSP |
| `RESTRICT` stripped | The generated C uses `RESTRICT` on parameter declarations. Headers omit it — `restrict` is an optimisation hint, not a type qualifier that affects linkage. |
| `void` on zero-arg functions | `newSynth()` in the generated C becomes `newSynth(void)` in the header — correct C for "no arguments". |

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `-o FILE` | stdout | Write header to file instead of stdout |
| `--guard NAME` | `CLASSNAME_H` | Override the include guard name |
| `--exports FILE` | — | Also write a linker exports file (one `_symbol` per line, for `.exp` dylib builds) |

## Exit codes

- `0` — header generated successfully
- `1` — input file not found, class name could not be detected, or no public functions found

## Examples

```bash
# Write to stdout (inspect before committing)
python3 gen_header.py src/generated/synth.c

# Write to file
python3 gen_header.py src/generated/synth.c -o src/generated/synth.h

# Also generate a linker exports file
python3 gen_header.py src/generated/synth.c \
  -o src/generated/synth.h \
  --exports src/generated/synth_exports.exp
```

## Notes

- **When to run**: after every `faust-build` that changes the class name (`--cn`) or adds/removes DSP outputs. If only internal DSP logic changes (filter coefficients, signal routing), the public API surface does not change and the header does not need regenerating.
- **Anonymous struct quirk**: The generated C uses `typedef struct { ... } Synth;` (anonymous struct). C++ forward declarations require `typedef struct Synth Synth;` (named struct tag). These are compatible at link time because consumers only hold `Synth*` pointers — they never dereference struct members through the header. This is the only divergence between the header and the generated C.
- **`MetaGlue*` and `UIGlue*` in prototypes**: The header uses these types in function signatures but does not include their definitions. Include `faust/gui/CInterface.h` before this header. This is intentional — it avoids pulling Faust headers into the project's own include tree.

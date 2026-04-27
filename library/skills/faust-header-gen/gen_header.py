#!/usr/bin/env python3
"""
faust-header-gen: Generate a matching extern "C" header from a Faust-generated C file.

Extracts the class name, finds all non-static public functions, strips
RESTRICT qualifiers, and emits a well-formed header with the opaque
typedef pattern required for C++ consumers.
"""

import re
import sys
import argparse
from pathlib import Path


# ── Parsing ───────────────────────────────────────────────────────────────────

def strip_comments(source: str) -> str:
    """Remove C-style block comments and line comments."""
    source = re.sub(r'/\*.*?\*/', '', source, flags=re.DOTALL)
    source = re.sub(r'//[^\n]*', '', source)
    return source


def extract_class_name(source: str) -> str:
    """
    Extract the class name from #define FAUSTCLASS ClassName.
    Falls back to scanning the anonymous struct typedef if the macro is absent.
    """
    m = re.search(r'#\s*define\s+FAUSTCLASS\s+(\w+)', source)
    if m:
        return m.group(1)
    # Fallback: typedef struct { ... } ClassName; (may match internal structs — use with care)
    m = re.search(r'typedef\s+struct\s*\{[^}]*\}\s*(\w+)\s*;', source, re.DOTALL)
    if m:
        return m.group(1)
    raise ValueError(
        "Could not find FAUSTCLASS macro or struct typedef in the generated C. "
        "Ensure the file was generated with `faust -lang c`."
    )


def extract_public_functions(source_raw: str, class_name: str) -> list:
    """
    Return list of (return_type, fn_name, params) for all non-static
    function declarations/definitions whose name ends with class_name.
    """
    source = strip_comments(source_raw)
    suffix = re.escape(class_name)

    # Match: optional-whitespace <return-type> <fnName ending in ClassName> ( <params> )
    # Negative lookahead for 'static' at the start of the logical line.
    pattern = re.compile(
        r'(?m)'                              # multiline
        r'^(?![ \t]*static\b)'              # not a static function
        r'(?![ \t]*typedef\b)'              # not a typedef
        r'(?![ \t]*#)'                      # not a preprocessor line
        r'[ \t]*([\w][\w\s\*]*?)\s+'        # return type (group 1)
        r'(\w+' + suffix + r')'             # function name (group 2)
        r'\s*\(([^)]*)\)'                   # parameter list (group 3)
    )

    seen = set()
    results = []

    for m in pattern.finditer(source):
        ret_type = m.group(1).strip()
        fn_name  = m.group(2).strip()
        params   = m.group(3).strip()

        # Skip duplicates (definition + forward decl in same file)
        if fn_name in seen:
            continue
        seen.add(fn_name)

        # Skip anything that looks like a macro or type alias artifact
        if ret_type.startswith('#') or not ret_type:
            continue

        params = _normalize_params(params, fn_name)
        results.append((ret_type, fn_name, params))

    return results


def _normalize_params(params: str, fn_name: str) -> str:
    """Strip RESTRICT, clean whitespace, use (void) for zero-argument functions."""
    if not params.strip():
        return 'void'
    params = re.sub(r'\bRESTRICT\b\s*', '', params)
    params = re.sub(r'\s+', ' ', params).strip()
    return params if params else 'void'


# ── Header emission ───────────────────────────────────────────────────────────

CATEGORY_ORDER = ['lifecycle', 'metadata', 'query', 'init', 'ui', 'compute', 'other']

CATEGORY_COMMENTS = {
    'lifecycle': '/* Lifecycle */',
    'metadata':  '/* Metadata */',
    'query':     '/* Query */',
    'init':      '/* Initialisation */',
    'ui':        '/* User interface */',
    'compute':   '/* DSP */',
    'other':     '/* Other */',
}


def _categorize(fn_name: str, class_name: str) -> str:
    base = fn_name[: len(fn_name) - len(class_name)]
    categories = {
        'new':                          'lifecycle',
        'delete':                       'lifecycle',
        'metadata':                     'metadata',
        'getSampleRate':                'query',
        'getNumInputs':                 'query',
        'getNumOutputs':                'query',
        'classInit':                    'init',
        'instanceResetUserInterface':   'init',
        'instanceClear':                'init',
        'instanceConstants':            'init',
        'instanceInit':                 'init',
        'init':                         'init',
        'buildUserInterface':           'ui',
        'compute':                      'compute',
    }
    return categories.get(base, 'other')


def generate_header(class_name: str, functions: list, guard: str) -> str:
    guard = guard or f'{class_name.upper()}_H'
    lines = []

    lines += [
        f'#ifndef {guard}',
        f'#define {guard}',
        '',
        '#ifndef FAUSTFLOAT',
        '#define FAUSTFLOAT float',
        '#endif',
        '',
        '/* Requires: faust/gui/CInterface.h must be included before this header.',
        ' * It defines UIGlue, MetaGlue, and FAUSTFLOAT. */',
        '',
        '#ifdef __cplusplus',
        'extern "C" {',
        '#endif',
        '',
        f'/* Opaque DSP instance type.',
        f' * Uses a named struct tag even though the generated C uses an anonymous typedef.',
        f' * Compatible at link time: consumers hold only {class_name}* pointers. */',
        f'typedef struct {class_name} {class_name};',
        '',
    ]

    # Group functions by category
    by_cat: dict = {c: [] for c in CATEGORY_ORDER}
    for ret_type, fn_name, params in functions:
        cat = _categorize(fn_name, class_name)
        by_cat[cat].append((ret_type, fn_name, params))

    for cat in CATEGORY_ORDER:
        fns = by_cat[cat]
        if not fns:
            continue
        lines.append(CATEGORY_COMMENTS[cat])
        for ret_type, fn_name, params in fns:
            lines.append(f'{ret_type} {fn_name}({params});')
        lines.append('')

    lines += [
        '#ifdef __cplusplus',
        '}',
        '#endif',
        '',
        f'#endif /* {guard} */',
    ]

    return '\n'.join(lines) + '\n'


def generate_exports(functions: list) -> str:
    """One _symbol per line, suitable for an .exp linker exports file."""
    return '\n'.join(f'_{fn_name}' for _, fn_name, _ in functions) + '\n'


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Generate an extern "C" header from a Faust-generated C file.'
    )
    parser.add_argument('input', help='Faust-generated .c file')
    parser.add_argument('-o', '--output', help='Output header path (default: stdout)')
    parser.add_argument('--guard', help='Include guard name (default: CLASSNAME_H)')
    parser.add_argument('--exports', help='Write a linker .exp exports file to this path')
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f'ERROR: File not found: {input_path}', file=sys.stderr)
        sys.exit(1)

    source = input_path.read_text()

    try:
        class_name = extract_class_name(source)
    except ValueError as e:
        print(f'ERROR: {e}', file=sys.stderr)
        sys.exit(1)

    print(f'Class name: {class_name}', file=sys.stderr)

    functions = extract_public_functions(source, class_name)

    if not functions:
        print(
            f'ERROR: No public functions found with suffix "{class_name}". '
            f'Check that the file was generated with -cn {class_name}.',
            file=sys.stderr
        )
        sys.exit(1)

    print(f'Found {len(functions)} public functions:', file=sys.stderr)
    for _, fn_name, _ in functions:
        print(f'  {fn_name}', file=sys.stderr)

    header = generate_header(class_name, functions, args.guard)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(header)
        print(f'Wrote: {out_path}', file=sys.stderr)
    else:
        print(header)

    if args.exports:
        exp_path = Path(args.exports)
        exp_path.parent.mkdir(parents=True, exist_ok=True)
        exp_path.write_text(generate_exports(functions))
        print(f'Wrote exports: {exp_path}', file=sys.stderr)


if __name__ == '__main__':
    main()

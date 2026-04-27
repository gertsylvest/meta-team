#!/usr/bin/env python3
"""
emscripten-env-audit: Static analysis of Emscripten build flags for AudioWorklet targets.

Parses a Makefile or shell script, extracts emcc flags, and cross-references
against known incompatibilities with AudioWorkletGlobalScope.
"""

import re
import sys
import argparse
from pathlib import Path
from dataclasses import dataclass, field
from typing import Literal

Severity = Literal['ERROR', 'WARN', 'INFO']


@dataclass
class Finding:
    severity: Severity
    code: str
    message: str
    detail: str = ''


# ── Flag extraction ───────────────────────────────────────────────────────────

def extract_flags_from_text(text: str, var_name: str | None) -> tuple[list[str], str]:
    """
    Return (flag_list, source_description).

    If var_name is given, extract the value of that Makefile variable.
    Otherwise, find the emcc invocation line(s) and collect all -s... flags.
    """
    # Normalise line continuations
    text = re.sub(r'\\\n\s*', ' ', text)

    if var_name:
        # Match: VAR_NAME := value  or  VAR_NAME = value (possibly multi-token)
        pattern = re.compile(
            r'^\s*' + re.escape(var_name) + r'\s*[:+?]?=\s*(.+)$',
            re.MULTILINE
        )
        m = pattern.search(text)
        if not m:
            return [], f'variable {var_name} not found'
        raw = m.group(1).strip()
        return _tokenize_flags(raw), f'variable {var_name}'

    # Auto-detect: find lines containing 'emcc' and extract flags
    emcc_lines = [line.strip() for line in text.splitlines() if re.search(r'\bemcc\b', line)]
    if not emcc_lines:
        return [], 'no emcc invocation found'

    flags = []
    for line in emcc_lines:
        flags.extend(_tokenize_flags(line))
    return flags, f'{len(emcc_lines)} emcc invocation(s)'


def _tokenize_flags(raw: str) -> list[str]:
    """Split a flag string into individual tokens, handling quotes and continuations."""
    # Remove make variable references $(...)
    raw = re.sub(r'\$\([^)]*\)', '', raw)
    # Split on whitespace
    tokens = raw.split()
    return [t for t in tokens if t and not t.startswith('$')]


# ── Flag parsing helpers ──────────────────────────────────────────────────────

def get_sflags(flags: list[str]) -> dict[str, str]:
    """Extract all -sKEY=VALUE flags into a dict. Handles -s KEY=VALUE and -sKEY=VALUE."""
    result = {}
    i = 0
    while i < len(flags):
        f = flags[i]
        if f == '-s' and i + 1 < len(flags):
            kv = flags[i + 1]
            if '=' in kv:
                k, v = kv.split('=', 1)
            else:
                k, v = kv, '1'
            result[k.strip()] = v.strip().strip("'\"")
            i += 2
            continue
        m = re.match(r'-s([A-Z_]+)(?:=(.*))?$', f)
        if m:
            k = m.group(1)
            v = m.group(2) if m.group(2) is not None else '1'
            result[k] = v.strip().strip("'\"")
        i += 1
    return result


def get_flag_values(flags: list[str], flag: str) -> list[str]:
    """Return all values for a given flag (e.g. all --pre-js paths)."""
    values = []
    for i, f in enumerate(flags):
        if f == flag and i + 1 < len(flags):
            values.append(flags[i + 1])
        elif f.startswith(flag + '='):
            values.append(f.split('=', 1)[1])
        elif f.startswith(flag) and len(f) > len(flag):
            values.append(f[len(flag):])
    return values


# ── Checks ────────────────────────────────────────────────────────────────────

def check_flags(flags: list[str], sflags: dict, target_env: str) -> list[Finding]:
    findings = []

    # ── ERROR: MODULARIZE=1 ──────────────────────────────────────────────────
    if sflags.get('MODULARIZE') in ('1', 'true', 'TRUE'):
        findings.append(Finding(
            severity='ERROR',
            code='MODULARIZE_INCOMPATIBLE',
            message='MODULARIZE=1 is incompatible with AudioWorklet targets.',
            detail=(
                'With MODULARIZE=1, Emscripten wraps the entire output — including --post-js content — '
                'inside the factory function. registerProcessor() must execute at the top level of '
                'AudioWorkletGlobalScope; inside a factory function it never runs. '
                'Fix: remove MODULARIZE=1 and EXPORT_NAME. Define Module in --pre-js instead.'
            )
        ))

    # ── ERROR: Wrong ENVIRONMENT ─────────────────────────────────────────────
    env = sflags.get('ENVIRONMENT', '')
    if target_env == 'audioworklet':
        if env in ('web', 'node'):
            findings.append(Finding(
                severity='ERROR',
                code='WRONG_ENVIRONMENT',
                message=f'ENVIRONMENT={env} is wrong for an AudioWorklet target.',
                detail=(
                    'Use ENVIRONMENT=worker (the closest available option). '
                    '"web" emits DOM-access code; "node" emits Node.js-specific code. '
                    'Note: "worker" still assumes self, self.location, and fetch() — '
                    'see WARN findings below for the required polyfills.'
                )
            ))
        elif not env or env == 'worker':
            # This is correct/expected — note the residual gap
            pass

    # ── WARN: ENVIRONMENT=worker without --pre-js (self polyfill) ────────────
    pre_js_files = get_flag_values(flags, '--pre-js')
    if target_env == 'audioworklet' and (not env or env == 'worker'):
        if not pre_js_files:
            findings.append(Finding(
                severity='WARN',
                code='MISSING_PRE_JS',
                message='No --pre-js found. ENVIRONMENT=worker code references self and self.location.href.',
                detail=(
                    'AudioWorkletGlobalScope does not expose self (WorkerGlobalScope) or self.location. '
                    'Add --pre-js with polyfills:\n'
                    '  var self = typeof self !== "undefined" ? self : globalThis;\n'
                    '  if (typeof self.location === "undefined") { self.location = { href: "" }; }'
                )
            ))
        else:
            findings.append(Finding(
                severity='INFO',
                code='PRE_JS_PRESENT',
                message=f'--pre-js found: {", ".join(pre_js_files)}. Verify it contains self and self.location polyfills.',
                detail='The audit does not inspect --pre-js content. Check manually that the file polyfills self, self.location, and Module.instantiateWasm.'
            ))

    # ── WARN: No instantiateWasm hook (fetch unavailable) ────────────────────
    # Heuristic: look for 'instantiateWasm' in pre-js references or in the build script text
    if target_env == 'audioworklet' and not pre_js_files:
        findings.append(Finding(
            severity='WARN',
            code='NO_INSTANTIATE_WASM_HOOK',
            message='No --pre-js detected. Emscripten will attempt to fetch() the .wasm file.',
            detail=(
                'fetch() is not available in AudioWorkletGlobalScope. Without a Module.instantiateWasm hook '
                'that receives a pre-compiled WebAssembly.Module from the main thread via processorOptions, '
                'WASM loading will fail with "fetch is not a function". '
                'Fix: main thread compiles WASM, passes WebAssembly.Module via AudioWorkletNode processorOptions, '
                '--pre-js defines Module.instantiateWasm to intercept Emscripten loading.'
            )
        ))

    # ── WARN: No --post-js ────────────────────────────────────────────────────
    post_js_files = get_flag_values(flags, '--post-js')
    if target_env == 'audioworklet' and not post_js_files:
        findings.append(Finding(
            severity='WARN',
            code='MISSING_POST_JS',
            message='No --post-js found.',
            detail=(
                'For AudioWorklet targets, the AudioWorkletProcessor class and registerProcessor() call '
                'are typically bundled into the Emscripten output via --post-js. '
                'Without this, the worklet file is purely Emscripten glue with no processor registration.'
            )
        ))

    # ── INFO: ALLOW_MEMORY_GROWTH ─────────────────────────────────────────────
    if sflags.get('ALLOW_MEMORY_GROWTH') in ('1', 'true'):
        findings.append(Finding(
            severity='INFO',
            code='MEMORY_GROWTH_HEAPF32',
            message='ALLOW_MEMORY_GROWTH=1: HEAPF32.buffer is invalidated on growth.',
            detail=(
                'If the Emscripten heap grows during a process() call, HEAPF32.buffer changes. '
                'Re-read HEAPF32.buffer at the start of each AudioWorkletProcessor.process() call '
                '(const f32 = new Float32Array(Module.HEAPF32.buffer, ptr, count)) rather than caching it.'
            )
        ))

    # ── INFO: EXPORT_NAME without MODULARIZE ─────────────────────────────────
    if 'EXPORT_NAME' in sflags and sflags.get('MODULARIZE') not in ('1', 'true'):
        findings.append(Finding(
            severity='INFO',
            code='EXPORT_NAME_WITHOUT_MODULARIZE',
            message=f'EXPORT_NAME={sflags["EXPORT_NAME"]} has no effect without MODULARIZE=1.',
            detail='EXPORT_NAME only renames the factory function produced by MODULARIZE. Without MODULARIZE, it is silently ignored.'
        ))

    return findings


# ── Reporting ─────────────────────────────────────────────────────────────────

SEV_ORDER = {'ERROR': 0, 'WARN': 1, 'INFO': 2}

def print_report(findings: list[Finding], flags: list[str], source: str):
    print('')
    print('── Extracted flags ─────────────────────────────────────────────────────')
    print(f'  Source: {source}')
    print(f'  Tokens: {len(flags)}')
    for f in flags:
        print(f'    {f}')

    print('')
    print('── Findings ────────────────────────────────────────────────────────────')

    if not findings:
        print('  No findings.')
        return

    for sev in ('ERROR', 'WARN', 'INFO'):
        for f in findings:
            if f.severity == sev:
                print(f'  [{sev}] [{f.code}] {f.message}')
                if f.detail:
                    for line in f.detail.strip().splitlines():
                        print(f'         {line}')
                print('')


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Audit Emscripten build flags for AudioWorklet compatibility.'
    )
    parser.add_argument('file', help='Makefile or shell script containing the emcc invocation')
    parser.add_argument('--var', help='Makefile variable name containing emcc flags (e.g. WASM_FLAGS)')
    parser.add_argument(
        '--env',
        default='audioworklet',
        choices=['audioworklet', 'worker', 'web', 'node'],
        help='Target execution environment (default: audioworklet)'
    )
    args = parser.parse_args()

    input_path = Path(args.file)
    if not input_path.exists():
        print(f'ERROR: File not found: {input_path}', file=sys.stderr)
        sys.exit(1)

    text = input_path.read_text()
    flags, source = extract_flags_from_text(text, args.var)

    if not flags:
        print(f'WARNING: {source} — no flags extracted. Check --var or verify the file contains an emcc invocation.')
        sys.exit(0)

    sflags = get_sflags(flags)
    findings = check_flags(flags, sflags, args.env)

    print_report(findings, flags, source)

    errors = [f for f in findings if f.severity == 'ERROR']
    warns  = [f for f in findings if f.severity == 'WARN']
    infos  = [f for f in findings if f.severity == 'INFO']

    print('────────────────────────────────────────────────────────────────────────')
    print(f'RESULT: {len(errors)} errors, {len(warns)} warnings, {len(infos)} infos')

    sys.exit(1 if errors else 0)


if __name__ == '__main__':
    main()

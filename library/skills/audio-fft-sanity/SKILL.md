---
name: audio-fft-sanity
description: FFT-based sanity check for audio output files — verifies fundamental frequency, THD, SNR, clipping, and silence. Use after offline C tests or WASM OfflineAudioContext captures to confirm a signal chain is producing correct output.
allowed-tools: Bash
argument-hint: "<audio-file.wav|float32> [--freq HZ] [--sr HZ] [--thd-max PCT] [--snr-min DB] [--channels N]"
---

# Audio FFT Sanity Check

Run a suite of FFT-based assertions on an audio output file to confirm a signal chain is behaving correctly. Suitable for both offline C test output and WASM `OfflineAudioContext` captures.

## Requirements

- Python 3.8+
- `numpy` and `scipy`: `pip install numpy scipy`

## Instructions

Arguments are in `$ARGUMENTS`. Pass them directly to the analysis script:

```bash
python3 "$(dirname "$0")/analyse.py" $ARGUMENTS
```

## Checks performed

| Check | What it detects |
|---|---|
| `CLIPPING` | Any sample magnitude > 0.99 — indicates gain staging problem or overflow |
| `SILENCE` | RMS below -60 dBFS — catches zero-output bugs (uninitialised buffer, wrong pointer) |
| `FUNDAMENTAL` | Detected peak frequency vs `--freq` (if given) — verifies oscillator/filter tuning |
| `THD` | Total harmonic distortion (harmonics 2–5 vs fundamental) — catches nonlinear distortion or aliasing |
| `SNR` | Signal-to-noise ratio estimate — catches noise floor issues or quantisation problems |

## Exit codes

- `0` — all checks passed
- `1` — one or more checks failed

## Examples

```bash
# Basic smoke test — check for clipping, silence, SNR, THD with defaults
python3 analyse.py output.wav

# Verify a 440 Hz sine from a synth, strict THD limit
python3 analyse.py output.wav --freq 440 --thd-max 1.0 --snr-min 60

# Raw float32 file at 48 kHz, stereo interleaved (uses first channel)
python3 analyse.py output.f32 --sr 48000 --channels 2 --freq 1000
```

## Typical usage patterns

**Synthesizer test:** Run the synth at a known pitch (e.g. MIDI A4 = 440 Hz), render N frames to a float32 file, then:
```bash
python3 analyse.py synth_output.wav --freq 440 --thd-max 2.0 --snr-min 50
```

**Effect processor test (e.g. filter, EQ):** Feed a broadband noise or sweep, capture output — omit `--freq` and check only for clipping and SNR:
```bash
python3 analyse.py filtered_output.wav --snr-min 30
```

**Impulse response capture:** Feed a single-sample impulse, check output is non-silent and not clipping:
```bash
python3 analyse.py ir_output.wav
```

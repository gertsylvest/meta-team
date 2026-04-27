#!/usr/bin/env python3
"""
audio-fft-sanity: FFT-based sanity check for audio output files.

Checks: clipping, silence, fundamental frequency, THD, SNR.
Supports .wav files and raw interleaved float32 binary files.

Exit code 0 = all checks passed, 1 = one or more checks failed.
"""

import sys
import argparse
import numpy as np


def load_audio(path, sample_rate=44100, channels=1):
    """Load audio from .wav or raw float32 binary. Returns (sample_rate, float32 array)."""
    if path.lower().endswith(".wav"):
        try:
            from scipy.io import wavfile
        except ImportError:
            sys.exit("FAIL  SETUP  scipy not installed — run: pip install numpy scipy")
        sr, data = wavfile.read(path)
        if data.dtype == np.int16:
            data = data.astype(np.float32) / 32768.0
        elif data.dtype == np.int32:
            data = data.astype(np.float32) / 2147483648.0
        else:
            data = data.astype(np.float32)
        if data.ndim > 1:
            data = data[:, 0]  # first channel only
        return sr, data
    else:
        # Raw interleaved float32
        with open(path, "rb") as f:
            raw = f.read()
        data = np.frombuffer(raw, dtype=np.float32)
        if channels > 1:
            data = data[::channels]  # extract first channel
        return sample_rate, data.copy()


def analyse(samples, sample_rate, expected_freq=None, thd_max=5.0, snr_min=40.0):
    """Run all checks. Prints results and returns True if all pass."""
    results = []
    passed = True
    N = len(samples)

    if N == 0:
        print("FAIL  SETUP  empty audio data")
        return False

    # -------------------------------------------------------------------------
    # Clipping check
    # -------------------------------------------------------------------------
    clip_mask = np.abs(samples) > 0.99
    clip_count = int(np.sum(clip_mask))
    if clip_count > 0:
        results.append(f"FAIL  CLIPPING    {clip_count} sample(s) above 0.99")
        passed = False
    else:
        results.append(f"PASS  CLIPPING    none detected (peak {float(np.max(np.abs(samples))):.4f})")

    # -------------------------------------------------------------------------
    # Silence check
    # -------------------------------------------------------------------------
    rms = float(np.sqrt(np.mean(samples ** 2)))
    rms_db = 20.0 * np.log10(rms + 1e-12)
    if rms_db < -60.0:
        results.append(f"FAIL  SILENCE     RMS {rms_db:.1f} dBFS (threshold -60 dBFS)")
        passed = False
    else:
        results.append(f"PASS  SILENCE     RMS {rms_db:.1f} dBFS")

    # -------------------------------------------------------------------------
    # FFT
    # -------------------------------------------------------------------------
    window = np.hanning(N)
    spectrum = np.abs(np.fft.rfft(samples * window))
    freqs = np.fft.rfftfreq(N, d=1.0 / sample_rate)

    bin_width = float(freqs[1]) if len(freqs) > 1 else 1.0

    # Skip DC / very low frequencies
    dc_bins = max(1, int(20.0 / bin_width))
    peak_idx = int(np.argmax(spectrum[dc_bins:])) + dc_bins
    peak_freq = float(freqs[peak_idx])
    peak_amp = float(spectrum[peak_idx])

    # -------------------------------------------------------------------------
    # Fundamental frequency check
    # -------------------------------------------------------------------------
    if expected_freq is not None:
        tolerance = max(expected_freq * 0.02, bin_width * 2)
        if abs(peak_freq - expected_freq) > tolerance:
            results.append(
                f"FAIL  FUNDAMENTAL detected {peak_freq:.1f} Hz, expected {expected_freq:.1f} Hz"
            )
            passed = False
        else:
            results.append(
                f"PASS  FUNDAMENTAL {peak_freq:.1f} Hz (expected {expected_freq:.1f} Hz)"
            )
    else:
        results.append(f"INFO  FUNDAMENTAL {peak_freq:.1f} Hz (no --freq given)")

    # -------------------------------------------------------------------------
    # THD — harmonics 2–5 vs fundamental
    # -------------------------------------------------------------------------
    window_bins = max(2, int(peak_freq * 0.015 / bin_width))  # ±1.5% of fundamental

    harmonic_power_sum = 0.0
    for h in range(2, 6):
        h_freq = peak_freq * h
        if h_freq >= sample_rate / 2.0:
            break
        h_idx = int(round(h_freq / bin_width))
        lo = max(0, h_idx - window_bins)
        hi = min(len(spectrum), h_idx + window_bins + 1)
        h_amp = float(np.max(spectrum[lo:hi]))
        harmonic_power_sum += h_amp ** 2

    thd = 100.0 * (harmonic_power_sum ** 0.5) / (peak_amp + 1e-12)
    if thd > thd_max:
        results.append(f"FAIL  THD          {thd:.2f}% (max {thd_max:.1f}%)")
        passed = False
    else:
        results.append(f"PASS  THD          {thd:.2f}% (max {thd_max:.1f}%)")

    # -------------------------------------------------------------------------
    # SNR — signal bins (fundamental + harmonics 2–5) vs noise floor
    # -------------------------------------------------------------------------
    signal_bins = set()
    for h in range(1, 6):
        h_freq = peak_freq * h
        if h_freq >= sample_rate / 2.0:
            break
        h_idx = int(round(h_freq / bin_width))
        for b in range(max(0, h_idx - window_bins), min(len(spectrum), h_idx + window_bins + 1)):
            signal_bins.add(b)

    total_power = float(np.sum(spectrum ** 2))
    signal_power = float(sum(spectrum[b] ** 2 for b in signal_bins))
    noise_power = max(total_power - signal_power, 1e-30)
    snr = 10.0 * np.log10(signal_power / noise_power) if signal_power > 0 else -999.0

    if snr < snr_min:
        results.append(f"FAIL  SNR          {snr:.1f} dB (min {snr_min:.1f} dB)")
        passed = False
    else:
        results.append(f"PASS  SNR          {snr:.1f} dB (min {snr_min:.1f} dB)")

    # -------------------------------------------------------------------------
    # Print results
    # -------------------------------------------------------------------------
    print(f"File: {path_hint}  |  SR: {sample_rate} Hz  |  Frames: {N}")
    print()
    for line in results:
        print(line)
    print()
    print("RESULT  " + ("PASS — all checks passed" if passed else "FAIL — one or more checks failed"))
    return passed


# Global for reporting in analyse()
path_hint = ""


def main():
    global path_hint

    try:
        import numpy  # noqa: F401
    except ImportError:
        print("FAIL  SETUP  numpy not installed — run: pip install numpy scipy")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="FFT-based audio sanity check")
    parser.add_argument("file", help=".wav or raw float32 audio file")
    parser.add_argument("--freq", type=float, default=None,
                        help="Expected fundamental frequency in Hz")
    parser.add_argument("--sr", type=int, default=44100,
                        help="Sample rate — required for raw float32 files (default: 44100)")
    parser.add_argument("--channels", type=int, default=1,
                        help="Channel count for raw float32 files, first channel used (default: 1)")
    parser.add_argument("--thd-max", type=float, default=5.0,
                        help="Maximum acceptable THD in percent (default: 5.0)")
    parser.add_argument("--snr-min", type=float, default=40.0,
                        help="Minimum acceptable SNR in dB (default: 40.0)")
    args = parser.parse_args()

    path_hint = args.file
    sr, samples = load_audio(args.file, sample_rate=args.sr, channels=args.channels)
    ok = analyse(samples, sr,
                 expected_freq=args.freq,
                 thd_max=args.thd_max,
                 snr_min=args.snr_min)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

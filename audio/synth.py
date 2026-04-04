"""Audio synthesis for meander.

Frequency mappings
------------------
Sustained tone (arc edge):
    f = TUNING_CONSTANT * sin(θ/2) / 100
    θ = π  (semicircle)  →  440 Hz (A4)
    θ = 0  (straight)    →  0 Hz  (silent)
    Frequency depends only on curvature angle θ, not on node distance.

Percussive hit (node):
    Angle between the incoming and outgoing chord directions.
    θ = π  (straight through)  →  silent
    θ → 0  (acute)             →  PERC_MAX_FREQ
    f = PERC_MAX_FREQ * (π - θ) / π
"""
from __future__ import annotations

import math

import numpy as np

SAMPLE_RATE = 44100          # Hz
TUNING_CONSTANT = 44000.0    # at θ=π (semicircle) with reference chord 200px → 440 Hz
PERC_MAX_FREQ = 4000.0       # Hz at 0° angle
FADE_SAMPLES = 256           # fade-in/out length for sustained tones
PERC_DECAY = 8.0             # decay exponent for percussive envelope


# ---------------------------------------------------------------------------
# Frequency mapping
# ---------------------------------------------------------------------------

def freq_from_curvature(curvature: float) -> float:
    """Map arc curvature angle θ ∈ [0, π] (radians) to frequency (Hz).

    f = TUNING_CONSTANT * sin(θ/2) / 100
    θ = 0   (straight)   → 0 Hz  (silent)
    θ = π   (semicircle) → 440 Hz (A4)
    Frequency is independent of node distance.
    """
    if curvature <= 0.0:
        return 0.0
    theta = min(curvature, math.pi)
    return TUNING_CONSTANT * math.sin(theta / 2.0) / 100.0


def freq_from_angle(angle_rad: float) -> float:
    """Map inter-edge angle (radians) to percussive frequency (Hz).

    angle_rad is the angle between the arriving chord reversed and the
    departing chord, i.e. the turning angle at the node.
    0 = fully acute (max freq), π = straight through (silent).
    """
    angle_rad = max(0.0, min(math.pi, angle_rad))
    return PERC_MAX_FREQ * angle_rad / math.pi #PERC_MAX_FREQ * (math.pi - angle_rad) / math.pi


# ---------------------------------------------------------------------------
# Synthesis
# ---------------------------------------------------------------------------

def generate_sustained(freq: float, duration_s: float) -> np.ndarray:
    """Sine tone at *freq* Hz lasting *duration_s* seconds.

    Returns a float32 mono array.  Returns silence if freq == 0.
    """
    n = max(int(SAMPLE_RATE * duration_s), 1)
    if freq <= 0:
        return np.zeros(n, dtype=np.float32)

    t = np.arange(n, dtype=np.float64) / SAMPLE_RATE
    wave = np.sin(2.0 * np.pi * freq * t).astype(np.float32)

    # Apply fade in/out to prevent clicks
    fade = min(FADE_SAMPLES, n // 2)
    if fade > 0:
        ramp = np.linspace(0.0, 1.0, fade, dtype=np.float32)
        wave[:fade] *= ramp
        wave[n - fade:] *= ramp[::-1]

    return wave


def generate_percussive(freq: float) -> np.ndarray:
    """Tight click/chick hit: bandpass-filtered white noise.

    White noise is passed through a Butterworth bandpass filter centred on
    *freq*, giving a pitched transient with no tonal/sine character.
    Higher frequencies produce a brighter, thinner hit; lower ones a thicker
    thud — all with the same noisy, non-tonal texture.

    Returns a float32 mono array of ~0.1 s.  Returns silence if freq == 0.
    """
    from scipy.signal import butter, sosfilt

    duration_s = 0.10
    n = int(SAMPLE_RATE * duration_s)
    if freq <= 0:
        return np.zeros(n, dtype=np.float32)

    t = np.arange(n, dtype=np.float64) / SAMPLE_RATE

    # White noise
    rng = np.random.default_rng(0)
    noise = rng.standard_normal(n)

    # Bandpass filter: one octave wide (freq/√2 … freq×√2), clamped to Nyquist
    nyq = SAMPLE_RATE / 2.0
    low  = max(freq / 1.414, 20.0)
    high = min(freq * 1.414, nyq * 0.95)
    if low >= high:
        # Very high freq — use a high-pass instead
        sos = butter(4, low / nyq, btype="high", output="sos")
    else:
        sos = butter(4, [low / nyq, high / nyq], btype="band", output="sos")
    filtered = sosfilt(sos, noise)

    # Normalise filtered noise (filter gain varies with bandwidth)
    peak = np.max(np.abs(filtered))
    if peak > 1e-6:
        filtered /= peak

    # Envelope: 2 ms linear attack + fast exponential decay
    attack_samp = int(SAMPLE_RATE * 0.002)
    env = np.exp(-40.0 * t)
    env[:attack_samp] *= np.linspace(0.0, 1.0, attack_samp)

    wave = filtered * env
    return wave.astype(np.float32)

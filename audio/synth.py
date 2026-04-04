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
    """Damped sinusoid at *freq* Hz.

    Returns a float32 mono array of ~0.5 s.  Returns silence if freq == 0.
    """
    duration_s = 0.5
    n = int(SAMPLE_RATE * duration_s)
    if freq <= 0:
        return np.zeros(n, dtype=np.float32)

    t = np.arange(n, dtype=np.float64) / SAMPLE_RATE
    envelope = np.exp(-PERC_DECAY * t).astype(np.float32) # we could add t* to change attack
    wave = np.sin(2.0 * np.pi * freq * t).astype(np.float32)
    return wave * envelope

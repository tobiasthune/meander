"""Audio synthesis for meander.

Frequency mappings
------------------
Sustained tone (arc edge):
    f = TUNING_CONSTANT / radius
    radius = 100 scene-units  →  440 Hz (A4)
    straight edge (radius → ∞)  →  0 Hz  (silent)

Percussive hit (node):
    θ ∈ [0, π] is the angle between the incoming and outgoing tangents.
    θ = π  (straight through)  →  silent
    θ → 0  (acute)             →  PERC_MAX_FREQ
    f = PERC_MAX_FREQ * (π - θ) / π
"""
from __future__ import annotations

import math

import numpy as np

SAMPLE_RATE = 44100          # Hz
TUNING_CONSTANT = 44000.0    # radius 100 scene-units → 440 Hz
PERC_MAX_FREQ = 4000.0       # Hz at 0° angle
FADE_SAMPLES = 256           # fade-in/out length for sustained tones
PERC_DECAY = 8.0             # decay exponent for percussive envelope


# ---------------------------------------------------------------------------
# Frequency mapping
# ---------------------------------------------------------------------------

def freq_from_radius(radius: float) -> float:
    """Map arc radius (scene units) to frequency (Hz).

    Returns 0.0 for straight edges (infinite radius).
    """
    if math.isinf(radius) or radius <= 0:
        return 0.0
    return TUNING_CONSTANT / radius


def freq_from_angle(angle_rad: float) -> float:
    """Map inter-edge angle (radians) to percussive frequency (Hz).

    angle_rad is the angle between the arriving tangent reversed and the
    departing tangent, i.e. the turning angle at the node.
    0 = fully acute (max freq), π = straight through (silent).
    """
    angle_rad = max(0.0, min(math.pi, angle_rad))
    return PERC_MAX_FREQ * (math.pi - angle_rad) / math.pi


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

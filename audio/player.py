"""Non-blocking audio player wrapping sounddevice.

Usage
-----
    player = AudioPlayer()
    player.play(samples)   # queues samples; returns immediately
    player.stop()          # cancels any ongoing playback
"""
from __future__ import annotations

import threading

import numpy as np
import sounddevice as sd

from audio.synth import SAMPLE_RATE


class AudioPlayer:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._stream: sd.OutputStream | None = None

    # ------------------------------------------------------------------
    def play(self, samples: np.ndarray) -> None:
        """Play *samples* (float32, mono) without blocking."""
        self.stop()
        data = np.asarray(samples, dtype=np.float32)
        if data.ndim == 1:
            data = data.reshape(-1, 1)

        with self._lock:
            self._stream = sd.OutputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="float32",
            )
            self._stream.start()
            self._stream.write(data)

    def play_blocking(self, samples: np.ndarray) -> None:
        """Play *samples* and block until playback finishes.

        Called from the traversal thread.
        """
        data = np.asarray(samples, dtype=np.float32)
        sd.play(data, samplerate=SAMPLE_RATE)
        sd.wait()

    def stop(self) -> None:
        """Stop and close any current stream."""
        with self._lock:
            if self._stream is not None:
                try:
                    sd.stop()
                    self._stream.stop(ignore_errors=True)
                    self._stream.close(ignore_errors=True)
                except Exception:
                    pass
                self._stream = None

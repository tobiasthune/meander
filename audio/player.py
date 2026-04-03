"""CompiledPlayer — plays a CompiledPlayback with a synchronised visual event clock.

The audio buffer is handed to sounddevice in one go (non-blocking).
A QTimer polls at ~16 ms intervals, checks wall-clock elapsed time against the
event list, and emits event_triggered for any events that have come due.
This gives canvas highlights that stay in sync with the audio without any
inter-thread communication or blocking calls.

Usage
-----
    player = CompiledPlayer(parent)
    player.event_triggered.connect(lambda kind, id: ...)
    player.finished.connect(on_done)
    player.play(compiled_playback)
    # ...
    player.stop()
"""
from __future__ import annotations

import time
from typing import Optional

import sounddevice as sd
from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from audio.compiler import CompiledPlayback


class CompiledPlayer(QObject):
    # Fired on the main thread when a timed event becomes due.
    # Args: kind ("edge" | "node"), item id (str)
    event_triggered = pyqtSignal(str, str)
    finished = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._compiled: Optional[CompiledPlayback] = None
        self._start_time: float = 0.0
        self._event_idx: int = 0

        self._timer = QTimer(self)
        self._timer.setInterval(16)          # ~60 fps
        self._timer.timeout.connect(self._tick)

    # ------------------------------------------------------------------
    def play(self, compiled: CompiledPlayback) -> None:
        self.stop()
        self._compiled = compiled
        self._event_idx = 0
        sd.play(compiled.audio, samplerate=compiled.sample_rate)
        self._start_time = time.perf_counter()
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()
        sd.stop()
        self._compiled = None

    def is_playing(self) -> bool:
        return self._timer.isActive()

    # ------------------------------------------------------------------
    def _tick(self) -> None:
        if self._compiled is None:
            self._timer.stop()
            return

        elapsed = time.perf_counter() - self._start_time
        events = self._compiled.events

        while (
            self._event_idx < len(events)
            and events[self._event_idx]["t"] <= elapsed
        ):
            e = events[self._event_idx]
            self.event_triggered.emit(e["kind"], e["id"])
            self._event_idx += 1

        # Stop once the full duration + 1 s tail has elapsed
        if elapsed >= self._compiled.duration + 1.0:
            self._timer.stop()
            self._compiled = None
            self.finished.emit()


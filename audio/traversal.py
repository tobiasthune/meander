# Replaced by audio/compiler.py + audio/player.py.
# Kept as an empty module to avoid breaking any external imports.


The Traverser walks a Graph starting from a given node, playing:
  - A sustained tone for each edge (frequency from radius, duration from arc length)
  - A percussive hit at each destination node (frequency from inter-edge angle)

It runs in a QThread so audio blocking calls don't freeze the UI.

Traversal stops when a node has no outgoing edges.
"""
from __future__ import annotations

import math
from typing import Optional, Tuple

from PyQt6.QtCore import QThread, pyqtSignal

from audio.player import AudioPlayer
from audio.synth import (
    freq_from_angle,
    freq_from_radius,
    generate_percussive,
    generate_sustained,
)
from graph.graph import Edge, Graph

# scene-units per second — governs how arc length maps to duration
PIXELS_PER_SECOND = 200.0


class Traverser(QThread):
    """QThread that walks *graph* from *start_node_id*, producing audio."""

    # Emitted when traversal completes or is stopped
    finished = pyqtSignal()
    # Emitted each time a new node is entered  (node_id)
    node_entered = pyqtSignal(str)
    # Emitted each time an edge starts playing (edge_id)
    edge_started = pyqtSignal(str)

    def __init__(
        self,
        graph: Graph,
        player: AudioPlayer,
        start_node_id: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._graph = graph
        self._player = player
        self._start_node_id = start_node_id
        self._stop_requested = False

    # ------------------------------------------------------------------
    def stop_traversal(self) -> None:
        self._stop_requested = True
        self._player.stop()

    # ------------------------------------------------------------------
    def run(self) -> None:
        current_node_id = self._start_node_id
        incoming_edge: Optional[Edge] = None

        while not self._stop_requested:
            outgoing = self._graph.outgoing_edges(current_node_id)
            if not outgoing:
                break

            # Always take the first outgoing edge
            edge = outgoing[0]

            # --- Percussive hit at current node -------------------------
            if incoming_edge is not None:
                angle = _inter_edge_angle(self._graph, incoming_edge, edge)
                perc_freq = freq_from_angle(angle)
                perc = generate_percussive(perc_freq)
                self._player.play_blocking(perc)

            if self._stop_requested:
                break

            # --- Sustained tone along edge ------------------------------
            self.edge_started.emit(edge.id)

            edge_radius = edge.radius
            sus_freq = freq_from_radius(edge_radius)
            duration_s = edge.arc_length(self._graph) / PIXELS_PER_SECOND
            duration_s = max(duration_s, 0.05)  # minimum 50 ms

            sus = generate_sustained(sus_freq, duration_s)
            self._player.play_blocking(sus)

            if self._stop_requested:
                break

            # --- Move to next node --------------------------------------
            incoming_edge = edge
            current_node_id = edge.dst
            self.node_entered.emit(current_node_id)

        self.finished.emit()


# ---------------------------------------------------------------------------
# Geometry helper
# ---------------------------------------------------------------------------

def _inter_edge_angle(graph: Graph, incoming: Edge, outgoing: Edge) -> float:
    """Angle at a node between the arriving and departing edges.

    Returns a value in [0, π]:
        π  = straight through (no bend)
        0  = completely reversed (hairpin)
    """
    # Tangent arriving into the node (direction of travel)
    arr_tx, arr_ty = incoming.tangent_at_dst(graph)
    # Tangent departing from the node
    dep_tx, dep_ty = outgoing.tangent_at_src(graph)

    # Dot product of the two unit vectors
    dot = arr_tx * dep_tx + arr_ty * dep_ty
    dot = max(-1.0, min(1.0, dot))  # clamp for acos safety
    return math.acos(dot)

"""Compile a graph traversal into a single audio buffer and a timed event list.

CompiledPlayback
----------------
    audio   — float32 mono numpy array; the full mixed sound
    events  — list of {"t": float, "kind": "edge"|"node", "id": str}
              sorted by ascending time; used to drive canvas highlights
              in sync with the audio via a wall-clock

Traversal rules
---------------
- Follow the first outgoing edge from each node
- Stop at dead ends or on a revisited edge (cycle guard)
- Each edge contributes a sustained sine tone (radius → freq, arc_length → duration)
- Each node arrival (except the very first) contributes a percussive hit
  whose pitch is determined by the turn angle between the incoming and outgoing edge
- Percussive hit and edge tone both start at the same t (they mix together)
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np

from audio.synth import (
    SAMPLE_RATE,
    freq_from_angle,
    freq_from_radius,
    generate_percussive,
    generate_sustained,
)
from graph.graph import Edge, Graph

PIXELS_PER_SECOND = 200.0


@dataclass
class CompiledPlayback:
    audio: np.ndarray          # float32 mono, full mix
    sample_rate: int
    events: List[dict]         # sorted: {"t": float, "kind": "edge"|"node", "id": str}
    duration: float            # seconds of meaningful content (excludes tail)


def compile_traversal(graph_dict: dict) -> CompiledPlayback:
    """Walk *graph_dict*, synthesise every edge tone and node hit, mix into one buffer."""
    from graph.serializer import from_dict

    graph = from_dict(graph_dict)
    start_id = graph_dict["start_node_id"]

    # ------------------------------------------------------------------
    # Walk the graph, collecting (t_start, kind, id, samples) tuples
    # ------------------------------------------------------------------
    steps: list = []   # (t_start: float, kind: str, id: str, samples: ndarray)
    t = 0.0
    current_node_id = start_id
    incoming_edge: Optional[Edge] = None
    visited_edges: set = set()

    while True:
        outgoing = graph.outgoing_edges(current_node_id)
        if not outgoing:
            break
        edge = outgoing[0]
        if edge.id in visited_edges:
            break
        visited_edges.add(edge.id)

        # Percussive hit at this node (fires at the same time as the edge tone)
        if incoming_edge is not None:
            angle = _inter_edge_angle(graph, incoming_edge, edge)
            perc_freq = freq_from_angle(angle)
            if perc_freq > 0:
                perc_samples = generate_percussive(perc_freq)
                steps.append((t, "node", current_node_id, perc_samples))

        # Sustained tone along this edge
        edge_duration = max(edge.arc_length(graph) / PIXELS_PER_SECOND, 0.05)
        sus_freq = freq_from_radius(edge.radius)
        sus_samples = generate_sustained(sus_freq, edge_duration)
        steps.append((t, "edge", edge.id, sus_samples))

        t += edge_duration
        incoming_edge = edge
        current_node_id = edge.dst

    # ------------------------------------------------------------------
    # Empty graph — return one second of silence
    # ------------------------------------------------------------------
    if not steps:
        return CompiledPlayback(
            audio=np.zeros(SAMPLE_RATE, dtype=np.float32),
            sample_rate=SAMPLE_RATE,
            events=[],
            duration=0.0,
        )

    # ------------------------------------------------------------------
    # Mix all samples into a single buffer
    # Add a 1 s tail so percussive decays at the end are not cut off
    # ------------------------------------------------------------------
    total_samples = int((t + 1.0) * SAMPLE_RATE)
    buffer = np.zeros(total_samples, dtype=np.float32)
    events: List[dict] = []

    for t_start, kind, item_id, samples in steps:
        start_idx = int(t_start * SAMPLE_RATE)
        n = min(len(samples), total_samples - start_idx)
        if n > 0:
            buffer[start_idx: start_idx + n] += samples[:n]
        events.append({"t": t_start, "kind": kind, "id": item_id})

    # Normalise to prevent clipping while preserving relative levels
    peak = float(np.max(np.abs(buffer)))
    if peak > 0.9:
        buffer *= 0.9 / peak

    events.sort(key=lambda e: e["t"])
    return CompiledPlayback(
        audio=buffer,
        sample_rate=SAMPLE_RATE,
        events=events,
        duration=t,
    )


# ---------------------------------------------------------------------------
# Geometry helper
# ---------------------------------------------------------------------------

def _inter_edge_angle(graph: Graph, incoming: Edge, outgoing: Edge) -> float:
    """Angle between the arriving and departing tangents at a node, in [0, π]."""
    arr_tx, arr_ty = incoming.tangent_at_dst(graph)
    dep_tx, dep_ty = outgoing.tangent_at_src(graph)
    dot = max(-1.0, min(1.0, arr_tx * dep_tx + arr_ty * dep_ty))
    return math.acos(dot)

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class Node:
    id: str
    x: float
    y: float

    @staticmethod
    def new(x: float, y: float) -> "Node":
        return Node(id=str(uuid.uuid4()), x=x, y=y)

    def pos(self) -> Tuple[float, float]:
        return (self.x, self.y)


@dataclass
class Edge:
    """A directed edge from src to dst.

    shape:
        'straight'  – infinite radius, silent
        'arc'       – circular arc; radius controls frequency

    arc_side:
        'left'  – arc bows to the left of the src→dst direction
        'right' – arc bows to the right

    length:
        Geometric arc length (radius × subtended_angle) in scene units.
        For straight edges this is the Euclidean chord length.

    radius:
        Arc radius in scene units. float('inf') means straight.
        Frequency = TUNING_CONSTANT / radius  (see audio/synth.py).
    """

    id: str
    src: str  # node id
    dst: str  # node id
    shape: str = "straight"  # 'straight' | 'arc'
    radius: float = float("inf")
    arc_side: str = "left"  # 'left' | 'right'
    # length is derived from geometry when None; can be overridden
    _length_override: Optional[float] = field(default=None, repr=False)

    @staticmethod
    def new(
        src: str,
        dst: str,
        shape: str = "straight",
        radius: float = float("inf"),
        arc_side: str = "left",
        length: Optional[float] = None,
    ) -> "Edge":
        return Edge(
            id=str(uuid.uuid4()),
            src=src,
            dst=dst,
            shape=shape,
            radius=radius,
            arc_side=arc_side,
            _length_override=length,
        )

    # ------------------------------------------------------------------
    # Geometry helpers
    # ------------------------------------------------------------------

    def chord_length(self, graph: "Graph") -> float:
        """Euclidean distance between src and dst nodes."""
        src_node = graph.nodes[self.src]
        dst_node = graph.nodes[self.dst]
        dx = dst_node.x - src_node.x
        dy = dst_node.y - src_node.y
        return math.hypot(dx, dy)

    def subtended_half_angle(self, graph: "Graph") -> float:
        """Half-angle α such that chord = 2*r*sin(α).  Returns 0 for straight."""
        if self.shape == "straight" or math.isinf(self.radius):
            return 0.0
        c = self.chord_length(graph)
        # clamp to avoid domain errors from rounding
        ratio = min(c / (2.0 * self.radius), 1.0)
        return math.asin(ratio)

    def arc_length(self, graph: "Graph") -> float:
        """Geometric arc length: r * 2α  (or chord for straight)."""
        if self._length_override is not None:
            return self._length_override
        if self.shape == "straight" or math.isinf(self.radius):
            return self.chord_length(graph)
        alpha = self.subtended_half_angle(graph)
        return self.radius * 2.0 * alpha

    def set_length(self, value: Optional[float]) -> None:
        self._length_override = value

    # ------------------------------------------------------------------
    # Tangent directions (unit vectors) at src and dst endpoints
    # Used by the traversal engine to compute inter-edge angles.
    # ------------------------------------------------------------------

    def tangent_at_src(self, graph: "Graph") -> Tuple[float, float]:
        """Unit tangent vector pointing away from src toward dst."""
        src_node = graph.nodes[self.src]
        dst_node = graph.nodes[self.dst]
        return _arc_tangent_at_start(
            src_node.x, src_node.y,
            dst_node.x, dst_node.y,
            self.radius,
            self.arc_side,
            self.shape,
        )

    def tangent_at_dst(self, graph: "Graph") -> Tuple[float, float]:
        """Unit tangent vector pointing *into* dst (arriving direction)."""
        src_node = graph.nodes[self.src]
        dst_node = graph.nodes[self.dst]
        return _arc_tangent_at_end(
            src_node.x, src_node.y,
            dst_node.x, dst_node.y,
            self.radius,
            self.arc_side,
            self.shape,
        )

    # ------------------------------------------------------------------
    # Center of the arc circle (used for drawing)
    # ------------------------------------------------------------------

    def arc_center(self, graph: "Graph") -> Optional[Tuple[float, float]]:
        """Returns the center of the arc circle, or None for straight edges."""
        if self.shape == "straight" or math.isinf(self.radius):
            return None
        src_node = graph.nodes[self.src]
        dst_node = graph.nodes[self.dst]
        return _arc_center(
            src_node.x, src_node.y,
            dst_node.x, dst_node.y,
            self.radius,
            self.arc_side,
        )


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------

class Graph:
    def __init__(self) -> None:
        self.nodes: Dict[str, Node] = {}
        self.edges: Dict[str, Edge] = {}
        # adjacency: src_id -> list of edge ids (outgoing)
        self._outgoing: Dict[str, List[str]] = {}
        # reverse: dst_id -> list of edge ids (incoming)
        self._incoming: Dict[str, List[str]] = {}

        # The start node is created once at construction and cannot be removed.
        start = Node.new(0.0, 0.0)
        self.start_node_id: str = start.id
        self.add_node(start)

    # ------------------------------------------------------------------
    def add_node(self, node: Node) -> Node:
        self.nodes[node.id] = node
        self._outgoing.setdefault(node.id, [])
        self._incoming.setdefault(node.id, [])
        return node

    def remove_node(self, node_id: str) -> None:
        # The start node is permanent.
        if node_id == self.start_node_id:
            return
        # remove all connected edges first
        for eid in list(self._outgoing.get(node_id, [])):
            self.remove_edge(eid)
        for eid in list(self._incoming.get(node_id, [])):
            self.remove_edge(eid)
        del self.nodes[node_id]
        self._outgoing.pop(node_id, None)
        self._incoming.pop(node_id, None)

    # ------------------------------------------------------------------
    def add_edge(self, edge: Edge) -> Edge:
        self.edges[edge.id] = edge
        self._outgoing.setdefault(edge.src, [])
        self._incoming.setdefault(edge.dst, [])
        self._outgoing[edge.src].append(edge.id)
        self._incoming[edge.dst].append(edge.id)
        return edge

    def remove_edge(self, edge_id: str) -> None:
        edge = self.edges.pop(edge_id, None)
        if edge is None:
            return
        try:
            self._outgoing[edge.src].remove(edge_id)
        except (KeyError, ValueError):
            pass
        try:
            self._incoming[edge.dst].remove(edge_id)
        except (KeyError, ValueError):
            pass

    # ------------------------------------------------------------------
    def outgoing_edges(self, node_id: str) -> List[Edge]:
        return [self.edges[eid] for eid in self._outgoing.get(node_id, [])]

    def incoming_edges(self, node_id: str) -> List[Edge]:
        return [self.edges[eid] for eid in self._incoming.get(node_id, [])]

    def first_node(self) -> Optional[Node]:
        """Returns the first node added, or None."""
        for node in self.nodes.values():
            return node
        return None


# ---------------------------------------------------------------------------
# Internal geometry helpers
# ---------------------------------------------------------------------------

def _chord_vector(x1: float, y1: float, x2: float, y2: float) -> Tuple[float, float]:
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy)
    if length == 0:
        return (1.0, 0.0)
    return (dx / length, dy / length)


def _perpendicular(vx: float, vy: float, side: str) -> Tuple[float, float]:
    """90° rotation of unit vector.  'left' = CCW, 'right' = CW."""
    if side == "left":
        return (-vy, vx)
    return (vy, -vx)


def _arc_center(
    x1: float, y1: float, x2: float, y2: float,
    radius: float, arc_side: str,
) -> Tuple[float, float]:
    """Center of the circular arc through (x1,y1) and (x2,y2) with given radius."""
    dx, dy = x2 - x1, y2 - y1
    chord = math.hypot(dx, dy)
    if chord == 0:
        return (x1, y1)
    # distance from midpoint to center along perpendicular
    half_chord = chord / 2.0
    # clamp to avoid sqrt of negative from floating point
    d = math.sqrt(max(radius ** 2 - half_chord ** 2, 0.0))
    mx, my = (x1 + x2) / 2.0, (y1 + y2) / 2.0
    ux, uy = _chord_vector(x1, y1, x2, y2)
    px, py = _perpendicular(ux, uy, arc_side)
    return (mx + px * d, my + py * d)


def _arc_tangent_at_start(
    x1: float, y1: float, x2: float, y2: float,
    radius: float, arc_side: str, shape: str,
) -> Tuple[float, float]:
    """Unit tangent leaving (x1,y1) along the arc toward (x2,y2)."""
    if shape == "straight" or math.isinf(radius):
        return _chord_vector(x1, y1, x2, y2)
    cx, cy = _arc_center(x1, y1, x2, y2, radius, arc_side)
    # radius vector from center to start
    rx, ry = x1 - cx, y1 - cy
    r = math.hypot(rx, ry)
    if r == 0:
        return _chord_vector(x1, y1, x2, y2)
    # tangent perpendicular to radius; direction depends on arc_side
    if arc_side == "left":
        # CCW arc: tangent = rotate radius 90° CW
        tx, ty = ry / r, -rx / r
    else:
        # CW arc: tangent = rotate radius 90° CCW
        tx, ty = -ry / r, rx / r
    # ensure tangent points generally toward dst
    dx, dy = x2 - x1, y2 - y1
    if tx * dx + ty * dy < 0:
        tx, ty = -tx, -ty
    return (tx, ty)


def _arc_tangent_at_end(
    x1: float, y1: float, x2: float, y2: float,
    radius: float, arc_side: str, shape: str,
) -> Tuple[float, float]:
    """Unit tangent arriving at (x2,y2) along the arc from (x1,y1)."""
    if shape == "straight" or math.isinf(radius):
        return _chord_vector(x1, y1, x2, y2)
    cx, cy = _arc_center(x1, y1, x2, y2, radius, arc_side)
    rx, ry = x2 - cx, y2 - cy
    r = math.hypot(rx, ry)
    if r == 0:
        return _chord_vector(x1, y1, x2, y2)
    if arc_side == "left":
        tx, ty = ry / r, -rx / r
    else:
        tx, ty = -ry / r, rx / r
    dx, dy = x2 - x1, y2 - y1
    if tx * dx + ty * dy < 0:
        tx, ty = -tx, -ty
    return (tx, ty)

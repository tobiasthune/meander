"""
Graph data model: Node, Edge, Graph, RoutingType.
All geometry is stored as plain floats (scene coordinates).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Tuple


class RoutingType(Enum):
    PASS_THROUGH = auto()   # single out-edge, follow it
    RANDOM_FORK  = auto()   # multiple out-edges, pick one at random
    PARALLEL_FORK = auto()  # multiple out-edges, spawn a spark on each
    SINK         = auto()   # no out-edges / terminate spark here


@dataclass
class Node:
    id: str
    x: float
    y: float
    routing: RoutingType = RoutingType.RANDOM_FORK

    # convenience
    def pos(self) -> Tuple[float, float]:
        return (self.x, self.y)


@dataclass
class Edge:
    id: str
    source_id: str
    target_id: str
    # Signed perpendicular offset from the chord midpoint.
    # Positive = arc bows left (from source→target), negative = right.
    # 0 = straight line.
    radius: float = 0.0


@dataclass
class Graph:
    nodes: Dict[str, Node] = field(default_factory=dict)
    edges: Dict[str, Edge] = field(default_factory=dict)
    bpm: float = 90.0

    # ------------------------------------------------------------------ #
    # Factories                                                            #
    # ------------------------------------------------------------------ #
    def add_node(self, x: float, y: float,
                 routing: RoutingType = RoutingType.RANDOM_FORK) -> Node:
        node = Node(id=_uid(), x=x, y=y, routing=routing)
        self.nodes[node.id] = node
        return node

    def add_edge(self, source_id: str, target_id: str,
                 radius: float = 0.0) -> Edge:
        edge = Edge(id=_uid(), source_id=source_id, target_id=target_id,
                    radius=radius)
        self.edges[edge.id] = edge
        return edge

    def remove_node(self, node_id: str) -> None:
        """Remove node and all connected edges."""
        self.nodes.pop(node_id, None)
        to_remove = [eid for eid, e in self.edges.items()
                     if e.source_id == node_id or e.target_id == node_id]
        for eid in to_remove:
            self.edges.pop(eid)

    def remove_edge(self, edge_id: str) -> None:
        self.edges.pop(edge_id, None)

    def out_edges(self, node_id: str) -> List[Edge]:
        return [e for e in self.edges.values() if e.source_id == node_id]

    def in_edges(self, node_id: str) -> List[Edge]:
        return [e for e in self.edges.values() if e.target_id == node_id]


def _uid() -> str:
    return uuid.uuid4().hex[:12]

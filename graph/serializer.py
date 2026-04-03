"""Serialise / deserialise a Graph to/from plain Python dicts.

Dict schema
-----------
{
    "start_node_id": str,
    "nodes": {
        "<id>": {"id": str, "x": float, "y": float},
        ...
    },
    "edges": {
        "<id>": {
            "id":       str,
            "src":      str,
            "dst":      str,
            "shape":    "straight" | "arc",
            "radius":   float,         # float("inf") for straight
            "arc_side": "left" | "right",
            "length":   float | None,  # None = auto from geometry
        },
        ...
    },
    "outgoing": {
        "<node_id>": ["<edge_id>", ...],   # ordered outgoing edge ids
        ...
    },
}
"""
from __future__ import annotations

from graph.graph import Edge, Graph, Node


def to_dict(graph: Graph) -> dict:
    return {
        "start_node_id": graph.start_node_id,
        "nodes": {
            nid: {"id": nid, "x": n.x, "y": n.y}
            for nid, n in graph.nodes.items()
        },
        "edges": {
            eid: {
                "id":       eid,
                "src":      e.src,
                "dst":      e.dst,
                "shape":    e.shape,
                "radius":   e.radius,
                "arc_side": e.arc_side,
                "length":   e._length_override,
            }
            for eid, e in graph.edges.items()
        },
        "outgoing": {
            nid: list(eids)
            for nid, eids in graph._outgoing.items()
        },
    }


def from_dict(d: dict) -> Graph:
    """Reconstruct a Graph from a dict snapshot.

    Bypasses Graph.__init__ so no auto start-node is created.
    Useful for the compiler, which works from a point-in-time snapshot.
    """
    g = object.__new__(Graph)
    g.nodes = {}
    g.edges = {}
    g._outgoing = {}
    g._incoming = {}
    g.start_node_id = d["start_node_id"]

    for nd in d["nodes"].values():
        nid = nd["id"]
        g.nodes[nid] = Node(id=nid, x=nd["x"], y=nd["y"])
        g._outgoing.setdefault(nid, [])
        g._incoming.setdefault(nid, [])

    for ed in d["edges"].values():
        e = Edge(
            id=ed["id"],
            src=ed["src"],
            dst=ed["dst"],
            shape=ed["shape"],
            radius=ed["radius"],
            arc_side=ed["arc_side"],
            _length_override=ed["length"],
        )
        g.edges[e.id] = e
        g._outgoing.setdefault(e.src, [])
        g._incoming.setdefault(e.dst, [])

    # Restore outgoing order exactly as captured
    for nid, eids in d["outgoing"].items():
        g._outgoing[nid] = list(eids)

    # Rebuild incoming from edges
    for e in g.edges.values():
        lst = g._incoming.setdefault(e.dst, [])
        if e.id not in lst:
            lst.append(e.id)

    return g

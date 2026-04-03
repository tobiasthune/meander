"""
Circle-arc geometry for edges.

Each edge is a circular arc defined by two endpoints and a signed radius.
The sagitta (midpoint offset) equals radius/2, giving exact closed-form
formulas for arc length and curvature — no integration needed.

Rendering uses a quadratic bezier via QPainterPath as a visual approximation.
"""
from __future__ import annotations

import math
from typing import Tuple

Point = Tuple[float, float]


def ctrl_from_radius(p0: Point, p2: Point, radius: float) -> Point:
    """Quadratic bezier control point: chord midpoint offset perpendicularly by radius."""
    mx, my = (p0[0] + p2[0]) * 0.5, (p0[1] + p2[1]) * 0.5
    dx, dy = p2[0] - p0[0], p2[1] - p0[1]
    length = math.hypot(dx, dy)
    if length < 1e-9:
        return (mx, my)
    px, py = -dy / length, dx / length   # perpendicular unit vector (CCW)
    return (mx + px * radius, my + py * radius)


def arc_point(p0: Point, p2: Point, radius: float, s: float) -> Point:
    """
    Position along the arc at normalised arc-length fraction s ∈ [0, 1].
    Uses the circle centre and subtended angle directly.
    """
    chord = math.hypot(p2[0] - p0[0], p2[1] - p0[1])
    h = radius / 2
    if abs(h) < 1e-6 or chord < 1e-9:
        # Straight line
        return (p0[0] + s * (p2[0] - p0[0]), p0[1] + s * (p2[1] - p0[1]))
    R = (chord ** 2 / 4 + h ** 2) / (2 * abs(h))
    # Half-angle subtended by the chord
    half_theta = math.asin(min(chord / (2 * R), 1.0))
    # Direction: midpoint of chord, then perpendicular toward centre
    mx, my = (p0[0] + p2[0]) * 0.5, (p0[1] + p2[1]) * 0.5
    dx, dy = p2[0] - p0[0], p2[1] - p0[1]
    length = math.hypot(dx, dy)
    px, py = -dy / length, dx / length          # CCW perpendicular
    sign = 1.0 if radius >= 0 else -1.0
    # Centre is on the opposite side of the chord from the sagitta
    dist_to_centre = R - abs(h)
    cx = mx - sign * px * dist_to_centre
    cy = my - sign * py * dist_to_centre
    # Angle from centre to p0, then sweep by s * full_theta.
    # The centre is on the opposite side from the arc, so the sweep is opposite to sign.
    angle_start = math.atan2(p0[1] - cy, p0[0] - cx)
    full_theta = -2 * half_theta * sign
    angle = angle_start + s * full_theta
    return (cx + R * math.cos(angle), cy + R * math.sin(angle))


def arc_length(p0: Point, p2: Point, radius: float) -> float:
    """Exact arc length: R·θ from chord and sagitta = radius/2."""
    chord = math.hypot(p2[0] - p0[0], p2[1] - p0[1])
    h = radius / 2
    if abs(h) < 1e-6:
        return chord
    R = (chord ** 2 / 4 + h ** 2) / (2 * abs(h))
    return 2 * R * math.asin(min(chord / (2 * R), 1.0))


def normalized_curvature(p0: Point, p2: Point, radius: float) -> float:
    """Curvature in [0, 1]: |radius| relative to half the chord length."""
    chord = math.hypot(p2[0] - p0[0], p2[1] - p0[1])
    if chord < 1e-6:
        return 0.0
    return min(abs(radius) / (chord * 0.5), 1.0)


def edge_angle_at_node(in_p0: Point, in_p1: Point, in_p2: Point,
                       out_p0: Point, out_p1: Point, out_p2: Point) -> float:
    """
    Angle (radians, 0–π) between arrival and departure tangents at the shared node.
    For a quadratic bezier the endpoint tangents are the control-polygon edges:
    tangent at t=1 is (p2-p1), tangent at t=0 is (p1-p0).

    0   → straight through.  π/2 → 90° turn.  π → U-turn.
    """
    in_tx,  in_ty  = in_p2[0]  - in_p1[0],  in_p2[1]  - in_p1[1]
    out_tx, out_ty = out_p1[0] - out_p0[0], out_p1[1] - out_p0[1]

    in_len  = math.hypot(in_tx,  in_ty)
    out_len = math.hypot(out_tx, out_ty)
    if in_len < 1e-9 or out_len < 1e-9:
        return 0.0

    dot = (in_tx * out_tx + in_ty * out_ty) / (in_len * out_len)
    return math.pi - math.acos(max(-1.0, min(1.0, dot)))

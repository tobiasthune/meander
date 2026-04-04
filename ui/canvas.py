"""Interactive canvas for the meander graph editor.

Interaction model
-----------------
- Double-click on empty canvas  → create new node
- Drag from a node's edge-port  → rubber-band preview → release on another node → create edge
- Click a node                  → select it
- Click an edge                 → select it (properties panel will update)
- Drag a node                   → reposition it; all attached edges redraw
- Drag an edge's midpoint handle→ adjust arc radius / arc_side
- Delete key                    → remove selected item
"""
from __future__ import annotations

import math
from typing import Dict, Optional

from PyQt6.QtCore import QPointF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsScene,
    QGraphicsView,
)

from graph.graph import Edge, Graph, Node

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NODE_RADIUS = 16.0
NODE_COLOR = QColor("#e8e8e8")
NODE_BORDER_COLOR = QColor("#555555")
NODE_SELECTED_COLOR = QColor("#ffd700")
NODE_START_COLOR = QColor("#50c878")   # green fill for start node
NODE_PORT_RADIUS = 6.0
NODE_PORT_COLOR = QColor("#4a90d9")

EDGE_COLOR = QColor("#333333")
EDGE_SELECTED_COLOR = QColor("#ffd700")
EDGE_WIDTH = 2.0

HANDLE_RADIUS = 7.0
HANDLE_COLOR = QColor("#e04040")

RUBBER_BAND_COLOR = QColor("#4a90d9")

ARROW_SIZE = 10.0


# ===========================================================================
# NodeItem
# ===========================================================================

class NodeItem(QGraphicsEllipseItem):
    def __init__(self, node: Node, canvas: "GraphCanvas") -> None:
        r = NODE_RADIUS
        super().__init__(-r, -r, 2 * r, 2 * r)
        self.node = node
        self.canvas = canvas

        self.setPos(node.x, node.y)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        self.setZValue(10)

        self._update_appearance()

    # ------------------------------------------------------------------
    def _update_appearance(self) -> None:
        is_start = (self.canvas._graph.start_node_id == self.node.id)
        if self.isSelected():
            color = NODE_SELECTED_COLOR
        elif is_start:
            color = NODE_START_COLOR
        else:
            color = NODE_COLOR
        self.setBrush(color)
        pen_width = 3.5 if is_start else 2.0
        self.setPen(QPen(NODE_BORDER_COLOR, pen_width))

    # ------------------------------------------------------------------
    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            # Sync model
            self.node.x = self.pos().x()
            self.node.y = self.pos().y()
            # Redraw all connected edges
            self.canvas.update_edges_for_node(self.node.id)
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            self._update_appearance()
            if self.isSelected():
                self.canvas.node_selected.emit(self.node.id)
        return super().itemChange(change, value)

    # ------------------------------------------------------------------
    # Port drag — initiated from the perimeter of the node
    def hoverMoveEvent(self, event) -> None:
        # Show an arrow cursor when near the border to hint dragging an edge
        pos = event.pos()
        dist = math.hypot(pos.x(), pos.y())
        if abs(dist - NODE_RADIUS) < NODE_PORT_RADIUS + 2:
            self.setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.setCursor(Qt.CursorShape.SizeAllCursor)
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event) -> None:
        pos = event.pos()
        dist = math.hypot(pos.x(), pos.y())
        if (
            abs(dist - NODE_RADIUS) < NODE_PORT_RADIUS + 4
            and event.button() == Qt.MouseButton.LeftButton
        ):
            # Start edge drag
            self.canvas.begin_edge_drag(self, event.scenePos())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self.canvas.is_dragging_edge():
            self.canvas.update_edge_drag(event.scenePos())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self.canvas.is_dragging_edge():
            self.canvas.end_edge_drag(event.scenePos())
            event.accept()
            return
        super().mouseReleaseEvent(event)


# ===========================================================================
# MidpointHandle  (small draggable circle on each EdgeItem)
# ===========================================================================

class MidpointHandle(QGraphicsEllipseItem):
    def __init__(self, edge_item: "EdgeItem") -> None:
        r = HANDLE_RADIUS
        super().__init__(-r, -r, 2 * r, 2 * r)
        self.edge_item = edge_item
        self.setBrush(HANDLE_COLOR)
        self.setPen(QPen(Qt.GlobalColor.white, 1.5))
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setZValue(20)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            if not self.edge_item._repositioning_handle:
                self.edge_item.handle_moved(self.pos())
        return super().itemChange(change, value)

    def mousePressEvent(self, event) -> None:
        # Clear the scene selection so no other item (e.g. a selected node) gets
        # dragged along while curvature is being adjusted.
        self.scene().clearSelection()
        super().mousePressEvent(event)


# ===========================================================================
# EdgeItem
# ===========================================================================

class EdgeItem(QGraphicsPathItem):
    def __init__(self, edge: Edge, graph: Graph, canvas: "GraphCanvas") -> None:
        super().__init__()
        self.edge = edge
        self.graph = graph
        self.canvas = canvas
        self._repositioning_handle = False

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        self.setZValue(5)

        pen = QPen(EDGE_COLOR, EDGE_WIDTH)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        self.setPen(pen)

        # Midpoint handle
        self.handle = MidpointHandle(self)
        self.canvas.scene().addItem(self.handle)

        self.redraw()

    # ------------------------------------------------------------------
    def remove_from_scene(self) -> None:
        self.canvas.scene().removeItem(self.handle)
        self.canvas.scene().removeItem(self)

    # ------------------------------------------------------------------
    def redraw(self) -> None:
        edge = self.edge
        graph = self.graph
        src = graph.nodes.get(edge.src)
        dst = graph.nodes.get(edge.dst)
        if src is None or dst is None:
            return

        path = QPainterPath()

        if edge.curvature > 0:
            center = edge.arc_center(graph)
            if center is None:
                _draw_straight(path, src, dst)
            else:
                _draw_arc(path, src, dst, edge, graph)
        else:
            _draw_straight(path, src, dst)

        self.setPath(path)

        # Place handle at the analytic arc sagitta point, not path.pointAtPercent(0.5)
        # (the path includes arrowhead segments which would shift the 50% point off the arc).
        self._repositioning_handle = True
        hx, hy = _sagitta_point(src, dst, self.edge, self.graph)
        self.handle.setPos(QPointF(hx, hy))
        self._repositioning_handle = False

        # Highlight selected state
        pen = self.pen()
        pen.setColor(EDGE_SELECTED_COLOR if self.isSelected() else EDGE_COLOR)
        self.setPen(pen)

    # ------------------------------------------------------------------
    def handle_moved(self, handle_pos: QPointF) -> None:
        """Recompute edge curvature (arc angle θ) from how the handle was dragged."""
        edge = self.edge
        graph = self.graph
        src_node = graph.nodes.get(edge.src)
        dst_node = graph.nodes.get(edge.dst)
        if src_node is None or dst_node is None:
            return

        sx, sy = src_node.x, src_node.y
        dx, dy = dst_node.x, dst_node.y
        hx, hy = handle_pos.x(), handle_pos.y()

        chord_x, chord_y = dx - sx, dy - sy
        chord_len = math.hypot(chord_x, chord_y)

        if chord_len < 2.0:
            return

        # Signed sagitta: perpendicular component of (handle - chord_midpoint).
        # Equivalent to cross / chord_len (distance from handle to chord line).
        # Negative = handle is visually above the chord = "left" in Qt (y-down).
        cross = chord_x * (hy - sy) - chord_y * (hx - sx)
        sagitta_signed = cross / chord_len
        arc_side = "left" if sagitta_signed < 0 else "right"

        SNAP_THRESHOLD = 10.0  # px — dead zone around chord line → straight
        s = abs(sagitta_signed)
        if s < SNAP_THRESHOLD:
            edge.curvature = 0.0
        else:
            # θ = 4·atan(2s/chord)  — exact for a handle at the arc midpoint;
            # for off-bisector drags s is the projected sagitta, same formula.
            # Capped at π (semicircle).
            theta = min(4.0 * math.atan(2.0 * s / chord_len), math.pi)
            edge.curvature = theta
            edge.arc_side = arc_side

        self.redraw()
        self.canvas.edge_changed.emit(edge.id)

    # ------------------------------------------------------------------
    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            self.redraw()
            if self.isSelected():
                self.canvas.edge_selected.emit(self.edge.id)
        return super().itemChange(change, value)

    # ------------------------------------------------------------------
    # Make the edge easier to click by using a wider hit area
    def shape(self):  # type: ignore[override]
        stroker_path = QPainterPath(self.path())
        from PyQt6.QtGui import QPainterPathStroker
        stroker = QPainterPathStroker()
        stroker.setWidth(12.0)
        return stroker.createStroke(stroker_path)


# ===========================================================================
# RubberBandEdge — temporary preview while dragging a new edge
# ===========================================================================

class RubberBandEdge(QGraphicsPathItem):
    def __init__(self) -> None:
        super().__init__()
        pen = QPen(RUBBER_BAND_COLOR, EDGE_WIDTH, Qt.PenStyle.DashLine)
        self.setPen(pen)
        self.setZValue(50)

    def update_path(self, start: QPointF, end: QPointF) -> None:
        path = QPainterPath(start)
        path.lineTo(end)
        self.setPath(path)


# ===========================================================================
# GraphCanvas
# ===========================================================================

class GraphCanvas(QGraphicsView):
    # Emitted when a node is selected
    node_selected = pyqtSignal(str)
    # Emitted when an edge is selected
    edge_selected = pyqtSignal(str)
    # Emitted when an edge's geometry changes (radius/arc_side)
    edge_changed = pyqtSignal(str)
    # Emitted when a new edge is created
    edge_created = pyqtSignal(str)
    # Emitted when a new node is created
    node_created = pyqtSignal(str)

    def __init__(self, graph: Graph, parent=None) -> None:
        super().__init__(parent)
        self._graph = graph

        self._scene = QGraphicsScene(self)
        self._scene.setSceneRect(-2000, -2000, 4000, 4000)
        self.setScene(self._scene)

        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)

        # Items keyed by model id
        self._node_items: Dict[str, NodeItem] = {}
        self._edge_items: Dict[str, EdgeItem] = {}

        # Edge drag state
        self._dragging_edge = False
        self._drag_src_item: Optional[NodeItem] = None
        self._rubber_band: Optional[RubberBandEdge] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_node_item(self, node: Node) -> NodeItem:
        item = NodeItem(node, self)
        self._scene.addItem(item)
        self._node_items[node.id] = item
        return item

    def add_edge_item(self, edge: Edge) -> EdgeItem:
        item = EdgeItem(edge, self._graph, self)
        self._scene.addItem(item)
        self._edge_items[edge.id] = item
        return item

    def remove_selected(self) -> None:
        for item in self._scene.selectedItems():
            if isinstance(item, NodeItem):
                # The start node cannot be deleted
                if item.node.id == self._graph.start_node_id:
                    continue
                self._graph.remove_node(item.node.id)
                # Also remove connected EdgeItems
                for eid, ei in list(self._edge_items.items()):
                    if ei.edge.src == item.node.id or ei.edge.dst == item.node.id:
                        ei.remove_from_scene()
                        del self._edge_items[eid]
                self._scene.removeItem(item)
                del self._node_items[item.node.id]
            elif isinstance(item, EdgeItem):
                self._graph.remove_edge(item.edge.id)
                item.remove_from_scene()
                del self._edge_items[item.edge.id]

    def update_edges_for_node(self, node_id: str) -> None:
        for ei in self._edge_items.values():
            if ei.edge.src == node_id or ei.edge.dst == node_id:
                ei.redraw()

    def highlight_node(self, node_id: str) -> None:
        for ni in self._node_items.values():
            ni._update_appearance()
        if node_id in self._node_items:
            self._node_items[node_id].setBrush(NODE_SELECTED_COLOR)

    def highlight_edge(self, edge_id: str) -> None:
        for eid, ei in self._edge_items.items():
            pen = ei.pen()
            pen.setColor(EDGE_SELECTED_COLOR if eid == edge_id else EDGE_COLOR)
            ei.setPen(pen)

    def clear_highlights(self) -> None:
        for ni in self._node_items.values():
            ni._update_appearance()
        for ei in self._edge_items.values():
            pen = ei.pen()
            pen.setColor(EDGE_COLOR)
            ei.setPen(pen)

    # ------------------------------------------------------------------
    # Edge drag protocol
    # ------------------------------------------------------------------

    def is_dragging_edge(self) -> bool:
        return self._dragging_edge

    def begin_edge_drag(self, src_item: NodeItem, scene_pos: QPointF) -> None:
        self._dragging_edge = True
        self._drag_src_item = src_item
        self._rubber_band = RubberBandEdge()
        self._rubber_band.update_path(
            QPointF(src_item.node.x, src_item.node.y), scene_pos
        )
        self._scene.addItem(self._rubber_band)

    def update_edge_drag(self, scene_pos: QPointF) -> None:
        if self._rubber_band and self._drag_src_item:
            self._rubber_band.update_path(
                QPointF(self._drag_src_item.node.x, self._drag_src_item.node.y),
                scene_pos,
            )

    def end_edge_drag(self, scene_pos: QPointF) -> None:
        # Remove rubber band
        if self._rubber_band:
            self._scene.removeItem(self._rubber_band)
            self._rubber_band = None

        if self._drag_src_item is None:
            self._dragging_edge = False
            return

        # Find the item under the cursor (excluding the src node and rubber band)
        items = self._scene.items(scene_pos)
        dst_item: Optional[NodeItem] = None
        for item in items:
            if isinstance(item, NodeItem) and item is not self._drag_src_item:
                dst_item = item
                break

        if dst_item is not None and dst_item is not self._drag_src_item:
            edge = Edge.new(
                src=self._drag_src_item.node.id,
                dst=dst_item.node.id,
            )
            self._graph.add_edge(edge)
            edge_item = self.add_edge_item(edge)
            edge_item.redraw()
            self.edge_created.emit(edge.id)

        self._dragging_edge = False
        self._drag_src_item = None

    # ------------------------------------------------------------------
    # Mouse events
    # ------------------------------------------------------------------

    def mouseDoubleClickEvent(self, event) -> None:
        scene_pos = self.mapToScene(event.pos())
        # Check nothing is under the cursor
        items = self._scene.items(scene_pos)
        for item in items:
            if isinstance(item, (NodeItem, EdgeItem)):
                super().mouseDoubleClickEvent(event)
                return

        # Create a new node at this position
        node = Node.new(scene_pos.x(), scene_pos.y())
        self._graph.add_node(node)
        item = self.add_node_item(node)
        self._scene.clearSelection()
        item.setSelected(True)
        self.node_created.emit(node.id)
        event.accept()

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.remove_selected()
        else:
            super().keyPressEvent(event)

    # Zoom with scroll wheel
    def wheelEvent(self, event) -> None:
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)


# ===========================================================================
# Drawing helpers
# ===========================================================================

def _sagitta_point(src: Node, dst: Node, edge: Edge, graph: Graph):
    """Return the midpoint of the arc (the sagitta point) as (x, y).

    For a circular arc the sagitta point lies on the perpendicular bisector of
    the chord, at distance R from the center, on the same side as the arc.
    When the center coincides with the chord midpoint (θ = π, semicircle) the
    direction is the perpendicular to the chord itself.
    """
    mx, my = (src.x + dst.x) / 2.0, (src.y + dst.y) / 2.0
    if edge.curvature <= 0.0:
        return (mx, my)
    center = edge.arc_center(graph)
    if center is None:
        return (mx, my)
    cx, cy = center
    r = edge.arc_radius(graph)
    dcx, dcy = mx - cx, my - cy
    dist = math.hypot(dcx, dcy)
    if dist < 1e-6:
        # Center == midpoint (semicircle): step perpendicularly from the chord.
        chord_x, chord_y = dst.x - src.x, dst.y - src.y
        chord_len = math.hypot(chord_x, chord_y)
        if chord_len < 1e-6:
            return (mx, my)
        # Perpendicular direction depends on arc_side.
        # For "left": center was offset in (-uy, ux); sagitta is the opposite: (uy, -ux).
        # For "right": center was offset in (uy, -ux); sagitta is the opposite: (-uy, ux).
        ux, uy = chord_x / chord_len, chord_y / chord_len
        if edge.arc_side == "left":
            px, py = uy, -ux
        else:
            px, py = -uy, ux
        return (cx + r * px, cy + r * py)
    return (cx + r * dcx / dist, cy + r * dcy / dist)

def _draw_straight(path: QPainterPath, src: Node, dst: Node) -> None:
    path.moveTo(src.x, src.y)
    path.lineTo(dst.x, dst.y)
    _add_arrowhead(path, src.x, src.y, dst.x, dst.y)


def _add_arrowhead(
    path: QPainterPath,
    sx: float, sy: float,
    dx: float, dy: float,
) -> None:
    chord = math.hypot(dx - sx, dy - sy)
    if chord < 1e-6:
        return
    ux, uy = (dx - sx) / chord, (dy - sy) / chord
    # Pull back from node border
    tip_x = dx - ux * NODE_RADIUS
    tip_y = dy - uy * NODE_RADIUS

    perp_x, perp_y = -uy, ux
    size = ARROW_SIZE
    path.moveTo(tip_x, tip_y)
    path.lineTo(
        tip_x - ux * size + perp_x * size * 0.4,
        tip_y - uy * size + perp_y * size * 0.4,
    )
    path.moveTo(tip_x, tip_y)
    path.lineTo(
        tip_x - ux * size - perp_x * size * 0.4,
        tip_y - uy * size - perp_y * size * 0.4,
    )


def _draw_arc(
    path: QPainterPath,
    src: Node,
    dst: Node,
    edge: Edge,
    graph: Graph,
) -> None:
    from PyQt6.QtCore import QRectF

    center = edge.arc_center(graph)
    if center is None:
        _draw_straight(path, src, dst)
        return

    cx, cy = center
    r = edge.arc_radius(graph)

    # Bounding rect of the circle
    rect = QRectF(cx - r, cy - r, 2 * r, 2 * r)

    # Angles from center to src and dst (Qt uses degrees, 0=right, CCW positive)
    src_angle = math.degrees(math.atan2(-(src.y - cy), src.x - cx))
    dst_angle = math.degrees(math.atan2(-(dst.y - cy), dst.x - cx))

    # Span: choose direction based on arc_side.
    # In Qt screen coords (y-down), the _arc_center for "left" places the center
    # *below* the chord, so the arc bows *above* it. arcTo with a negative span
    # sweeps CW, which is the short path passing through the top. "right" is the
    # mirror: center above, arc bows below, positive (CCW) span is the short path.
    span = dst_angle - src_angle
    if edge.arc_side == "left":
        # CW sweep (negative span) bows above/left
        if span >= 0:
            span -= 360
    else:
        # CCW sweep (positive span) bows below/right
        if span <= 0:
            span += 360

    path.arcMoveTo(rect, src_angle)
    path.arcTo(rect, src_angle, span)

    # Arrowhead at dst endpoint
    # Compute tangent at dst numerically
    tang = edge.tangent_at_dst(graph)
    tip_x = dst.x - tang[0] * NODE_RADIUS
    tip_y = dst.y - tang[1] * NODE_RADIUS
    ux, uy = tang
    perp_x, perp_y = -uy, ux
    size = ARROW_SIZE
    path.moveTo(tip_x, tip_y)
    path.lineTo(
        tip_x - ux * size + perp_x * size * 0.4,
        tip_y - uy * size + perp_y * size * 0.4,
    )
    path.moveTo(tip_x, tip_y)
    path.lineTo(
        tip_x - ux * size - perp_x * size * 0.4,
        tip_y - uy * size - perp_y * size * 0.4,
    )

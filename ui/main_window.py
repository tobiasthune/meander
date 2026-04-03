"""Main application window for meander."""
from __future__ import annotations

import math
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDockWidget,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QToolBar,
    QWidget,
)

from audio.player import AudioPlayer
from audio.traversal import Traverser
from graph.graph import Edge, Graph, Node
from ui.canvas import GraphCanvas


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("meander")
        self.resize(1200, 800)

        # ---- Data model ------------------------------------------------
        self._graph = Graph()
        self._player = AudioPlayer()
        self._traverser: Optional[Traverser] = None

        # ---- Canvas ----------------------------------------------------
        self._canvas = GraphCanvas(self._graph, self)
        self.setCentralWidget(self._canvas)

        # ---- Toolbar ---------------------------------------------------
        self._build_toolbar()

        # ---- Properties panel ------------------------------------------
        self._build_properties_dock()

        # ---- Connect canvas signals ------------------------------------
        self._canvas.edge_selected.connect(self._on_edge_selected)
        self._canvas.edge_changed.connect(self._on_edge_changed)
        self._canvas.node_selected.connect(self._on_node_selected)

        # ---- State ------------------------------------------------
        self._selected_edge_id: Optional[str] = None
        self._selected_node_id: Optional[str] = None

    # ==================================================================
    # Toolbar
    # ==================================================================

    def _build_toolbar(self) -> None:
        tb = QToolBar("Controls", self)
        tb.setMovable(False)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, tb)

        self._play_btn = QPushButton("▶  Play")
        self._play_btn.setToolTip("Traverse graph from the selected (or first) node")
        self._play_btn.clicked.connect(self._on_play)
        tb.addWidget(self._play_btn)

        self._stop_btn = QPushButton("⏹  Stop")
        self._stop_btn.setToolTip("Stop traversal")
        self._stop_btn.clicked.connect(self._on_stop)
        self._stop_btn.setEnabled(False)
        tb.addWidget(self._stop_btn)

    # ==================================================================
    # Properties dock
    # ==================================================================

    def _build_properties_dock(self) -> None:
        dock = QDockWidget("Properties", self)
        dock.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea)
        dock.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)

        container = QWidget()
        layout = QFormLayout(container)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self._prop_label = QLabel("Nothing selected")
        layout.addRow(self._prop_label)

        # Edge radius
        self._radius_spin = QDoubleSpinBox()
        self._radius_spin.setRange(MIN_ARC_RADIUS_UI, 5000.0)
        self._radius_spin.setSingleStep(10.0)
        self._radius_spin.setDecimals(1)
        self._radius_spin.setSuffix(" px")
        self._radius_spin.setToolTip("Arc radius in scene units (smaller = higher pitch)")
        self._radius_spin.valueChanged.connect(self._on_radius_changed)
        layout.addRow("Radius:", self._radius_spin)

        # Frequency display (read-only)
        self._freq_label = QLabel("—")
        layout.addRow("Frequency:", self._freq_label)

        # Length override (None = auto)
        self._length_spin = QDoubleSpinBox()
        self._length_spin.setRange(1.0, 10000.0)
        self._length_spin.setSingleStep(10.0)
        self._length_spin.setDecimals(1)
        self._length_spin.setSuffix(" px")
        self._length_spin.setToolTip("Arc length (controls duration). 0 = auto from geometry")
        self._length_spin.setSpecialValueText("auto")
        self._length_spin.setMinimum(0.0)
        self._length_spin.valueChanged.connect(self._on_length_changed)
        layout.addRow("Length:", self._length_spin)

        # Arc side toggle
        self._arc_side_btn = QPushButton("Bow: Left")
        self._arc_side_btn.setCheckable(True)
        self._arc_side_btn.setToolTip("Toggle which side the arc bows to")
        self._arc_side_btn.clicked.connect(self._on_arc_side_toggled)
        layout.addRow("", self._arc_side_btn)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addRow(spacer)

        self._set_properties_enabled(False)

        dock.setWidget(container)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)

    def _set_properties_enabled(self, enabled: bool) -> None:
        self._radius_spin.setEnabled(enabled)
        self._length_spin.setEnabled(enabled)
        self._arc_side_btn.setEnabled(enabled)

    # ==================================================================
    # Slot handlers
    # ==================================================================

    def _on_edge_selected(self, edge_id: str) -> None:
        self._selected_edge_id = edge_id
        self._selected_node_id = None
        edge = self._graph.edges.get(edge_id)
        if edge is None:
            return
        self._refresh_edge_props(edge)

    def _on_edge_changed(self, edge_id: str) -> None:
        if edge_id == self._selected_edge_id:
            edge = self._graph.edges.get(edge_id)
            if edge:
                self._refresh_edge_props(edge)

    def _refresh_edge_props(self, edge: Edge) -> None:
        self._prop_label.setText("Edge selected")
        self._set_properties_enabled(True)

        # Temporarily block signals to avoid feedback loops
        self._radius_spin.blockSignals(True)
        self._length_spin.blockSignals(True)
        self._arc_side_btn.blockSignals(True)

        if math.isinf(edge.radius):
            self._radius_spin.setValue(self._radius_spin.maximum())
            self._freq_label.setText("silent (straight)")
        else:
            self._radius_spin.setValue(edge.radius)
            from audio.synth import freq_from_radius
            freq = freq_from_radius(edge.radius)
            self._freq_label.setText(f"{freq:.1f} Hz")

        if edge._length_override is not None:
            self._length_spin.setValue(edge._length_override)
        else:
            self._length_spin.setValue(0.0)  # "auto"

        side = edge.arc_side
        self._arc_side_btn.setText(f"Bow: {'Left' if side == 'left' else 'Right'}")
        self._arc_side_btn.setChecked(side == "right")

        self._radius_spin.blockSignals(False)
        self._length_spin.blockSignals(False)
        self._arc_side_btn.blockSignals(False)

    def _on_node_selected(self, node_id: str) -> None:
        self._selected_node_id = node_id
        self._selected_edge_id = None
        self._prop_label.setText("Node selected")
        self._set_properties_enabled(False)
        self._freq_label.setText("—")

    def _on_radius_changed(self, value: float) -> None:
        if self._selected_edge_id is None:
            return
        edge = self._graph.edges.get(self._selected_edge_id)
        if edge is None:
            return
        if value >= self._radius_spin.maximum() - 1:
            edge.shape = "straight"
            edge.radius = float("inf")
            self._freq_label.setText("silent (straight)")
        else:
            edge.shape = "arc"
            edge.radius = value
            from audio.synth import freq_from_radius
            freq = freq_from_radius(value)
            self._freq_label.setText(f"{freq:.1f} Hz")
        # Redraw the edge item
        item = self._canvas._edge_items.get(self._selected_edge_id)
        if item:
            item.redraw()

    def _on_length_changed(self, value: float) -> None:
        if self._selected_edge_id is None:
            return
        edge = self._graph.edges.get(self._selected_edge_id)
        if edge is None:
            return
        edge.set_length(None if value == 0.0 else value)

    def _on_arc_side_toggled(self, checked: bool) -> None:
        if self._selected_edge_id is None:
            return
        edge = self._graph.edges.get(self._selected_edge_id)
        if edge is None:
            return
        edge.arc_side = "right" if checked else "left"
        self._arc_side_btn.setText(f"Bow: {'Right' if checked else 'Left'}")
        item = self._canvas._edge_items.get(self._selected_edge_id)
        if item:
            item.redraw()

    # ==================================================================
    # Playback
    # ==================================================================

    def _on_play(self) -> None:
        if self._traverser and self._traverser.isRunning():
            return

        # Find start node: selected node or first node
        start_id: Optional[str] = self._selected_node_id
        if start_id is None:
            node = self._graph.first_node()
            if node is None:
                return
            start_id = node.id

        self._traverser = Traverser(
            self._graph, self._player, start_id, parent=self
        )
        self._traverser.finished.connect(self._on_traversal_finished)
        self._traverser.node_entered.connect(self._canvas.highlight_node)
        self._traverser.edge_started.connect(self._canvas.highlight_edge)
        self._traverser.start()

        self._play_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)

    def _on_stop(self) -> None:
        if self._traverser:
            self._traverser.stop_traversal()

    def _on_traversal_finished(self) -> None:
        self._play_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)


MIN_ARC_RADIUS_UI = 30.0

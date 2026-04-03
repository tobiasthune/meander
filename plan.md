# Plan: Meander — Experimental Python Sound Editor

## Core Model

**Edges = sustained tones**
- Straight (infinite radius) → silent
- Circular arc → sustained tone; radius ↓ = frequency ↑ (f = k / r)
- Length → duration of the tone

**Nodes = percussive hits**
- Fired when traversal arrives at a node and departs on an outgoing edge
- Angle between incoming and outgoing edge → percussive frequency
- 180° (straight through) → silent; more acute angle → higher pitch

## File Structure

### graph/graph.py
- `Node(id, x, y)`
- `Edge(id, src_node_id, dst_node_id, shape: 'straight'|'arc', radius: float, length: float, arc_side: 'left'|'right')`
- `Graph`: nodes dict, edges dict, adjacency list; methods: `add_node`, `add_edge`, `outgoing_edges(node_id)`, `incoming_edge(node_id)` (for traversal)

### audio/synth.py
- `freq_from_radius(r) -> float`: f = TUNING_CONSTANT / r (e.g. TUNING_CONSTANT = 44000 so radius 100px → 440Hz)
- `freq_from_angle(angle_rad) -> float`: angle deviation from π; f = TUNING_CONSTANT * (π - angle) / π — clamped/scaled
- `generate_sustained(freq, duration_s, sample_rate=44100) -> np.ndarray`: sine wave with short fade-in/out envelope
- `generate_percussive(freq, sample_rate=44100) -> np.ndarray`: damped sinusoid (e.g. exp decay × sin)

### audio/player.py
- `AudioPlayer`: wraps sounddevice; `play(samples)` queues audio; `stop()`

### audio/traversal.py
- `Traverser(graph, player)`: 
  - `start(node_id)`: begins traversal from node
  - `_step()`: plays outgoing edge tone, schedules percussive hit at next node, follows to next node
  - Runs in a QThread to avoid blocking UI
  - Stops when no outgoing edges

### ui/canvas.py
- `GraphCanvas(QGraphicsView)`:
  - `NodeItem(QGraphicsEllipseItem)`: draggable node; double-click on canvas → `GraphCanvas.mouseDoubleClickEvent` creates new node
  - `EdgeItem(QGraphicsPathItem)`: draws straight line or circular arc via `QPainterPath`; has a draggable midpoint handle that adjusts `radius` and `arc_side`
  - Interaction: drag from NodeItem → rubber-band edge → on release over another NodeItem → `graph.add_edge()`
  - Selected edge → Properties panel updates

### ui/main_window.py
- `MainWindow(QMainWindow)`:
  - Central widget: `GraphCanvas`
  - Toolbar/panel: Play button (▶), Stop button, selected-edge properties (radius spinbox, length spinbox)
  - Play button picks selected node (or first node) and hands to `Traverser`

### main.py
- Creates QApplication, instantiates MainWindow, shows it

## Phase Breakdown

### Phase 1 — Graph data model
1. Implement `graph/graph.py` (Node, Edge, Graph classes)

### Phase 2 — Audio synthesis
2. Implement `audio/synth.py` (generate_sustained, generate_percussive, freq mappings)
3. Implement `audio/player.py` (sounddevice wrapper)

### Phase 3 — Traversal engine
4. Implement `audio/traversal.py` (Traverser, QThread-based)
5. Compute traversal angle: given incoming edge geometry and outgoing edge geometry at a node

### Phase 4 — UI canvas
6. Implement `ui/canvas.py` (NodeItem, EdgeItem, drag-to-create-edge, midpoint handle for radius)
7. Implement `ui/main_window.py` (window layout, toolbar, property panel)

### Phase 5 — Wiring
8. Connect canvas events → graph model updates
9. Connect Play button → Traverser
10. Update `main.py` entrypoint

## Decisions / Assumptions
- f = TUNING_CONSTANT / radius; default TUNING_CONSTANT ≈ 44000 (so 100px radius → 440Hz, A4)
- Percussive frequency: f_perc = PERC_MAX * (π - θ) / π; PERC_MAX ≈ 4000Hz
- Multiple outgoing edges: pick the first one added (simple for now)
- Arc direction (which side it bows): toggleable via dragging midpoint handle
- Length is computed as arc length = radius * angle_subtended, OR it can be overridden via the property panel
- No io/ module needed yet

## Further Considerations
1. Should the arc's end-to-end chord length equal `length`, or should arc length (arc_radius × subtended_angle) equal `length`? Recommend: arc length = length.
2. Should traversal loop (cycle detection) or stop at dead ends?

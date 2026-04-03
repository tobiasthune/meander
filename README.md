# meander
Music generation through paths. Curves and angles define sounds.

## What it is

Meander is an experimental sound editor where music is described as a directed graph. There are no notes in the traditional sense — the geometry of the graph *is* the composition.

- **Edges are sustained tones.** A circular arc edge plays a sine tone. The arc's radius determines pitch (smaller radius = higher frequency), and the arc length determines duration. A straight edge is silent.
- **Nodes are percussive hits.** When traversal arrives at a node, the angle between the incoming and outgoing edges determines the pitch of a short percussive strike. A straight-through angle (180°) is silent; a sharper turn produces a higher-pitched hit.

### Frequency mapping

| Parameter | Sound | Frequency formula |
|---|---|---|
| Arc radius | Sustained tone | `f = 44000 / radius` (radius 100 px → A4 = 440 Hz) |
| Turn angle θ | Percussive hit | `f = 4000 × (π − θ) / π` (straight = silent, acute = up to 4 kHz) |

## Running

```bash
# From the project directory
uv run main.py
# or
.venv/bin/python main.py
```

## How to use

### Building the graph

| Action | Result |
|---|---|
| Double-click on empty canvas | Create a new node |
| Drag from the **border** of a node to another node | Create a directed edge (starts straight/silent) |
| Drag the **red midpoint handle** on an edge | Bow the edge into an arc; radius and pitch update live |
| Click a node or edge | Select it |
| Delete / Backspace | Remove the selected node or edge |
| Scroll wheel | Zoom in / out |

### Properties panel (right side)

When an edge is selected:

- **Radius** — arc radius in scene units; drives the sustained tone pitch. Drag all the way up to make the edge silent/straight.
- **Frequency** — read-only display of the resulting pitch in Hz.
- **Length** — arc length in scene units; drives duration. Set to 0 for automatic (derived from geometry).
- **Bow** — toggle which side the arc curves to.

### Playback

1. Optionally click a node to select it as the start point (otherwise the first node added is used).
2. Press **▶ Play** — the traversal thread walks the graph, playing each edge's sustained tone and each node's percussive hit in sequence.
3. Press **⏹ Stop** to interrupt at any time.

Traversal follows the first outgoing edge at each node and stops at a dead end.

## Project structure

```
meander/
  main.py               — entry point
  graph/
    graph.py            — Node, Edge, Graph data model + arc geometry
  audio/
    synth.py            — sine tone and percussive synthesis; frequency mappings
    player.py           — sounddevice wrapper
    traversal.py        — QThread-based graph traversal with audio playback
  ui/
    canvas.py           — interactive QGraphicsView canvas
    main_window.py      — main window, toolbar, properties dock
```

## Dependencies

- [PyQt6](https://pypi.org/project/PyQt6/) — UI framework
- [NumPy](https://numpy.org/) — audio buffer generation
- [SciPy](https://scipy.org/) — available for future DSP use
- [sounddevice](https://python-sounddevice.readthedocs.io/) — audio output


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

A green node is fixed at the origin and always acts as the traversal start point. It cannot be deleted.

| Action | Result |
|---|---|
| Double-click on empty canvas | Create a new node |
| Drag from the **border** of a node to another node | Create a directed edge (starts straight/silent) |
| Drag the **red midpoint handle** on an edge | Bow the edge into an arc; radius and pitch update live |
| Click a node or edge | Select it |
| Delete / Backspace | Remove the selected node or edge (start node is protected) |
| Scroll wheel | Zoom in / out |

### Properties panel (right side)

When an edge is selected:

- **Radius** — arc radius in scene units; drives the sustained tone pitch. Drag all the way up to make the edge silent/straight.
- **Frequency** — read-only display of the resulting pitch in Hz.
- **Length** — arc length in scene units; drives duration. Set to 0 for automatic (derived from geometry).
- **Bow** — toggle which side the arc curves to.

### Playback

Press **▶ Play** to compile and play back the graph. Press **⏹ Stop** to interrupt.

Traversal always starts from the fixed start node, follows the first outgoing edge at each node, and stops at a dead end or if a cycle is detected. Canvas highlights stay in sync with the audio via a global clock.

#### How playback works internally

1. **Compile** — the graph is serialised to a plain dict snapshot, then `compile_traversal()` walks it, synthesising every edge tone and node hit into a single mixed NumPy buffer, and building a timestamped event list.
2. **Play** — `sd.play()` sends the buffer to the audio device in one call. A 16 ms `QTimer` compares elapsed wall-clock time (`time.perf_counter`) against the event list and fires canvas highlights as each event comes due.

This means the audio and the visual animation are compiled independently and driven by the same clock, with no inter-thread communication during playback.

## Project structure

```
meander/
  main.py                  — entry point
  graph/
    graph.py               — Node, Edge, Graph data model + arc geometry
    serializer.py          — to_dict / from_dict (plain Python dict schema)
  audio/
    synth.py               — sine tone and percussive synthesis; frequency mappings
    compiler.py            — compile_traversal() → CompiledPlayback (audio buffer + event list)
    player.py              — CompiledPlayer: sd.play() + QTimer event clock
  ui/
    canvas.py              — interactive QGraphicsView canvas
    main_window.py         — main window, toolbar, properties dock
```

### Graph dict schema

```python
{
    "start_node_id": str,
    "nodes":   { "<id>": {"id": str, "x": float, "y": float}, ... },
    "edges":   { "<id>": {"id": str, "src": str, "dst": str,
                           "shape": "straight"|"arc",
                           "radius": float,        # inf for straight
                           "arc_side": "left"|"right",
                           "length": float|None }, ... },
    "outgoing": { "<node_id>": ["<edge_id>", ...], ... },
}
```

## Dependencies

- [PyQt6](https://pypi.org/project/PyQt6/) — UI framework
- [NumPy](https://numpy.org/) — audio buffer generation
- [SciPy](https://scipy.org/) — available for future DSP use
- [sounddevice](https://python-sounddevice.readthedocs.io/) — audio output


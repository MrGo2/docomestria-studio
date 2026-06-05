# Architecture

High-level design notes for `docomestria-studio v0.1.0`. The viewer is a thin
Flask layer on top of `docomestria.Pipeline.stream()`.

## Goals

- Let non-technical users see what the pipeline does, step by step.
- Stay simple — no Redis, no SSE, no Node toolchain.
- Be self-contained for local demos: `python app.py` is enough.

## Strategy: pre-run, then play

The naive approach would be to stream pipeline steps over Server-Sent Events
as they happen. For a v0.1.0 demo that adds operational complexity (long-
lived connections, reconnect logic, head-of-line blocking). Instead:

1. On upload we save the PDF to a temp directory and create a session.
2. A daemon thread immediately starts iterating `pipe.stream(pdf_path)` and
   appends every `PipelineStep` to `session.steps`. Errors set
   `session.status = "error"` with the message.
3. The frontend polls `/api/session/<id>/status` every 500 ms.
4. Once `status == "ready"` the frontend fetches step 0 and the user advances
   manually via Next, Back, Auto, or Skip.

The trade-off: there's a brief "Procesando..." spinner before playback. The
benefit: the UI is a simple state machine, no streaming concerns.

## Module map

| Module | Responsibility |
|--------|----------------|
| `app.py` | Flask factory + route wiring |
| `config.py` | Read env vars into `StudioConfig` |
| `sessions.py` | Thread-safe in-memory `SessionStore` |
| `runner.py` | Background thread that drives `Pipeline.stream()` |
| `serializers.py` | `PipelineStep` -> JSON-safe dict for the frontend |
| `default_schema.py` | Lazy-built ES contract form schema |
| `templates/` | Jinja2 templates for the landing + studio pages |
| `static/studio.js` | Alpine.js component + pdf.js rendering + SVG overlay |

## State machine

```
session.status: processing -> ready
                       \-> error
```

`steps` is append-only. The frontend never re-orders or mutates them; it just
indexes into the array.

## Session lifecycle

Sessions are in-memory and survive only until the process restarts. A
`cleanup_old_sessions(max_age_minutes)` helper removes sessions whose
`last_accessed` is older than the cutoff (60 minutes by default). The viewer
doesn't yet schedule this — operators can call it from a maintenance hook.

## Frontend layout

```
+--------------------------+--------------------------+
|  pdf.js canvas + SVG     |  Step panel              |
|  overlay (engine-color)  |  - title + explanation   |
|                          |  - payload summary       |
|                          |  - controls              |
+--------------------------+--------------------------+
```

The SVG overlay uses absolute positioning over the canvas. Each `bbox` in the
current step is rendered as a `<rect>` with the engine's color (see
`ENGINE_COLORS` in `serializers.py`). Bbox coordinates are PDF points,
top-left origin — we multiply by the pdf.js viewport scale to map to pixels.

## Engine color legend

| Engine | Color |
|--------|-------|
| liteparse | blue |
| docling | orange |
| pdfplumber | green |
| fusion | purple |
| llm | pink |
| provenance | cyan |
| transform | yellow |
| system | gray |

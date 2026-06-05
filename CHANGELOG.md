# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.3] - 2026-06-05

### Changed
- PDF + bbox overlay rendering rebuilt around an SVG viewBox in raw PDF
  points. Canvas renders at fixed intrinsic 2x scale and is then sized to
  the panel via plain CSS (`width: 100%` on canvas + SVG inside a wrapper
  with the page's aspect-ratio). Result: full page is always visible, no
  horizontal scrollbar, and bbox overlays line up exactly with the PDF
  content regardless of viewport width or zoom.
- Removed the ResizeObserver that re-rendered on every container resize —
  cancellable render tasks were racing during initial layout and leaving the
  canvas blank. CSS scaling handles resize for free now.

## [0.2.2] - 2026-06-05

### Fixed
- PDF canvas now fits the panel width instead of being clipped to half the page.
  Scale is computed from the container width at render time, and the wrapper no
  longer scrolls horizontally.

## [0.2.1] - 2026-06-05

### Fixed
- PDF rendering no longer fails with "Cannot read private member #d" — `pdf.js`
  document and viewport objects are kept in closure variables instead of
  Alpine's reactive Proxy (private class fields cannot survive proxying).
- Step counter now shows the correct total for the active mode (Paso X de 9
  in deterministic, Paso X de 13 in AI). Was previously hardcoded to 13.
- Next button is no longer stuck disabled when only the first step has loaded.
  Bound now uses `stepsDone` instead of the locally cached `steps.length`.
- Canvas double-render race condition during Alpine double-init is avoided
  with an `initialized` guard and a cancellable `renderTask`.
- Requires `docomestria>=0.6.1` which also reports `total_steps` correctly
  from the server side.

## [0.2.0] - 2026-06-05

### Added
- Mode toggle on upload page: Determinista (no LLM, free, default) vs AI-asistido (OpenRouter)
- Deterministic mode is now the default — works without OPENROUTER_API_KEY
- Mode badge in studio header so users always know which path is running
- Engine color for new `pair_fields` step (teal #14b8a6)
- DEFAULT_SCHEMA now includes explicit `labels` for every field, optimized for the
  Spanish "DATOS PERSONALES DEL TITULAR" form layout

### Changed
- Upload endpoint accepts a `mode` field; rejects `mode=ai` only when no API key
- Setup-required banner no longer blocks the whole app; only blocks AI mode
- Requires `docomestria>=0.6.0` for the new deterministic Pipeline path
- `default_pipeline_factory` and `PipelineFactory` signature now take a mode argument

## [0.1.0] - 2026-06-05

### Added
- First release: Flask + htmx + Alpine + Tailwind interactive viewer
- Drag-and-drop PDF upload
- Step-by-step playback of docomestria `Pipeline.stream()` with Next/Auto/Skip controls
- Live PDF rendering via pdf.js with per-step SVG bbox overlays color-coded by engine
- Plain-language explanations in Spanish for non-technical users
- Cost and duration summary on completion
- OpenRouter provider via `google/gemini-2.5-flash-lite` by default
- Hardcoded ES contract form schema (will be configurable in v0.2.0)

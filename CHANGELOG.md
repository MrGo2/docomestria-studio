# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

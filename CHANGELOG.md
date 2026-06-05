# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

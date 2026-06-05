"""Wrap `docomestria.Pipeline.stream()` into a session-backed background run.

Two modes are supported:

- ``deterministic`` — builds a `Pipeline(llm=None)` which runs the schema-
  driven label pairing path. No API key, no network, no cost.
- ``ai`` — builds a `Pipeline(llm=OpenRouter(...))`. Requires an API key
  in the config.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

from .sessions import StudioSession

# Type alias for the pipeline factory injected by the app / tests.
# It receives the desired mode and returns a pipeline-like object.
Mode = Literal["deterministic", "ai"]
PipelineFactory = Callable[[Mode], Any]


def _build_pipeline(mode: Mode, api_key: str | None, model: str) -> Any:
    """Build a docomestria Pipeline for the requested mode.

    Lazy-imports so test runs that pass an explicit factory don't pull in
    docomestria's heavy engine dependencies.
    """
    from docomestria import Pipeline

    from .default_schema import build_default_schema

    schema = build_default_schema()

    if mode == "deterministic":
        return Pipeline(schema=schema, llm=None, cache_dir=None)
    if mode == "ai":
        if not api_key:
            raise RuntimeError(
                "OPENROUTER_API_KEY is required for AI-assisted mode."
            )
        from docomestria.pipeline.providers import OpenRouter

        llm = OpenRouter(api_key=api_key, model=model)
        return Pipeline(schema=schema, llm=llm, cache_dir=None)
    raise ValueError(f"Unknown mode: {mode}")


def default_pipeline_factory(api_key: str | None, model: str) -> PipelineFactory:
    """Return a mode-aware factory bound to the given API key and model."""

    def factory(mode: Mode) -> Any:
        return _build_pipeline(mode, api_key, model)

    return factory


def run_pipeline_into_session(
    session: StudioSession,
    pdf_path: Path,
    pipeline_factory: PipelineFactory,
) -> None:
    """Run `pipe.stream(pdf_path)` and append every step to the session.

    Marks the session `ready` when the stream completes, or `error` if any
    exception is raised. Designed to be called from a background thread.
    """
    try:
        pipe = pipeline_factory(session.mode)
        for step in pipe.stream(pdf_path):
            session.steps.append(step)
        session.status = "ready"
    except Exception as exc:  # noqa: BLE001 - we surface the error to the UI
        session.error = f"{type(exc).__name__}: {exc}"
        session.status = "error"


def start_background_run(
    session: StudioSession,
    pipeline_factory: PipelineFactory,
) -> threading.Thread:
    """Spawn a daemon thread that runs the pipeline into the session."""
    thread = threading.Thread(
        target=run_pipeline_into_session,
        args=(session, session.pdf_path, pipeline_factory),
        daemon=True,
        name=f"studio-pipeline-{session.id[:8]}",
    )
    thread.start()
    return thread


__all__ = [
    "Mode",
    "PipelineFactory",
    "default_pipeline_factory",
    "run_pipeline_into_session",
    "start_background_run",
]

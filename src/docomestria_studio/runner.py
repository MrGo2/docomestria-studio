"""Wrap `docomestria.Pipeline.stream()` into a session-backed background run."""

from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .sessions import StudioSession

# Type alias for the pipeline factory injected by the app / tests.
PipelineFactory = Callable[[], Any]


def _default_pipeline_factory(api_key: str | None, model: str) -> Any:
    """Build the default OpenRouter-backed pipeline.

    Lazy-imports so test runs that pass an explicit factory don't pull in
    docomestria's heavy engine dependencies.
    """
    from docomestria import Pipeline
    from docomestria.pipeline.providers import OpenRouter

    from .default_schema import build_default_schema

    if not api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is required to build the default pipeline."
        )
    llm = OpenRouter(api_key=api_key, model=model)
    return Pipeline(schema=build_default_schema(), llm=llm, cache_dir=None)


def default_pipeline_factory(api_key: str | None, model: str) -> PipelineFactory:
    """Return a zero-arg factory bound to the given API key and model."""

    def factory() -> Any:
        return _default_pipeline_factory(api_key, model)

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
        pipe = pipeline_factory()
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
    "PipelineFactory",
    "default_pipeline_factory",
    "run_pipeline_into_session",
    "start_background_run",
]

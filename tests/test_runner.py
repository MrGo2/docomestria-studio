"""Tests for the background pipeline runner."""

from __future__ import annotations

import time
from pathlib import Path

from docomestria_studio.runner import run_pipeline_into_session, start_background_run
from docomestria_studio.sessions import SessionStore

from .conftest import fake_pipeline_factory


def _make_session(tmp_path: Path):
    store = SessionStore()
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%fake\n")
    return store, store.create(pdf)


def test_run_captures_all_steps(tmp_path):
    _, session = _make_session(tmp_path)
    run_pipeline_into_session(session, session.pdf_path, fake_pipeline_factory())
    assert session.status == "ready"
    assert len(session.steps) == 3
    assert session.steps[0].name == "start"
    assert session.steps[-1].is_terminal


def test_run_marks_error_when_pipeline_raises(tmp_path):
    _, session = _make_session(tmp_path)
    run_pipeline_into_session(
        session,
        session.pdf_path,
        fake_pipeline_factory(raise_in_stream=True),
    )
    assert session.status == "error"
    assert "boom" in (session.error or "")


def test_status_transitions_via_background_thread(tmp_path):
    _, session = _make_session(tmp_path)
    factory = fake_pipeline_factory(delay=0.05)
    thread = start_background_run(session, factory)
    # Initially the session should still be processing (steps may already be 1+).
    assert session.status == "processing"
    thread.join(timeout=3.0)
    assert session.status == "ready"
    assert len(session.steps) == 3


def test_runner_with_real_step_dataclass_works(tmp_path):
    """Sanity check: the runner doesn't care about the step class, only its
    attributes — so using docomestria's real `PipelineStep` is fine too."""
    from docomestria.pipeline.step import PipelineStep

    _, session = _make_session(tmp_path)

    real_step = PipelineStep(
        name="start",
        title="Inicio",
        explanation="OK",
        engine="system",
        step_index=0,
        total_steps=1,
        elapsed_ms=1,
        cumulative_ms=1,
    )

    class _RealStepPipeline:
        def stream(self, _path):
            yield real_step

    def factory():
        return _RealStepPipeline()

    run_pipeline_into_session(session, session.pdf_path, factory)
    assert session.status == "ready"
    assert session.steps[0].name == "start"


def test_session_store_basics(tmp_path):
    store, session = _make_session(tmp_path)
    assert store.get(session.id) is session
    assert store.delete(session.id) is True
    assert store.get(session.id) is None
    assert store.delete(session.id) is False


def test_cleanup_old_sessions(tmp_path):
    store, session = _make_session(tmp_path)
    session.last_accessed = time.time() - 3600 * 2  # 2 hours ago
    removed = store.cleanup_old_sessions(max_age_minutes=60)
    assert removed == 1
    assert store.get(session.id) is None

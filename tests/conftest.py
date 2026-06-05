"""Shared fixtures for docomestria-studio tests.

We mock the pipeline so tests are fast and offline: no real LLM, no real
extraction, no torch download.
"""

from __future__ import annotations

import io
import time
from pathlib import Path

import pytest

from docomestria_studio.app import create_app
from docomestria_studio.config import StudioConfig


def _make_pdf_bytes() -> bytes:
    """Generate a tiny one-page PDF in memory."""
    try:
        from reportlab.pdfgen import canvas
    except ImportError:  # pragma: no cover
        pytest.skip("reportlab is required for the PDF fixture")
    buf = io.BytesIO()
    pdf = canvas.Canvas(buf)
    pdf.drawString(72, 720, "docomestria-studio test PDF")
    pdf.drawString(72, 700, "Carlos Lorenzo - 12345678Z")
    pdf.showPage()
    pdf.save()
    return buf.getvalue()


@pytest.fixture
def pdf_bytes() -> bytes:
    return _make_pdf_bytes()


class _FakeStep:
    """Stand-in for `docomestria.pipeline.step.PipelineStep`.

    We don't subclass the real dataclass because we want to keep the test
    surface small and not depend on its frozen field set.
    """

    def __init__(
        self,
        *,
        name: str,
        title: str,
        explanation: str,
        engine: str,
        step_index: int,
        total_steps: int,
        elapsed_ms: int = 1,
        cumulative_ms: int = 1,
        bboxes: tuple = (),
        payload: dict | None = None,
        is_terminal: bool = False,
        is_error: bool = False,
        error_message: str | None = None,
    ) -> None:
        self.name = name
        self.title = title
        self.explanation = explanation
        self.engine = engine
        self.step_index = step_index
        self.total_steps = total_steps
        self.elapsed_ms = elapsed_ms
        self.cumulative_ms = cumulative_ms
        self.bboxes = bboxes
        self.payload = payload or {}
        self.is_terminal = is_terminal
        self.is_error = is_error
        self.error_message = error_message

    @property
    def progress(self) -> float:
        if self.total_steps <= 0:
            return 0.0
        return self.step_index / self.total_steps


class _FakePipeline:
    """A pipeline that yields a deterministic sequence of fake steps."""

    def __init__(self, *, raise_in_stream: bool = False, delay: float = 0.0) -> None:
        self.raise_in_stream = raise_in_stream
        self.delay = delay

    def stream(self, pdf_path):  # noqa: ARG002 - signature parity with real pipeline
        if self.raise_in_stream:
            raise RuntimeError("boom")
        steps = [
            _FakeStep(
                name="start",
                title="Inicio",
                explanation="PDF recibido.",
                engine="system",
                step_index=0,
                total_steps=3,
            ),
            _FakeStep(
                name="extract_liteparse",
                title="Extracción texto",
                explanation="LiteParse extrae palabras.",
                engine="liteparse",
                step_index=1,
                total_steps=3,
                bboxes=(_FakeBBox(10, 10, 100, 12),),
                payload={"items_count": 42},
            ),
            _FakeStep(
                name="complete",
                title="Listo",
                explanation="Extracción completada.",
                engine="system",
                step_index=2,
                total_steps=3,
                is_terminal=True,
                payload={"result": _FakeResult()},
            ),
        ]
        for step in steps:
            if self.delay:
                time.sleep(self.delay)
            yield step


class _FakeBBox:
    def __init__(self, x, y, w, h):
        self.x = float(x)
        self.y = float(y)
        self.w = float(w)
        self.h = float(h)


class _FakeTypedValue:
    def __init__(self, *, field, raw, normalized, confidence, transform_used):
        self.field = field
        self.raw = raw
        self.normalized = normalized
        self.confidence = confidence
        self.transform_used = transform_used
        self.page = 1
        self.issues = ()
        self.ok = True


class _FakeCost:
    tokens_in = 100
    tokens_out = 50
    usd = 0.0001
    model_used = "test/model"


class _FakeResult:
    typed_fields = {
        "datos_titular.nif": _FakeTypedValue(
            field="datos_titular.nif",
            raw="12345678Z",
            normalized="12345678Z",
            confidence=0.95,
            transform_used="nif_es",
        ),
    }
    issues = ()
    cost = _FakeCost()
    duration_ms = 123
    llm_calls = 1
    cache_hit = False


def fake_pipeline_factory(*, raise_in_stream: bool = False, delay: float = 0.0):
    def factory():
        return _FakePipeline(raise_in_stream=raise_in_stream, delay=delay)

    return factory


@pytest.fixture
def fake_factory():
    return fake_pipeline_factory()


@pytest.fixture
def fake_factory_error():
    return fake_pipeline_factory(raise_in_stream=True)


@pytest.fixture
def test_config(tmp_path: Path) -> StudioConfig:
    return StudioConfig(
        openrouter_api_key="test-key",
        openrouter_model="google/gemini-2.5-flash-lite",
        upload_max_mb=5,
        host="127.0.0.1",
        port=5050,
        debug=False,
        session_max_age_minutes=60,
    )


@pytest.fixture
def app(test_config, fake_factory):
    app = create_app(test_config, pipeline_factory=fake_factory)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def fake_step_factory():
    """Public fixture so other tests can build PipelineStep-like objects."""
    return _FakeStep


@pytest.fixture
def fake_bbox_factory():
    return _FakeBBox


@pytest.fixture
def fake_result_factory():
    return _FakeResult

"""Tests for the PipelineStep serializer."""

from __future__ import annotations

import json

from docomestria_studio.serializers import (
    ENGINE_COLORS,
    bbox_to_dict,
    serialize_step,
)


def test_bbox_to_dict_from_object(fake_bbox_factory):
    bbox = fake_bbox_factory(10, 20, 30, 40)
    result = bbox_to_dict(bbox, page=2, label="header")
    assert result == {
        "x": 10.0,
        "y": 20.0,
        "w": 30.0,
        "h": 40.0,
        "page": 2,
        "label": "header",
    }


def test_bbox_to_dict_from_tuple():
    result = bbox_to_dict((1, 2, 3, 4))
    assert result["x"] == 1.0
    assert result["w"] == 3.0


def test_engine_colors_cover_documented_engines():
    expected = {
        "liteparse",
        "docling",
        "pdfplumber",
        "fusion",
        "llm",
        "provenance",
        "transform",
        "system",
    }
    assert expected.issubset(set(ENGINE_COLORS.keys()))
    # All values must be valid hex colors.
    for color in ENGINE_COLORS.values():
        assert color.startswith("#")
        assert len(color) == 7


def test_serialize_step_basic(fake_step_factory, fake_bbox_factory):
    step = fake_step_factory(
        name="extract_liteparse",
        title="Extracción texto",
        explanation="LiteParse extrae palabras.",
        engine="liteparse",
        step_index=2,
        total_steps=13,
        elapsed_ms=247,
        cumulative_ms=412,
        bboxes=(fake_bbox_factory(100, 50, 80, 12),),
        payload={"items_count": 159, "sample_texts": ["DATOS", "Apellidos:"]},
    )
    data = serialize_step(step)
    # JSON-serializable round-trip.
    json.dumps(data)
    assert data["name"] == "extract_liteparse"
    assert data["engine_color"] == "#3b82f6"
    assert data["bboxes"][0]["x"] == 100.0
    assert data["payload"]["items_count"] == 159
    assert data["progress"] == 2 / 13
    assert data["final"] is None


def test_serialize_step_drops_non_json_payload_safely(fake_step_factory):
    class _Weird:
        def __repr__(self) -> str:
            return "<weird>"

    step = fake_step_factory(
        name="fuse",
        title="Fusión",
        explanation="",
        engine="fusion",
        step_index=4,
        total_steps=13,
        payload={"weird": _Weird()},
    )
    data = serialize_step(step)
    json.dumps(data)  # must not raise
    assert data["payload"]["weird"] == "<weird>"


def test_serialize_terminal_step_includes_final(
    fake_step_factory, fake_result_factory
):
    step = fake_step_factory(
        name="complete",
        title="Listo",
        explanation="",
        engine="system",
        step_index=12,
        total_steps=13,
        is_terminal=True,
        payload={"result": fake_result_factory()},
    )
    data = serialize_step(step)
    json.dumps(data)
    assert data["final"] is not None
    assert data["final"]["cost"]["usd"] == 0.0001
    assert data["final"]["typed_fields"][0]["field"] == "datos_titular.nif"
    assert data["final"]["typed_fields"][0]["normalized"] == "12345678Z"
    assert data["final"]["duration_ms"] == 123


def test_serialize_step_unknown_engine_falls_back_to_system(fake_step_factory):
    step = fake_step_factory(
        name="weird",
        title="?",
        explanation="",
        engine="not-a-real-engine",
        step_index=0,
        total_steps=1,
    )
    data = serialize_step(step)
    assert data["engine_color"] == ENGINE_COLORS["system"]

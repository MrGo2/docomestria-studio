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
        "pairing",
    }
    assert expected.issubset(set(ENGINE_COLORS.keys()))
    # All values must be valid hex colors.
    for color in ENGINE_COLORS.values():
        assert color.startswith("#")
        assert len(color) == 7


def test_pairing_engine_color_is_teal():
    assert ENGINE_COLORS["pairing"] == "#14b8a6"


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


# ============================================================================ details (v0.2.5)


def test_details_text_items_for_extract_liteparse(fake_step_factory):
    items = [
        {"text": "DATOS", "font": "Helvetica-Bold", "size": 12.0, "page": 1,
         "bbox": [10, 20, 40, 12]},
        {"text": "Apellidos", "font": "Helvetica", "size": 10.0, "page": 1,
         "bbox": [10, 40, 60, 12]},
    ]
    step = fake_step_factory(
        name="extract_liteparse",
        title="t",
        explanation="",
        engine="liteparse",
        step_index=1,
        total_steps=9,
        payload={"items_count": 2, "_text_items": items},
    )
    data = serialize_step(step)
    assert data["details"] is not None
    assert data["details"]["kind"] == "text_items"
    assert data["details"]["total"] == 2
    assert data["details"]["rows"][0]["text"] == "DATOS"
    assert data["details"]["rows"][0]["font"] == "Helvetica-Bold"
    # _text_items should be stripped from the user-visible payload summary.
    assert "_text_items" not in data["payload"]
    assert data["payload"]["items_count"] == 2


def test_details_blocks_for_extract_docling(fake_step_factory):
    blocks = [
        {"label": "section_header", "level": 1, "layer": "body", "page": 1,
         "bbox": [5, 5, 200, 20], "text": "DATOS PERSONALES"},
        {"label": "table", "level": None, "layer": "body", "page": 1,
         "bbox": [10, 50, 300, 200], "text": ""},
    ]
    step = fake_step_factory(
        name="extract_docling",
        title="t",
        explanation="",
        engine="docling",
        step_index=1,
        total_steps=9,
        payload={"_blocks": blocks},
    )
    data = serialize_step(step)
    assert data["details"]["kind"] == "blocks"
    assert data["details"]["rows"][0]["label"] == "section_header"
    assert data["details"]["rows"][0]["summary"] == "DATOS PERSONALES"
    assert data["details"]["rows"][1]["label"] == "table"


def test_details_visual_rects_for_extract_pdfplumber(fake_step_factory):
    rects = [
        {"rect_id": "rect_0", "rect_type": "table", "is_filled": False,
         "page": 1, "bbox": [10, 10, 100, 100], "table_grid": "8 rows x 3 cols"},
        {"rect_id": "rect_1", "rect_type": "checkbox", "is_filled": True,
         "page": 1, "bbox": [50, 50, 8, 8], "table_grid": None},
    ]
    step = fake_step_factory(
        name="extract_pdfplumber",
        title="t",
        explanation="",
        engine="pdfplumber",
        step_index=1,
        total_steps=9,
        payload={"_rects": rects},
    )
    data = serialize_step(step)
    assert data["details"]["kind"] == "visual_rects"
    assert data["details"]["rows"][0]["rect_type"] == "table"
    assert data["details"]["rows"][0]["table_grid"] == "8 rows x 3 cols"
    assert data["details"]["rows"][1]["rect_type"] == "checkbox"
    assert data["details"]["rows"][1]["is_filled"] is True


def test_details_pairs_for_pair_fields(fake_step_factory):
    pairs = [
        {"field": "nif", "label_searched": ["NIF", "DNI"], "label_found": "NIF",
         "value_raw": "51789286W", "matched": True, "page": 1},
        {"field": "email", "label_searched": ["Email"], "label_found": None,
         "value_raw": None, "matched": False, "page": None},
    ]
    step = fake_step_factory(
        name="pair_fields",
        title="t",
        explanation="",
        engine="pairing",
        step_index=4,
        total_steps=7,
        payload={"paired_count": 1, "_pairs": pairs},
    )
    data = serialize_step(step)
    assert data["details"]["kind"] == "pairs"
    assert data["details"]["total"] == 2
    assert data["details"]["matched_count"] == 1
    assert data["details"]["rows"][0]["matched"] is True
    assert data["details"]["rows"][0]["value_raw"] == "51789286W"
    assert "_pairs" not in data["payload"]


def test_details_typed_fields_for_apply_schema(fake_step_factory, fake_bbox_factory):
    class _TV:
        def __init__(self, raw, normalized, transform, ok):
            self.raw = raw
            self.normalized = normalized
            self.transform_used = transform
            self.ok = ok
            self.issues = ()

    typed = {
        "nif": _TV("51789286W", "51789286W", "nif_es", True),
        "fecha": _TV("06 de Diciembre", "2026-12-06", "date_es_long", True),
    }
    step = fake_step_factory(
        name="apply_schema",
        title="t",
        explanation="",
        engine="transform",
        step_index=5,
        total_steps=7,
    )
    step.typed_fields = typed
    data = serialize_step(step)
    assert data["details"]["kind"] == "typed_fields"
    assert data["details"]["total"] == 2
    assert data["details"]["ok_count"] == 2
    assert data["details"]["rows"][0]["field"] == "nif"
    assert data["details"]["rows"][0]["normalized"] == "51789286W"


def test_details_fused_items_for_fuse(fake_step_factory):
    class _Item:
        def __init__(self, text, section, label, box_id, page):
            self.text = text
            self.section_title = section
            self.docling_label = label
            self.enclosing_box_id = box_id
            self.table_id = None
            self.page = page

    class _Fusion:
        items = (
            _Item("HELLO", "DATOS", "text", "box-1", 1),
            _Item("WORLD", None, "text", None, 1),
        )
        coverage = 1.0
        matched_to_box = 1
        matched_to_docling = 2

    step = fake_step_factory(
        name="fuse",
        title="t",
        explanation="",
        engine="fusion",
        step_index=3,
        total_steps=7,
        payload={"items_count": 2},
    )
    step.fusion = _Fusion()
    data = serialize_step(step)
    assert data["details"]["kind"] == "fused_items"
    assert data["details"]["total"] == 2
    assert data["details"]["rows"][0]["text"] == "HELLO"
    assert data["details"]["stats"]["coverage"] == 1.0


def test_bbox_labels_populated_for_docling(fake_step_factory, fake_bbox_factory):
    blocks = [
        {"label": "section_header", "level": 1, "layer": "body", "page": 1,
         "bbox": [5, 5, 200, 20], "text": "DATOS"},
        {"label": "table", "level": None, "layer": "body", "page": 1,
         "bbox": [10, 50, 300, 200], "text": ""},
    ]
    bboxes = (
        fake_bbox_factory(5, 5, 200, 20),
        fake_bbox_factory(10, 50, 300, 200),
    )
    step = fake_step_factory(
        name="extract_docling",
        title="t",
        explanation="",
        engine="docling",
        step_index=1,
        total_steps=9,
        bboxes=bboxes,
        payload={"_blocks": blocks},
    )
    data = serialize_step(step)
    assert data["bboxes"][0]["label"] == "section_header"
    assert data["bboxes"][1]["label"] == "table"


def test_bbox_labels_populated_for_pdfplumber(fake_step_factory, fake_bbox_factory):
    rects = [
        {"rect_id": "r0", "rect_type": "table", "is_filled": False, "page": 1,
         "bbox": [10, 10, 100, 100], "table_grid": "8 rows x 3 cols"},
        {"rect_id": "r1", "rect_type": "checkbox", "is_filled": True, "page": 1,
         "bbox": [50, 50, 8, 8], "table_grid": None},
    ]
    bboxes = (
        fake_bbox_factory(10, 10, 100, 100),
        fake_bbox_factory(50, 50, 8, 8),
    )
    step = fake_step_factory(
        name="extract_pdfplumber",
        title="t",
        explanation="",
        engine="pdfplumber",
        step_index=1,
        total_steps=9,
        bboxes=bboxes,
        payload={"_rects": rects},
    )
    data = serialize_step(step)
    assert data["bboxes"][0]["label"] == "table"
    assert data["bboxes"][1]["label"] == "checkbox"


def test_details_none_for_steps_without_engine_data(fake_step_factory):
    step = fake_step_factory(
        name="start",
        title="t",
        explanation="",
        engine="system",
        step_index=0,
        total_steps=7,
    )
    data = serialize_step(step)
    assert data["details"] is None

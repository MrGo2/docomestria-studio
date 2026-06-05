"""Convert PipelineStep / FusedItem / BBox into JSON-safe dicts for the UI."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from docomestria.pipeline.step import PipelineStep


# Engine -> color mapping consumed by the SVG overlay.
ENGINE_COLORS: dict[str, str] = {
    "liteparse": "#3b82f6",
    "docling": "#f97316",
    "pdfplumber": "#10b981",
    "fusion": "#8b5cf6",
    "llm": "#ec4899",
    "provenance": "#06b6d4",
    "transform": "#eab308",
    "system": "#6b7280",
    "pairing": "#14b8a6",
}

# Max rows shown per kind in the step detail panel; full count is preserved
# in `details.total` so the UI can show "showing N/M".
DETAILS_PREVIEW_LIMIT = 25


def bbox_to_dict(bbox: Any, page: int = 1, label: str = "") -> dict[str, Any]:
    """Serialize a BBox-like object to a JSON-safe dict.

    Accepts both `docomestria.models.BBox` instances and 4-tuples
    `(x, y, w, h)` to remain robust against upstream API drift.
    """
    if hasattr(bbox, "x"):
        return {
            "x": float(bbox.x),
            "y": float(bbox.y),
            "w": float(bbox.w),
            "h": float(bbox.h),
            "page": page,
            "label": label,
        }
    if isinstance(bbox, (tuple, list)) and len(bbox) == 4:
        x, y, w, h = bbox
        return {
            "x": float(x),
            "y": float(y),
            "w": float(w),
            "h": float(h),
            "page": page,
            "label": label,
        }
    raise TypeError(f"Cannot serialize bbox: {bbox!r}")


def _serialize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a JSON-safe view of a step payload — drops non-serializable refs.

    Keys starting with `_` are internal-only (consumed by `_build_details`)
    and are stripped here so they don't double up in the user-visible payload
    summary.
    """
    safe: dict[str, Any] = {}
    for key, value in payload.items():
        # The `result` field holds an ExtractionResult; we surface its summary
        # separately in `final`. Skip the raw object here to keep payload light.
        if key == "result":
            continue
        if isinstance(key, str) and key.startswith("_"):
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            safe[key] = value
        elif isinstance(value, (list, tuple)):
            safe[key] = [_serialize_scalar(v) for v in value]
        elif isinstance(value, dict):
            safe[key] = {k: _serialize_scalar(v) for k, v in value.items()}
        else:
            safe[key] = repr(value)
    return safe


def _serialize_scalar(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return repr(value)


def _serialize_final(step: PipelineStep) -> dict[str, Any] | None:
    """Surface terminal-step state (cost, typed_fields, issues) as a dict."""
    if not step.is_terminal:
        return None
    payload = step.payload or {}
    result = payload.get("result")
    if result is None:
        return None
    typed_fields = []
    raw_typed = getattr(result, "typed_fields", None) or {}
    for field_name, tv in raw_typed.items():
        typed_fields.append(
            {
                "field": field_name,
                "raw": getattr(tv, "raw", ""),
                "normalized": str(getattr(tv, "normalized", "")),
                "confidence": float(getattr(tv, "confidence", 0.0) or 0.0),
                "transform": getattr(tv, "transform_used", ""),
                "ok": bool(getattr(tv, "ok", False)),
                "page": getattr(tv, "page", None),
                "issues": list(getattr(tv, "issues", ()) or ()),
            }
        )
    issues = []
    for issue in getattr(result, "issues", ()) or ():
        issues.append(
            {
                "field": getattr(issue, "field_name", ""),
                "value": getattr(issue, "value", ""),
                "type": getattr(issue, "issue_type", ""),
                "severity": getattr(issue, "severity", ""),
                "detail": getattr(issue, "detail", ""),
            }
        )
    cost = getattr(result, "cost", None)
    cost_dict = None
    if cost is not None:
        cost_dict = {
            "tokens_in": int(getattr(cost, "tokens_in", 0) or 0),
            "tokens_out": int(getattr(cost, "tokens_out", 0) or 0),
            "usd": float(getattr(cost, "usd", 0.0) or 0.0),
            "model": getattr(cost, "model_used", ""),
        }
    return {
        "typed_fields": typed_fields,
        "issues": issues,
        "cost": cost_dict,
        "duration_ms": int(getattr(result, "duration_ms", 0) or 0),
        "llm_calls": int(getattr(result, "llm_calls", 0) or 0),
        "cache_hit": bool(getattr(result, "cache_hit", False)),
    }


def serialize_step(step: PipelineStep) -> dict[str, Any]:
    """Serialize one PipelineStep into the dict shape the frontend expects."""
    details = _build_details(step)
    # Per-bbox label hints — keyed by index when the engine knows what each
    # bbox represents (e.g. Docling labels). Falls back to the empty string
    # to keep older callers working.
    bbox_labels = _bbox_labels_from_details(details)
    bboxes = []
    for idx, bbox in enumerate(step.bboxes or ()):
        try:
            bboxes.append(
                bbox_to_dict(bbox, page=1, label=bbox_labels.get(idx, ""))
            )
        except TypeError:
            continue
    return {
        "name": step.name,
        "title": step.title,
        "explanation": step.explanation,
        "engine": step.engine,
        "step_index": step.step_index,
        "total_steps": step.total_steps,
        "progress": step.progress,
        "elapsed_ms": step.elapsed_ms,
        "cumulative_ms": step.cumulative_ms,
        "is_terminal": step.is_terminal,
        "is_error": step.is_error,
        "error_message": step.error_message,
        "engine_color": ENGINE_COLORS.get(step.engine, ENGINE_COLORS["system"]),
        "bboxes": bboxes,
        "payload": _serialize_payload(dict(step.payload or {})),
        "details": details,
        "final": _serialize_final(step),
    }


# ============================================================================ details
# Each branch returns a JSON-safe `{kind, rows, total, ...}` dict, or None.


def _build_details(step: PipelineStep) -> dict[str, Any] | None:
    name = step.name
    payload = dict(step.payload or {})
    if name == "extract_liteparse":
        return _details_text_items(payload.get("_text_items") or [])
    if name == "extract_docling":
        return _details_blocks(payload.get("_blocks") or [])
    if name == "extract_pdfplumber":
        return _details_visual_rects(payload.get("_rects") or [])
    if name == "fuse":
        return _details_fused_items(step)
    if name == "pair_fields":
        return _details_pairs(payload.get("_pairs") or [])
    if name == "apply_schema":
        return _details_typed_fields(step)
    return None


def _details_text_items(items: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for it in items[:DETAILS_PREVIEW_LIMIT]:
        rows.append(
            {
                "text": str(it.get("text", "")),
                "font": it.get("font"),
                "size": it.get("size"),
                "page": int(it.get("page", 1) or 1),
                "bbox": list(it.get("bbox") or [0, 0, 0, 0]),
            }
        )
    return {"kind": "text_items", "rows": rows, "total": len(items)}


def _details_blocks(blocks: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for b in blocks[:DETAILS_PREVIEW_LIMIT]:
        rows.append(
            {
                "label": str(b.get("label", "") or ""),
                "level": b.get("level"),
                "layer": b.get("layer", "body") or "body",
                "page": int(b.get("page", 1) or 1),
                "bbox": list(b.get("bbox") or [0, 0, 0, 0]),
                "summary": _block_summary(b),
            }
        )
    return {"kind": "blocks", "rows": rows, "total": len(blocks)}


def _block_summary(block: dict[str, Any]) -> str:
    text = (block.get("text") or "").strip()
    if text:
        return text[:80]
    label = block.get("label") or "block"
    bbox = block.get("bbox") or [0, 0, 0, 0]
    if label == "picture":
        return f"image {bbox[2]:.0f}x{bbox[3]:.0f}pt"
    if label == "table":
        return "table"
    return str(label)


def _details_visual_rects(rects: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for r in rects[:DETAILS_PREVIEW_LIMIT]:
        rows.append(
            {
                "rect_id": str(r.get("rect_id", "") or ""),
                "rect_type": str(r.get("rect_type", "box") or "box"),
                "is_filled": bool(r.get("is_filled", False)),
                "page": int(r.get("page", 1) or 1),
                "bbox": list(r.get("bbox") or [0, 0, 0, 0]),
                "table_grid": r.get("table_grid"),
                "summary": _rect_summary(r),
            }
        )
    return {"kind": "visual_rects", "rows": rows, "total": len(rects)}


def _rect_summary(rect: dict[str, Any]) -> str:
    rtype = rect.get("rect_type", "box")
    grid = rect.get("table_grid")
    if rtype == "table" and grid:
        return str(grid)
    if rtype == "checkbox":
        return "marcado" if rect.get("is_filled") else "vacio"
    bbox = rect.get("bbox") or [0, 0, 0, 0]
    return f"{bbox[2]:.0f}x{bbox[3]:.0f}pt"


def _details_fused_items(step: PipelineStep) -> dict[str, Any] | None:
    fusion = getattr(step, "fusion", None)
    if fusion is None:
        return None
    items = list(getattr(fusion, "items", ()) or ())
    rows = []
    for it in items[:DETAILS_PREVIEW_LIMIT]:
        rows.append(
            {
                "text": (getattr(it, "text", "") or "")[:80],
                "section": getattr(it, "section_title", None),
                "docling_label": getattr(it, "docling_label", None),
                "in_box": getattr(it, "enclosing_box_id", None),
                "in_table": getattr(it, "table_id", None),
                "page": int(getattr(it, "page", 1) or 1),
            }
        )
    stats = {
        "matched_to_box": int(getattr(fusion, "matched_to_box", 0) or 0),
        "matched_to_docling": int(getattr(fusion, "matched_to_docling", 0) or 0),
        "coverage": float(getattr(fusion, "coverage", 0.0) or 0.0),
    }
    return {
        "kind": "fused_items",
        "rows": rows,
        "total": len(items),
        "stats": stats,
    }


def _details_pairs(pairs: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    matched_count = 0
    for p in pairs[:DETAILS_PREVIEW_LIMIT]:
        is_matched = bool(p.get("matched", False))
        if is_matched:
            matched_count += 1
        rows.append(
            {
                "field": str(p.get("field", "") or ""),
                "label_searched": list(p.get("label_searched") or []),
                "label_found": p.get("label_found"),
                "value_raw": p.get("value_raw"),
                "matched": is_matched,
            }
        )
    # `matched_count` above only counts the previewed rows; recompute for the
    # full list so the summary line shows the real number.
    full_matched = sum(1 for p in pairs if p.get("matched"))
    return {
        "kind": "pairs",
        "rows": rows,
        "total": len(pairs),
        "matched_count": full_matched,
    }


def _details_typed_fields(step: PipelineStep) -> dict[str, Any] | None:
    typed = getattr(step, "typed_fields", None)
    if not typed:
        return None
    rows = []
    ok_count = 0
    items = list(typed.items())
    for field_name, tv in items[:DETAILS_PREVIEW_LIMIT]:
        is_ok = bool(getattr(tv, "ok", False))
        if is_ok:
            ok_count += 1
        rows.append(
            {
                "field": field_name,
                "raw": str(getattr(tv, "raw", "") or ""),
                "normalized": str(getattr(tv, "normalized", "") or ""),
                "transform": str(getattr(tv, "transform_used", "") or ""),
                "ok": is_ok,
                "issues": list(getattr(tv, "issues", ()) or ()),
            }
        )
    full_ok = sum(1 for tv in typed.values() if getattr(tv, "ok", False))
    return {
        "kind": "typed_fields",
        "rows": rows,
        "total": len(items),
        "ok_count": full_ok,
    }


# ============================================================================ bbox labels


def _bbox_labels_from_details(details: dict[str, Any] | None) -> dict[int, str]:
    """Map bbox index -> short label so the SVG overlay can render text inside.

    Only Docling and pdfplumber bboxes carry labels — LiteParse text bboxes
    would clutter the overlay (one word per box).
    """
    if not details:
        return {}
    kind = details.get("kind")
    rows = details.get("rows") or []
    if kind == "blocks":
        return {i: str(r.get("label", "") or "") for i, r in enumerate(rows)}
    if kind == "visual_rects":
        return {i: str(r.get("rect_type", "") or "") for i, r in enumerate(rows)}
    return {}


__all__ = [
    "DETAILS_PREVIEW_LIMIT",
    "ENGINE_COLORS",
    "bbox_to_dict",
    "serialize_step",
]

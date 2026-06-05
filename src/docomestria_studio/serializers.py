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
    """Return a JSON-safe view of a step payload — drops non-serializable refs."""
    safe: dict[str, Any] = {}
    for key, value in payload.items():
        # The `result` field holds an ExtractionResult; we surface its summary
        # separately in `final`. Skip the raw object here to keep payload light.
        if key == "result":
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
    bboxes = []
    for bbox in step.bboxes or ():
        # PipelineStep.bboxes is a tuple of `BBox`; the page isn't on the bbox
        # so we default to 1 (the overlay falls back to the active page).
        try:
            bboxes.append(bbox_to_dict(bbox, page=1, label=""))
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
        "final": _serialize_final(step),
    }


__all__ = ["ENGINE_COLORS", "bbox_to_dict", "serialize_step"]

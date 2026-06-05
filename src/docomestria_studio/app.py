"""Flask app factory for docomestria-studio.

The factory wires together the in-memory session store, the background
pipeline runner, and a small set of HTTP endpoints that the htmx/Alpine
frontend polls and renders.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from flask import (
    Flask,
    abort,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)

from .config import StudioConfig, load_config
from .runner import PipelineFactory, default_pipeline_factory, start_background_run
from .serializers import serialize_step
from .sessions import SessionStore

_VALID_MODES = ("deterministic", "ai")


def create_app(
    config: StudioConfig | None = None,
    *,
    pipeline_factory: PipelineFactory | None = None,
) -> Flask:
    """Build the Flask app.

    Parameters
    ----------
    config:
        Optional pre-built `StudioConfig`. Tests pass an explicit one.
    pipeline_factory:
        Mode-aware callable ``factory(mode) -> pipeline``. Tests inject a
        fake factory; production uses the docomestria-backed default built
        from the config.
    """
    cfg = config or load_config()
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )
    app.config["MAX_CONTENT_LENGTH"] = cfg.upload_max_mb * 1024 * 1024
    app.config["STUDIO_CONFIG"] = cfg

    store = SessionStore()
    app.extensions["studio_sessions"] = store
    upload_dir = Path(tempfile.gettempdir()) / "docomestria-studio"
    upload_dir.mkdir(parents=True, exist_ok=True)
    app.config["STUDIO_UPLOAD_DIR"] = upload_dir

    factory = pipeline_factory or default_pipeline_factory(
        cfg.openrouter_api_key, cfg.openrouter_model
    )

    _register_routes(app, cfg, store, factory)
    return app


def _register_routes(
    app: Flask,
    cfg: StudioConfig,
    store: SessionStore,
    pipeline_factory: PipelineFactory,
) -> None:
    """Attach every HTTP route to the app."""

    @app.get("/")
    def index() -> Any:
        return render_template(
            "index.html",
            has_api_key=cfg.is_ready,
            model=cfg.openrouter_model,
            max_mb=cfg.upload_max_mb,
        )

    @app.post("/upload")
    def upload() -> Any:
        mode = request.form.get("mode", "deterministic").strip().lower()
        if mode not in _VALID_MODES:
            return jsonify({"error": f"Unknown mode: {mode}"}), 400
        if mode == "ai" and not cfg.is_ready:
            return _setup_required_response()

        file = request.files.get("pdf")
        if file is None or not file.filename:
            return jsonify({"error": "No file uploaded."}), 400
        if not file.filename.lower().endswith(".pdf"):
            return jsonify({"error": "Only PDF files are accepted."}), 400

        upload_dir: Path = app.config["STUDIO_UPLOAD_DIR"]
        # Save under a stable name in the upload dir so the runner can read it
        # asynchronously. We use the future session id once we know it.
        tmp_path = upload_dir / f"upload-{file.filename}"
        file.save(tmp_path)

        session = store.create(tmp_path, mode=mode)
        # Rename the file to embed the session id, avoiding collisions when
        # multiple users upload the same filename.
        final_path = upload_dir / f"{session.id}.pdf"
        tmp_path.rename(final_path)
        session.pdf_path = final_path

        start_background_run(session, pipeline_factory)
        return redirect(url_for("studio", session_id=session.id))

    @app.get("/studio/<session_id>")
    def studio(session_id: str) -> Any:
        session = store.get(session_id)
        if session is None:
            abort(404)
        return render_template(
            "studio.html",
            session_id=session.id,
            model=cfg.openrouter_model,
            mode=session.mode,
        )

    @app.get("/api/session/<session_id>/status")
    def session_status(session_id: str) -> Any:
        session = store.get(session_id)
        if session is None:
            abort(404)
        return jsonify(
            {
                "status": session.status,
                "mode": session.mode,
                "steps_done": len(session.steps),
                "steps_total": _total_steps(session),
                "error": session.error,
            }
        )

    @app.get("/api/session/<session_id>/step/<int:index>")
    def session_step(session_id: str, index: int) -> Any:
        session = store.get(session_id)
        if session is None:
            abort(404)
        if index < 0 or index >= len(session.steps):
            abort(404)
        return jsonify(serialize_step(session.steps[index]))

    @app.get("/api/session/<session_id>/pdf")
    def session_pdf(session_id: str) -> Any:
        session = store.get(session_id)
        if session is None:
            abort(404)
        if not session.pdf_path.exists():
            abort(404)
        return send_file(
            session.pdf_path,
            mimetype="application/pdf",
            as_attachment=False,
            download_name="document.pdf",
        )

    @app.post("/api/session/<session_id>/reset")
    def session_reset(session_id: str) -> Any:
        ok = store.delete(session_id)
        if not ok:
            abort(404)
        return jsonify({"deleted": True})

    @app.errorhandler(413)
    def too_large(_err: Any) -> Any:
        return (
            jsonify(
                {
                    "error": f"File too large. Max size is {cfg.upload_max_mb} MB.",
                }
            ),
            413,
        )


def _setup_required_response() -> Any:
    """Return a friendly JSON error when OPENROUTER_API_KEY is missing."""
    return (
        jsonify(
            {
                "error": "Setup required",
                "detail": (
                    "AI-assisted mode requires OPENROUTER_API_KEY. Set the"
                    " variable and restart, or pick the deterministic mode."
                ),
            }
        ),
        503,
    )


def _total_steps(session: Any) -> int:
    """Best-effort total step count from the latest captured step."""
    if not session.steps:
        # Mirror docomestria's canonical sequence length to keep progress
        # monotonic before the first step arrives. Deterministic mode is
        # shorter (~9 steps) than the LLM path (~13).
        return 9 if session.mode == "deterministic" else 13
    return session.steps[-1].total_steps


def main() -> None:
    """CLI entry point — run the Flask development server."""
    cfg = load_config()
    app = create_app(cfg)
    print(f"docomestria-studio — http://{cfg.host}:{cfg.port}")
    if not cfg.is_ready:
        print(
            "INFO: OPENROUTER_API_KEY is not set. Deterministic mode is"
            " available; AI-assisted mode will be disabled until you set it."
        )
    app.run(host=cfg.host, port=cfg.port, debug=cfg.debug)


__all__ = ["create_app", "main"]

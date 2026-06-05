"""Smoke tests for the Flask routes."""

from __future__ import annotations

import io
import time


def test_index_renders(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"docomestria" in response.data
    assert b"<form" in response.data


def test_upload_creates_session_and_redirects(client, pdf_bytes):
    response = client.post(
        "/upload",
        data={"pdf": (io.BytesIO(pdf_bytes), "sample.pdf")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 302
    assert "/studio/" in response.headers["Location"]
    session_id = response.headers["Location"].rsplit("/", 1)[-1]
    assert len(session_id) > 0


def test_upload_rejects_non_pdf(client):
    response = client.post(
        "/upload",
        data={"pdf": (io.BytesIO(b"hello"), "note.txt")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 400


def test_upload_rejects_empty(client):
    response = client.post(
        "/upload",
        data={},
        content_type="multipart/form-data",
    )
    assert response.status_code == 400


def test_studio_page_renders(client, pdf_bytes):
    upload = client.post(
        "/upload",
        data={"pdf": (io.BytesIO(pdf_bytes), "sample.pdf")},
        content_type="multipart/form-data",
    )
    session_id = upload.headers["Location"].rsplit("/", 1)[-1]
    page = client.get(f"/studio/{session_id}")
    assert page.status_code == 200
    assert b"studioApp" in page.data


def test_status_endpoint_returns_json(client, pdf_bytes):
    upload = client.post(
        "/upload",
        data={"pdf": (io.BytesIO(pdf_bytes), "sample.pdf")},
        content_type="multipart/form-data",
    )
    session_id = upload.headers["Location"].rsplit("/", 1)[-1]
    # The background thread should finish quickly with the fake pipeline.
    deadline = time.time() + 2.0
    status = None
    while time.time() < deadline:
        res = client.get(f"/api/session/{session_id}/status")
        assert res.status_code == 200
        status = res.get_json()
        if status["status"] == "ready":
            break
        time.sleep(0.05)
    assert status is not None
    assert status["status"] == "ready"
    assert status["steps_done"] == 3


def test_step_endpoint_returns_serialized_step(client, pdf_bytes):
    upload = client.post(
        "/upload",
        data={"pdf": (io.BytesIO(pdf_bytes), "sample.pdf")},
        content_type="multipart/form-data",
    )
    session_id = upload.headers["Location"].rsplit("/", 1)[-1]
    deadline = time.time() + 2.0
    while time.time() < deadline:
        if client.get(f"/api/session/{session_id}/status").get_json()["status"] == "ready":
            break
        time.sleep(0.05)
    res = client.get(f"/api/session/{session_id}/step/1")
    assert res.status_code == 200
    data = res.get_json()
    assert data["name"] == "extract_liteparse"
    assert data["engine_color"] == "#3b82f6"
    assert data["bboxes"]


def test_pdf_endpoint_serves_bytes(client, pdf_bytes):
    upload = client.post(
        "/upload",
        data={"pdf": (io.BytesIO(pdf_bytes), "sample.pdf")},
        content_type="multipart/form-data",
    )
    session_id = upload.headers["Location"].rsplit("/", 1)[-1]
    res = client.get(f"/api/session/{session_id}/pdf")
    assert res.status_code == 200
    assert res.mimetype == "application/pdf"
    assert res.data.startswith(b"%PDF")


def test_unknown_session_returns_404(client):
    assert client.get("/studio/does-not-exist").status_code == 404
    assert client.get("/api/session/does-not-exist/status").status_code == 404
    assert client.get("/api/session/does-not-exist/step/0").status_code == 404
    assert client.get("/api/session/does-not-exist/pdf").status_code == 404


def test_reset_deletes_session(client, pdf_bytes):
    upload = client.post(
        "/upload",
        data={"pdf": (io.BytesIO(pdf_bytes), "sample.pdf")},
        content_type="multipart/form-data",
    )
    session_id = upload.headers["Location"].rsplit("/", 1)[-1]
    res = client.post(f"/api/session/{session_id}/reset")
    assert res.status_code == 200
    assert client.get(f"/api/session/{session_id}/status").status_code == 404


def test_setup_required_when_no_api_key(test_config, fake_factory, pdf_bytes):
    """When OPENROUTER_API_KEY is missing the app boots but blocks uploads."""
    from dataclasses import replace

    from docomestria_studio.app import create_app

    bad_config = replace(test_config, openrouter_api_key=None)
    app = create_app(bad_config, pipeline_factory=fake_factory)
    app.config["TESTING"] = True
    client = app.test_client()

    # Landing page still renders.
    assert client.get("/").status_code == 200

    # Upload is refused with 503.
    res = client.post(
        "/upload",
        data={"pdf": (io.BytesIO(pdf_bytes), "sample.pdf")},
        content_type="multipart/form-data",
    )
    assert res.status_code == 503
    assert res.get_json()["error"] == "Setup required"

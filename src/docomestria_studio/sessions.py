"""In-memory session store for the studio viewer.

Each session captures the path to the uploaded PDF and the list of
`PipelineStep` objects emitted by `Pipeline.stream()`. Storage is process-
local and ephemeral — restarting the server clears all sessions.
"""

from __future__ import annotations

import contextlib
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:  # pragma: no cover
    from docomestria.pipeline.step import PipelineStep


Status = Literal["processing", "ready", "error"]


@dataclass
class StudioSession:
    """One uploaded PDF and its captured pipeline steps."""

    id: str
    pdf_path: Path
    status: Status = "processing"
    steps: list[PipelineStep] = field(default_factory=list)
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)

    def touch(self) -> None:
        """Update the access timestamp (called on every read)."""
        self.last_accessed = time.time()


class SessionStore:
    """Thread-safe in-memory map of session_id -> StudioSession."""

    def __init__(self) -> None:
        self._sessions: dict[str, StudioSession] = {}
        self._lock = threading.Lock()

    def create(self, pdf_path: Path) -> StudioSession:
        """Create a new session and return it."""
        session = StudioSession(id=str(uuid.uuid4()), pdf_path=pdf_path)
        with self._lock:
            self._sessions[session.id] = session
        return session

    def get(self, session_id: str) -> StudioSession | None:
        """Return the session, or None if missing. Touches access time."""
        with self._lock:
            session = self._sessions.get(session_id)
        if session is not None:
            session.touch()
        return session

    def delete(self, session_id: str) -> bool:
        """Remove a session and best-effort delete its temp PDF file."""
        with self._lock:
            session = self._sessions.pop(session_id, None)
        if session is None:
            return False
        with contextlib.suppress(OSError):
            session.pdf_path.unlink(missing_ok=True)
        return True

    def cleanup_old_sessions(self, max_age_minutes: int = 60) -> int:
        """Drop sessions whose last_accessed is older than the cutoff."""
        cutoff = time.time() - (max_age_minutes * 60)
        removed = 0
        with self._lock:
            stale_ids = [
                sid for sid, s in self._sessions.items() if s.last_accessed < cutoff
            ]
        for sid in stale_ids:
            if self.delete(sid):
                removed += 1
        return removed

    def __len__(self) -> int:
        return len(self._sessions)


__all__ = ["SessionStore", "StudioSession", "Status"]

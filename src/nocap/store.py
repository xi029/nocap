import hashlib
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path


class Store:
    """One local SQLite file. Connections are short-lived and thread-local."""

    def __init__(self, directory: Path):
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / "nocap.sqlite3"
        legacy = directory / "jevlens.sqlite3"  # Workspaces created before the rename.
        if legacy.exists() and not self.path.exists():
            legacy.rename(self.path)
        with self.connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS documents (id TEXT PRIMARY KEY, name TEXT, text TEXT)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS traces (id TEXT PRIMARY KEY, created TEXT, payload TEXT)"
            )

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=20)
        try:
            with db:
                yield db
        finally:
            db.close()

    def add_document(self, name: str, text: str) -> dict:
        name = Path(name.replace("\\", "/")).name.strip()
        text = text.strip()
        if not name or not text:
            raise ValueError("Document name and text must not be blank.")
        doc_id = hashlib.sha256(f"{name}\0{text}".encode()).hexdigest()[:16]
        with self.connect() as db:
            count = db.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
            exists = db.execute("SELECT 1 FROM documents WHERE id = ?", (doc_id,)).fetchone()
            if count >= 100 and not exists:
                raise ValueError("This local workspace is limited to 100 documents.")
            db.execute("INSERT OR IGNORE INTO documents VALUES (?, ?, ?)", (doc_id, name, text))
        return {"id": doc_id, "name": name, "chars": len(text)}

    def documents(self) -> list[dict]:
        with self.connect() as db:
            return [
                dict(zip(("id", "name", "text"), row, strict=True))
                for row in db.execute("SELECT id, name, text FROM documents ORDER BY name, id")
            ]

    def delete_document(self, doc_id: str) -> bool:
        with self.connect() as db:
            return db.execute("DELETE FROM documents WHERE id = ?", (doc_id,)).rowcount > 0

    def save_trace(self, payload: dict) -> dict:
        payload = {
            **payload,
            "id": uuid.uuid4().hex,
            "created": datetime.now(UTC).isoformat(),
            "schema_version": 1,
        }
        with self.connect() as db:
            db.execute(
                "INSERT INTO traces VALUES (?, ?, ?)",
                (payload["id"], payload["created"], json.dumps(payload, ensure_ascii=False)),
            )
        return payload

    def trace(self, trace_id: str) -> dict | None:
        with self.connect() as db:
            row = db.execute("SELECT payload FROM traces WHERE id = ?", (trace_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def history(self) -> list[dict]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT payload FROM traces ORDER BY created DESC LIMIT 30"
            ).fetchall()
        return [
            {k: trace[k] for k in ("id", "created", "question", "action", "decision")}
            for trace in (json.loads(row[0]) for row in rows)
        ]

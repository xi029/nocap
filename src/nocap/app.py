from pathlib import Path
from typing import Annotated
from urllib.parse import urlparse

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import __version__
from .config import Settings
from .engine import replay, run_decision, run_query
from .models import DecisionQuery, DocumentInput, Query, ReplayInput
from .providers import ProviderError
from .samples import CONFLICT_DOCUMENT, DOCUMENTS, SCENARIOS
from .store import Store

STATIC = Path(__file__).parent / "static"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    store = Store(settings.data_dir)
    app = FastAPI(title="NoCap", version=__version__, description="No evidence, no answer.")
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "[::1]", "testserver"]
    )
    app.state.store = store
    app.state.settings = settings

    @app.middleware("http")
    async def local_workspace(request: Request, call_next):
        origin = request.headers.get("origin")
        if request.method in {"POST", "DELETE", "PUT", "PATCH"} and origin:
            parsed = urlparse(origin)
            if parsed.netloc != request.url.netloc or parsed.scheme != request.url.scheme:
                return JSONResponse(
                    {"detail": "Cross-origin workspace writes are disabled."}, status_code=403
                )
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"
        )
        if request.url.path in {"/docs", "/redoc"}:
            # FastAPI's default documentation uses the official Swagger/ReDoc CDN assets.
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "img-src 'self' data: https://fastapi.tiangolo.com; connect-src 'self'; "
                "frame-ancestors 'none'; base-uri 'none'"
            )
        return response

    @app.get("/health")
    def health():
        return {"status": "ok", "version": __version__}

    @app.get("/api/config")
    def config():
        return {
            "provider": settings.provider,
            "ollama_model": settings.ollama_model,
            "scenarios": SCENARIOS,
            "version": __version__,
            "providers": ["demo", "ollama", "openai", "laya", "jev"],
        }

    @app.get("/api/documents")
    def documents():
        return [
            {"id": d["id"], "name": d["name"], "chars": len(d["text"])} for d in store.documents()
        ]

    @app.post("/api/documents", status_code=201)
    def add_document(document: DocumentInput):
        try:
            return store.add_document(document.name, document.text)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.post("/api/upload", status_code=201)
    async def upload(file: Annotated[UploadFile, File()]):
        if Path(file.filename or "").suffix.lower() not in {".md", ".txt"}:
            raise HTTPException(422, "Upload a UTF-8 .md or .txt file.")
        content = await file.read(200_001)
        await file.close()
        if len(content) > 200_000:
            raise HTTPException(413, "File must be 200 KB or smaller.")
        try:
            return store.add_document(file.filename or "document.txt", content.decode("utf-8-sig"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise HTTPException(
                422, "Upload a nonempty UTF-8 text document (up to 100 documents)."
            ) from exc

    @app.delete("/api/documents/{document_id}")
    def delete_document(document_id: str):
        if not store.delete_document(document_id):
            raise HTTPException(404, "Document not found.")
        return {"deleted": document_id, "note": "Saved traces retain their original excerpts."}

    @app.post("/api/samples")
    def samples():
        return [store.add_document(name, text) for name, text in DOCUMENTS.items()]

    @app.post("/api/samples/conflict")
    def conflict_sample():
        for name, text in DOCUMENTS.items():
            store.add_document(name, text)
        return store.add_document(*CONFLICT_DOCUMENT)

    @app.post("/api/query")
    async def query(body: Query):
        try:
            return await run_query(store, settings, body)
        except ProviderError as exc:
            raise HTTPException(502, str(exc)) from exc

    @app.post("/api/decide")
    async def decide(body: DecisionQuery):
        try:
            return await run_decision(store, settings, body)
        except ProviderError as exc:
            raise HTTPException(502, str(exc)) from exc

    @app.get("/api/traces")
    def history():
        return store.history()

    def get_trace(trace_id: str):
        trace = store.trace(trace_id)
        if trace is None:
            raise HTTPException(404, "Trace not found.")
        return trace

    @app.get("/api/traces/{trace_id}")
    def trace(trace_id: str):
        return get_trace(trace_id)

    @app.get("/api/traces/{trace_id}/export")
    def export(trace_id: str):
        return JSONResponse(
            get_trace(trace_id),
            headers={
                "Content-Disposition": f'attachment; filename="nocap-{trace_id}.json"',
            },
        )

    @app.post("/api/traces/{trace_id}/replay")
    def replay_trace(trace_id: str, body: ReplayInput):
        return replay(get_trace(trace_id), body.policy)

    @app.get("/")
    def index():
        return FileResponse(STATIC / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app

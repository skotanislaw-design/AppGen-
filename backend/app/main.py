"""Nomos Audit API — έλεγχος νομικής πληρότητας δικογράφων."""

import logging

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings
from app.exemplars import EXEMPLARS
from app.extraction import ExtractionError, extract_text
from app.pipeline import checklists
from app.pipeline.engine import (
    PipelineError,
    run_pipeline,
    run_pipeline_events,
    sse_event,
)
from app.schemas import (
    AnalyzeRequest,
    AuditReport,
    DocumentTypeInfo,
    ExemplarDetail,
    ExemplarSummary,
    ExtractResponse,
)

logger = logging.getLogger("nomos_audit")

app = FastAPI(
    title="Nomos Audit API",
    version="1.0.0",
    description="Αυστηρός έλεγχος νομικής πληρότητας ελληνικών δικογράφων.",
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

_bearer = HTTPBearer(auto_error=False)


async def require_api_key(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> None:
    expected = get_settings().api_key
    if not expected:
        return
    if credentials is None or credentials.credentials != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"detail": "Μη έγκυρο ή ελλείπον API key.", "code": "unauthorized"},
        )


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "model": get_settings().model}


@app.get("/api/document-types", response_model=list[DocumentTypeInfo])
async def document_types() -> list[DocumentTypeInfo]:
    return [
        DocumentTypeInfo(
            key=spec.key,
            label=spec.label,
            branch=spec.branch,
            description=spec.description,
        )
        for spec in checklists.DOCUMENT_TYPES.values()
    ]


@app.get("/api/exemplars", response_model=list[ExemplarSummary])
async def exemplars() -> list[ExemplarSummary]:
    return [
        ExemplarSummary(
            doc_type=ex.doc_type,
            doc_type_label=checklists.get_spec(ex.doc_type).label,
            branch=checklists.get_spec(ex.doc_type).branch,
            title=ex.title,
            scenario=ex.scenario,
        )
        for ex in EXEMPLARS.values()
    ]


@app.get("/api/exemplars/{doc_type}", response_model=ExemplarDetail)
async def exemplar_detail(doc_type: str) -> ExemplarDetail:
    ex = EXEMPLARS.get(doc_type)
    if ex is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "detail": "Δεν υπάρχει υπόδειγμα για το είδος αυτό.",
                "code": "exemplar_not_found",
            },
        )
    spec = checklists.get_spec(ex.doc_type)
    return ExemplarDetail(
        doc_type=ex.doc_type,
        doc_type_label=spec.label,
        branch=spec.branch,
        title=ex.title,
        scenario=ex.scenario,
        body=ex.body,
        drafting_notes=ex.drafting_notes,
        key_provisions=ex.key_provisions,
    )


@app.post(
    "/api/extract",
    response_model=ExtractResponse,
    dependencies=[Depends(require_api_key)],
)
async def extract(file: UploadFile = File(...)) -> ExtractResponse:
    data = await file.read()
    max_bytes = 25 * 1024 * 1024
    if len(data) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={"detail": "Το αρχείο υπερβαίνει τα 25MB.", "code": "file_too_large"},
        )
    try:
        text = extract_text(file.filename or "document", data)
    except ExtractionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"detail": str(exc), "code": "extraction_failed"},
        ) from exc
    return ExtractResponse(
        filename=file.filename or "document", text=text, characters=len(text)
    )


@app.post(
    "/api/analyze",
    response_model=AuditReport,
    dependencies=[Depends(require_api_key)],
)
async def analyze(request: AnalyzeRequest) -> AuditReport:
    try:
        return await run_pipeline(request.text, request.context, request.doc_type_hint)
    except PipelineError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"detail": str(exc), "code": "pipeline_error"},
        ) from exc


@app.post("/api/analyze/stream", dependencies=[Depends(require_api_key)])
async def analyze_stream(request: AnalyzeRequest) -> StreamingResponse:
    async def event_stream():
        try:
            async for stage, payload in run_pipeline_events(
                request.text, request.context, request.doc_type_hint
            ):
                yield sse_event(stage, payload)
        except PipelineError as exc:
            yield sse_event("error", {"detail": str(exc), "code": "pipeline_error"})
        except Exception:
            logger.exception("Απρόβλεπτο σφάλμα pipeline")
            yield sse_event(
                "error",
                {"detail": "Απρόβλεπτο σφάλμα κατά την ανάλυση.", "code": "internal"},
            )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

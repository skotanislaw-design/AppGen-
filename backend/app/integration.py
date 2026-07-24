"""Mountable FastAPI router για ενσωμάτωση του Nomos Audit στο Nomos One.

Ο router είναι auth-agnostic: περνάτε το δικό σας RBAC dependency του LPMS
(π.χ. `require_role(["super_admin", "admin", "attorney", "paralegal"])`) ως
`auth_dependency`, οπότε κάθε endpoint ελέγχου κάθεται πίσω από το JWT και
τους ρόλους του Nomos One. Ο πυρήνας του pipeline (ταξινόμηση → έλεγχος από
ειδικό κλάδου → πρότυπο γραφείου → ντετερμινιστική βαθμολόγηση) και η
βιβλιοθήκη υποδειγμάτων επαναχρησιμοποιούνται αυτούσια — δεν διπλασιάζεται
λογική, μόνο η ενορχήστρωση των routes.

Παράδειγμα ενσωμάτωσης στο main.py του Nomos One:

    from app.core.auth import require_role
    from nomos_audit.integration import create_audit_router

    app.include_router(
        create_audit_router(
            auth_dependency=require_role(
                ["super_admin", "admin", "attorney", "paralegal"]
            ),
            on_result=persist_audit_to_matter,   # προαιρετικό hook (MongoDB)
        ),
        prefix="/api",
    )

Οι διαδρομές γίνονται τότε /api/audit/... πίσω από το JWT/RBAC του LPMS.
"""

import inspect
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response, StreamingResponse

from app.docx_export import build_exemplar_docx
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

logger = logging.getLogger("nomos_audit.integration")

# Προτεινόμενοι ρόλοι με πρόσβαση στον έλεγχο δικογράφων. Ο client αποκλείεται:
# ο έλεγχος αφορά εσωτερική νομική εργασία, όχι το portal του εντολέα.
DEFAULT_AUDIT_ROLES = ["super_admin", "admin", "attorney", "paralegal"]

DOCX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)

# Τύπος του προαιρετικού hook εμμονής: λαμβάνει (χρήστης, matter_id, report).
ResultHook = Callable[[Any, str | None, AuditReport], Awaitable[None] | None]


class MatterAnalyzeRequest(AnalyzeRequest):
    """Αίτημα ανάλυσης εντός LPMS, προαιρετικά συνδεδεμένο με υπόθεση."""

    matter_id: str | None = None


async def _maybe_call(hook: ResultHook | None, *args: Any) -> None:
    if hook is None:
        return
    try:
        result = hook(*args)
        if inspect.isawaitable(result):
            await result
    except Exception:
        # Η αποτυχία εμμονής δεν πρέπει να ρίχνει τον ίδιο τον έλεγχο.
        logger.exception("Απέτυχε το hook εμμονής αποτελέσματος ελέγχου")


def create_audit_router(
    *,
    auth_dependency: Callable[..., Any],
    prefix: str = "/audit",
    on_result: ResultHook | None = None,
) -> APIRouter:
    """Δημιουργεί τον router του ελέγχου, gated πίσω από το `auth_dependency`.

    - `auth_dependency`: το RBAC dependency του Nomos One (π.χ. require_role).
      Εφαρμόζεται σε ΟΛΕΣ τις διαδρομές — ακόμη και οι αναγνώσεις απαιτούν
      έγκυρη συνεδρία στελέχους.
    - `on_result`: προαιρετικό (async) callable για εμμονή του αποτελέσματος
      (π.χ. σύνδεση με υπόθεση στο MongoDB). Καλείται με (user, matter_id,
      report) μετά από κάθε επιτυχή ανάλυση.
    """
    router = APIRouter(
        prefix=prefix,
        tags=["audit"],
        dependencies=[Depends(auth_dependency)],
    )

    @router.get("/document-types", response_model=list[DocumentTypeInfo])
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

    @router.get("/exemplars", response_model=list[ExemplarSummary])
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

    @router.get("/exemplars/{doc_type}", response_model=ExemplarDetail)
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

    @router.get("/exemplars/{doc_type}/docx")
    async def exemplar_docx(doc_type: str) -> Response:
        ex = EXEMPLARS.get(doc_type)
        if ex is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "detail": "Δεν υπάρχει υπόδειγμα για το είδος αυτό.",
                    "code": "exemplar_not_found",
                },
            )
        data = build_exemplar_docx(ex)
        filename = f"skotanis-ypodeigma-{doc_type}.docx"
        return Response(
            content=data,
            media_type=DOCX_MEDIA_TYPE,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @router.post("/extract", response_model=ExtractResponse)
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

    @router.post("/analyze", response_model=AuditReport)
    async def analyze(
        request: MatterAnalyzeRequest,
        user: Any = Depends(auth_dependency),
    ) -> AuditReport:
        try:
            report = await run_pipeline(
                request.text, request.context, request.doc_type_hint
            )
        except PipelineError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"detail": str(exc), "code": "pipeline_error"},
            ) from exc
        await _maybe_call(on_result, user, request.matter_id, report)
        return report

    @router.post("/analyze/stream")
    async def analyze_stream(
        request: MatterAnalyzeRequest,
        user: Any = Depends(auth_dependency),
    ) -> StreamingResponse:
        async def event_stream():
            try:
                async for stage, payload in run_pipeline_events(
                    request.text, request.context, request.doc_type_hint
                ):
                    if stage == "complete":
                        await _maybe_call(on_result, user, request.matter_id, payload)
                    yield sse_event(stage, payload)
            except PipelineError as exc:
                yield sse_event("error", {"detail": str(exc), "code": "pipeline_error"})
            except Exception:
                logger.exception("Απρόβλεπτο σφάλμα pipeline (ενσωματωμένο)")
                yield sse_event(
                    "error",
                    {"detail": "Απρόβλεπτο σφάλμα κατά την ανάλυση.", "code": "internal"},
                )

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return router

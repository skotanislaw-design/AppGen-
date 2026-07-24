"""Παράδειγμα hook εμμονής αποτελεσμάτων ελέγχου, συνδεδεμένων με υπόθεση.

Δείχνει πώς το on_result του create_audit_router γράφει το αποτέλεσμα στο
MongoDB του Nomos One, συνδεδεμένο με matter και χρήστη — ώστε ο έλεγχος να
εμφανίζεται στο ιστορικό της υπόθεσης (module Documents/Matters). Προσαρμόστε
τα ονόματα collection/πεδίων στο σχήμα σας.

Χρήση στο main.py του Nomos One:

    from app.db import get_database          # το δικό σας MongoDB handle
    from nomos_audit.integration import create_audit_router
    from app.core.auth import require_role

    async def persist_audit(user, matter_id, report):
        await save_audit_result(get_database(), user, matter_id, report)

    app.include_router(
        create_audit_router(
            auth_dependency=require_role(
                ["super_admin", "admin", "attorney", "paralegal"]
            ),
            on_result=persist_audit,
        ),
        prefix="/api",
    )
"""

from datetime import datetime, timezone
from typing import Any

from app.schemas import AuditReport


async def save_audit_result(
    db: Any,
    user: Any,
    matter_id: str | None,
    report: AuditReport,
) -> None:
    """Αποθηκεύει σύνοψη + πλήρη αναφορά ελέγχου στο MongoDB.

    `db` είναι ένα Motor/PyMongo-συμβατό database handle. `user` το αντικείμενο
    χρήστη του Nomos One (αναμένεται να εκθέτει id/role — προσαρμόστε).
    """
    document = {
        "matter_id": matter_id,
        "created_by": getattr(user, "id", None),
        "created_by_role": getattr(user, "role", None),
        "created_at": datetime.now(timezone.utc),
        "doc_type": report.classification.doc_type,
        "doc_type_label": report.classification.label,
        "branch": report.classification.branch,
        "auditor_title": report.auditor.title,
        "overall_score": report.score.overall,
        "verdict": report.score.verdict,
        "firm_standard": report.score.firm_standard,
        "model": report.model,
        # Πλήρης αναφορά για αναδρομική προβολή στο ιστορικό της υπόθεσης.
        "report": report.model_dump(mode="json"),
    }
    # Προσαρμόστε το όνομα collection στο σχήμα του Nomos One.
    await db["document_audits"].insert_one(document)


# Παράδειγμα ανάκτησης ιστορικού ελέγχων μιας υπόθεσης (για το UI της υπόθεσης).
async def list_matter_audits(db: Any, matter_id: str) -> list[dict]:
    cursor = (
        db["document_audits"]
        .find(
            {"matter_id": matter_id},
            {"report": 0},  # χωρίς το βαρύ report στη λίστα
        )
        .sort("created_at", -1)
    )
    return [doc async for doc in cursor]

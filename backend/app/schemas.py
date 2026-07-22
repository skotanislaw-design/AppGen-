"""Pydantic μοντέλα: structured outputs του Claude και API request/response."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    """Βάση για structured outputs: παράγει additionalProperties: false στο schema."""

    model_config = ConfigDict(extra="forbid")

# ---------------------------------------------------------------------------
# Structured outputs — Στάδιο 1: Ταξινόμηση
# ---------------------------------------------------------------------------

Branch = Literal["penal", "civil", "administrative", "extrajudicial", "generic"]


class DocumentClassification(StrictModel):
    doc_type: str = Field(
        description="Κλειδί είδους από το παρεχόμενο μητρώο (π.χ. 'agogi', 'exodiko')."
    )
    branch: Branch = Field(description="Κλάδος δικαίου του εγγράφου.")
    label: str = Field(description="Σύντομη ελληνική ονομασία του είδους.")
    purpose: str = Field(
        description="Ο δικονομικός/έννομος σκοπός που επιδιώκει το έγγραφο."
    )
    court_or_authority: str | None = Field(
        default=None,
        description="Το δικαστήριο ή η αρχή στην οποία απευθύνεται, όπως προκύπτει.",
    )
    procedural_stage: str | None = Field(
        default=None,
        description="Το δικονομικό στάδιο/πλαίσιο (π.χ. πρώτος βαθμός, προδικασία).",
    )
    summary: str = Field(
        description="Περίληψη 2-4 προτάσεων του αντικειμένου του εγγράφου."
    )
    confidence: Literal["high", "medium", "low"] = Field(
        description="Βαθμός βεβαιότητας της ταξινόμησης."
    )


# ---------------------------------------------------------------------------
# Structured outputs — Στάδιο 2: Έλεγχος πληρότητας
# ---------------------------------------------------------------------------

CriterionStatus = Literal["met", "partially_met", "missing", "not_applicable"]
Severity = Literal["critical", "major", "minor"]
Priority = Literal["critical", "high", "medium", "low"]


class CriterionEvaluation(StrictModel):
    criterion_id: str = Field(description="Το id του κριτηρίου από το checklist.")
    status: CriterionStatus
    score: int = Field(
        description="Βαθμός κάλυψης 0-100. Για status 'not_applicable' βάλε 0."
    )
    evidence: str | None = Field(
        default=None,
        description="Σύντομο αυτούσιο απόσπασμα του εγγράφου που τεκμηριώνει την κρίση.",
    )
    commentary: str = Field(
        description="Αιτιολογημένη νομική κρίση στα ελληνικά: τι καλύπτεται, τι λείπει, γιατί."
    )

    @field_validator("score")
    @classmethod
    def _clamp(cls, v: int) -> int:
        return max(0, min(100, v))


class ExtraFinding(StrictModel):
    title: str = Field(description="Σύντομος τίτλος του ευρήματος.")
    severity: Severity
    commentary: str = Field(
        description="Ανάλυση του προβλήματος που εντοπίστηκε πέραν του checklist."
    )


class Suggestion(StrictModel):
    priority: Priority
    target: str = Field(
        description="Το σημείο/τμήμα του εγγράφου που αφορά η βελτίωση."
    )
    proposed_action: str = Field(
        description="Συγκεκριμένη βελτιωτική ενέργεια, με προτεινόμενη διατύπωση όπου χρειάζεται."
    )
    rationale: str = Field(description="Γιατί η αλλαγή είναι αναγκαία ή σκόπιμη.")


class AuditModelOutput(StrictModel):
    evaluations: list[CriterionEvaluation] = Field(
        description="Μία αξιολόγηση για ΚΑΘΕ κριτήριο του checklist, με το ίδιο criterion_id."
    )
    extra_findings: list[ExtraFinding] = Field(
        description="Ουσιώδη προβλήματα που δεν καλύπτονται από τα κριτήρια του checklist."
    )
    suggestions: list[Suggestion] = Field(
        description="Ιεραρχημένες βελτιωτικές προτάσεις."
    )
    overall_assessment: str = Field(
        description=(
            "Συνολική ουσιαστική αξιολόγηση σε ρέοντα, υψηλού επιπέδου ελληνικό "
            "νομικό λόγο (2-4 παράγραφοι, χωρίς λίστες)."
        )
    )


# ---------------------------------------------------------------------------
# API μοντέλα
# ---------------------------------------------------------------------------


class AnalyzeRequest(BaseModel):
    text: str = Field(description="Το πλήρες κείμενο του δικογράφου.")
    context: str | None = Field(
        default=None,
        description="Προαιρετικό πλαίσιο από τον χρήστη (σκοπός, ιστορικό υπόθεσης).",
    )
    doc_type_hint: str | None = Field(
        default=None,
        description="Προαιρετική επιβολή είδους (κλειδί μητρώου) — παρακάμπτει την ταξινόμηση.",
    )


class CriterionReport(BaseModel):
    criterion_id: str
    category: str
    category_label: str
    text: str
    critical: bool
    weight: float
    status: CriterionStatus
    score: int
    evidence: str | None
    commentary: str


class CategoryScore(BaseModel):
    category: str
    label: str
    weight: float
    score: float | None  # None όταν κανένα κριτήριο δεν είναι εφαρμοστέο
    criteria_count: int


class ScoreSummary(BaseModel):
    overall: float
    verdict: str
    verdict_detail: str
    capped: bool
    cap_reason: str | None
    categories: list[CategoryScore]


class AuditorInfo(BaseModel):
    branch: str
    title: str
    description: str


class AuditReport(BaseModel):
    classification: DocumentClassification
    auditor: AuditorInfo
    score: ScoreSummary
    criteria: list[CriterionReport]
    extra_findings: list[ExtraFinding]
    suggestions: list[Suggestion]
    overall_assessment: str
    model: str


class ExtractResponse(BaseModel):
    filename: str
    text: str
    characters: int


class DocumentTypeInfo(BaseModel):
    key: str
    label: str
    branch: str
    description: str

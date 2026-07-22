"""Ο agent ελέγχου: ταξινόμηση → ανάθεση σε ειδικό κλάδου → έλεγχος → βαθμολόγηση.

Η ταξινόμηση (στάδιο 1) γίνεται από ουδέτερο «δικονομολόγο διαλογής». Ο κατ'
ουσίαν έλεγχος (στάδιο 2) ΔΕΝ γίνεται από γενικό ελεγκτή: το δικόγραφο
δρομολογείται στον ειδικό του οικείου κλάδου (ποινικολόγο, αστικολόγο-
δικονομολόγο, διοικητικολόγο, ειδικό εξωδικαστικής πρακτικής — βλ.
experts.py), ο οποίος φέρει το γνωστικό υπόβαθρο και το δόγμα ελέγχου του
κλάδου του.

Και τα δύο στάδια εκτελούνται με structured outputs (output_config.format),
ώστε η απόκριση να είναι εγγυημένα έγκυρο JSON κατά το σχήμα. Η τελική
βαθμολογία υπολογίζεται ντετερμινιστικά στο scorer — όχι από το μοντέλο.
"""

import json
from collections.abc import AsyncIterator
from typing import Any, TypeVar

import anthropic
from anthropic import AsyncAnthropic
from pydantic import BaseModel

from app.config import Settings, get_settings
from app.pipeline import checklists
from app.pipeline.checklists import CATEGORY_LABELS, Criterion
from app.pipeline.experts import ExpertProfile, expert_for
from app.pipeline.scorer import compute_score
from app.schemas import (
    AuditModelOutput,
    AuditorInfo,
    AuditReport,
    CriterionReport,
    DocumentClassification,
)

T = TypeVar("T", bound=BaseModel)


class PipelineError(RuntimeError):
    """Σφάλμα εκτέλεσης του pipeline με μήνυμα κατάλληλο για τον χρήστη."""


TRIAGE_SYSTEM_PROMPT = """\
Είσαι έμπειρος Έλληνας δικονομολόγος και ενεργείς ως υπεύθυνος διαλογής \
δικογράφων στο γραφείο Skotanis & Associates. Έργο σου είναι αποκλειστικά η \
ακριβής ταξινόμηση του εγγράφου που σου υποβάλλεται — είδος, κλάδος δικαίου, \
σκοπός, δικονομικό πλαίσιο — ώστε ο κατ' ουσίαν έλεγχος να ανατεθεί στον \
ειδικό του οικείου κλάδου. Δεν αξιολογείς την ποιότητα του εγγράφου. Κρίνεις \
μόνο βάσει του κειμένου και του δηλωθέντος πλαισίου, χωρίς εικασίες.
"""

COMMON_AUDIT_RULES = """\
Ενεργείς ως αυστηρός ελεγκτής νομικής πληρότητας δικογράφων στο γραφείο \
Skotanis & Associates, εντός του πεδίου της ειδικότητάς σου.

Αποστολή σου είναι ο ενδελεχής, αμερόληπτος και αυστηρός έλεγχος του εγγράφου \
που σου υποβάλλεται: τυπική πληρότητα, ουσιαστική επάρκεια, νομική τεκμηρίωση \
και ποιότητα δικανικού λόγου. Δεν είσαι συντάκτης του εγγράφου ούτε συνήγορός \
του — είσαι ο κριτής του, όπως θα το έκρινε ο δικαστής ή ο αντίδικος.

Κανόνες ελέγχου:
1. Κρίνεις ΜΟΝΟ βάσει του κειμένου που σου δίνεται και του δηλωθέντος \
πλαισίου. Ό,τι δεν προκύπτει από το έγγραφο θεωρείται ελλείπον, ακόμη κι αν \
πιθανολογείται ότι υπάρχει αλλού στον φάκελο.
2. Ανέφερε ΚΑΘΕ έλλειψη που εντοπίζεις, και τις αμφίβολες — η διήθηση γίνεται \
σε επόμενο στάδιο. Καλύτερα ένα εύρημα που θα απορριφθεί παρά μια σιωπηρή \
παράλειψη.
3. Κάθε κρίση σου τεκμηριώνεται: παραθέτεις σύντομο αυτούσιο απόσπασμα του \
εγγράφου ως στοιχείο, ή διαπιστώνεις ρητά την απουσία.
4. Οι διατάξεις που επικαλείσαι αναφέρονται με πλήρη στοιχεία (άρθρο, \
παράγραφος, νομοθέτημα). Αν το έγγραφο επικαλείται ανίσχυρη ή τροποποιημένη \
διάταξη, το επισημαίνεις.
5. Ο σχολιασμός σου συντάσσεται σε άρτια ελληνική νομική γλώσσα, υψηλού \
δικανικού ύφους, χωρίς κοινοτοπίες.
6. Δεν επινοείς περιστατικά, νομολογία ή διατάξεις. Όπου δεν είσαι βέβαιος \
για την τρέχουσα μορφή διάταξης, διατυπώνεις τη σχετική επιφύλαξη.
7. Αν το έγγραφο εμπλέκει παρεμπιπτόντως ζητήματα άλλου κλάδου δικαίου εκτός \
της ειδικότητάς σου, τα καταγράφεις στα extra_findings με ρητή σύσταση \
ελέγχου από ειδικό του οικείου κλάδου — δεν τα προσπερνάς σιωπηρά.
"""


def build_audit_system_prompt(expert: ExpertProfile) -> str:
    """System prompt σταδίου 2: ταυτότητα ειδικού + κοινοί κανόνες ελέγχου."""
    return f"{expert.identity}\n\n{COMMON_AUDIT_RULES}"


# ---------------------------------------------------------------------------
# Κλήση Claude με structured output
# ---------------------------------------------------------------------------


def _document_block(text: str, context: str | None) -> dict[str, Any]:
    parts = [f"<ΕΓΓΡΑΦΟ>\n{text}\n</ΕΓΓΡΑΦΟ>"]
    if context and context.strip():
        parts.append(f"<ΠΛΑΙΣΙΟ_ΑΠΟ_ΤΟΝ_ΕΝΤΟΛΕΑ>\n{context.strip()}\n</ΠΛΑΙΣΙΟ_ΑΠΟ_ΤΟΝ_ΕΝΤΟΛΕΑ>")
    return {
        "type": "text",
        "text": "\n\n".join(parts),
        "cache_control": {"type": "ephemeral"},
    }


async def _structured_call(
    client: AsyncAnthropic,
    settings: Settings,
    *,
    system_prompt: str,
    document: dict[str, Any],
    task: str,
    output_model: type[T],
    effort: str,
) -> T:
    schema = output_model.model_json_schema()
    try:
        response = await client.messages.create(
            model=settings.model,
            max_tokens=settings.max_output_tokens,
            thinking={"type": "adaptive"},
            output_config={
                "effort": effort,
                "format": {"type": "json_schema", "schema": schema},
            },
            system=[
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[
                {"role": "user", "content": [document, {"type": "text", "text": task}]}
            ],
        )
    except anthropic.AuthenticationError as exc:
        raise PipelineError(
            "Μη έγκυρο ANTHROPIC_API_KEY — ελέγξτε τη ρύθμιση του διακομιστή."
        ) from exc
    except anthropic.RateLimitError as exc:
        raise PipelineError(
            "Υπέρβαση ορίου αιτημάτων προς το Claude API — δοκιμάστε ξανά σε λίγο."
        ) from exc
    except anthropic.APIStatusError as exc:
        raise PipelineError(f"Σφάλμα Claude API ({exc.status_code}).") from exc
    except anthropic.APIConnectionError as exc:
        raise PipelineError("Αδυναμία σύνδεσης με το Claude API.") from exc

    if response.stop_reason == "refusal":
        raise PipelineError(
            "Το μοντέλο αρνήθηκε να επεξεργαστεί το περιεχόμενο του εγγράφου."
        )
    if response.stop_reason == "max_tokens":
        raise PipelineError(
            "Η ανάλυση υπερέβη το όριο εξόδου — δοκιμάστε με συντομότερο έγγραφο."
        )

    text = next((b.text for b in response.content if b.type == "text"), None)
    if text is None:
        raise PipelineError("Κενή απόκριση από το μοντέλο.")
    try:
        return output_model.model_validate_json(text)
    except Exception as exc:
        raise PipelineError("Μη έγκυρη δομημένη απόκριση από το μοντέλο.") from exc


# ---------------------------------------------------------------------------
# Στάδιο 1 — Ταξινόμηση
# ---------------------------------------------------------------------------

CLASSIFY_TASK_TEMPLATE = """\
ΣΤΑΔΙΟ 1 — ΤΑΞΙΝΟΜΗΣΗ

Προσδιόρισε το είδος, τον κλάδο, τον σκοπό και το δικονομικό πλαίσιο του \
ανωτέρω εγγράφου. Επίλεξε το doc_type ΑΠΟΚΛΕΙΣΤΙΚΑ από το ακόλουθο μητρώο· αν \
κανένα είδος δεν ταιριάζει, επίλεξε 'generic' και περιέγραψε το είδος στο label.

ΜΗΤΡΩΟ ΕΙΔΩΝ:
{menu}

Στο summary απόδωσε με ακρίβεια το αντικείμενο του εγγράφου. Στο confidence \
δήλωσε πόσο βέβαιος είσαι για την ταξινόμηση.
"""


async def classify(
    client: AsyncAnthropic,
    settings: Settings,
    document: dict[str, Any],
) -> DocumentClassification:
    task = CLASSIFY_TASK_TEMPLATE.format(menu=checklists.classification_menu())
    result = await _structured_call(
        client,
        settings,
        system_prompt=TRIAGE_SYSTEM_PROMPT,
        document=document,
        task=task,
        output_model=DocumentClassification,
        effort=settings.classification_effort,
    )
    if result.doc_type not in checklists.DOCUMENT_TYPES:
        result = result.model_copy(update={"doc_type": "generic"})
    return result


# ---------------------------------------------------------------------------
# Στάδιο 2 — Έλεγχος πληρότητας
# ---------------------------------------------------------------------------


def _render_checklist(criteria: list[Criterion]) -> str:
    lines = []
    for crit in criteria:
        flag = " [ΚΡΙΣΙΜΟ]" if crit.critical else ""
        lines.append(
            f"- id: {crit.id} | κατηγορία: {CATEGORY_LABELS[crit.category]}{flag}\n"
            f"  {crit.text}"
        )
    return "\n".join(lines)


AUDIT_TASK_TEMPLATE = """\
ΣΤΑΔΙΟ 2 — ΕΛΕΓΧΟΣ ΝΟΜΙΚΗΣ ΠΛΗΡΟΤΗΤΑΣ

Το έγγραφο ταξινομήθηκε ως: {label} ({branch}).
Σκοπός: {purpose}
Δικονομικό πλαίσιο: {stage}

Αξιολόγησε το έγγραφο έναντι ΚΑΘΕ κριτηρίου του ακόλουθου καταλόγου. Για κάθε \
κριτήριο επίστρεψε μία εγγραφή στο evaluations με το ίδιο ακριβώς criterion_id.

ΚΑΤΑΛΟΓΟΣ ΚΡΙΤΗΡΙΩΝ:
{checklist}

Οδηγίες αξιολόγησης:
- status: "met" μόνο όταν το κριτήριο καλύπτεται πλήρως και ορθά· \
"partially_met" όταν υπάρχει ατελής, αόριστη ή εν μέρει εσφαλμένη κάλυψη· \
"missing" όταν το στοιχείο απουσιάζει ή είναι νομικά εσφαλμένο· \
"not_applicable" ΜΟΝΟ όταν το κριτήριο εκ φύσεως δεν αφορά το συγκεκριμένο \
έγγραφο (π.χ. δικαστικό ένσημο σε αναγνωριστική αγωγή).
- score: 0-100, αυστηρά. Το 100 προϋποθέτει άψογη κάλυψη· κάλυψη με αοριστίες \
ή κενά βαθμολογείται κάτω από 70.
- evidence: αυτούσιο απόσπασμα έως 30 λέξεων που θεμελιώνει την κρίση, ή null \
όταν διαπιστώνεις απουσία.
- commentary: αιτιολογημένη νομική κρίση — τι υπάρχει, τι λείπει, ποια η \
δικονομική/ουσιαστική συνέπεια της έλλειψης.

Στα extra_findings κατέγραψε κάθε ουσιώδες πρόβλημα που δεν καλύπτεται από τα \
κριτήρια (π.χ. εσωτερικές αντιφάσεις, εσφαλμένη επίκληση διάταξης, παραγραφή \
που προκύπτει από τα ίδια τα εκτιθέμενα, επικίνδυνες ομολογίες).

Στα suggestions δώσε ιεραρχημένες, άμεσα εφαρμόσιμες βελτιώσεις. Όπου η \
βελτίωση αφορά διατύπωση, πρότεινε συγκεκριμένη διατύπωση σε δικανικό ύφος.

Στο overall_assessment συνόψισε τη συνολική σου κρίση σε 2-4 παραγράφους \
ρέοντος ελληνικού νομικού λόγου, χωρίς λίστες και χωρίς αριθμητικούς βαθμούς: \
πού στέκει το δικόγραφο, πού κινδυνεύει, τι προέχει να διορθωθεί.
"""


async def audit(
    client: AsyncAnthropic,
    settings: Settings,
    document: dict[str, Any],
    classification: DocumentClassification,
    criteria: list[Criterion],
    expert: ExpertProfile,
) -> AuditModelOutput:
    task = AUDIT_TASK_TEMPLATE.format(
        label=classification.label,
        branch=classification.branch,
        purpose=classification.purpose,
        stage=classification.procedural_stage or "δεν προσδιορίζεται",
        checklist=_render_checklist(criteria),
    )
    return await _structured_call(
        client,
        settings,
        system_prompt=build_audit_system_prompt(expert),
        document=document,
        task=task,
        output_model=AuditModelOutput,
        effort=settings.audit_effort,
    )


# ---------------------------------------------------------------------------
# Ορχήστρωση
# ---------------------------------------------------------------------------


def _build_report(
    settings: Settings,
    classification: DocumentClassification,
    criteria: list[Criterion],
    audit_output: AuditModelOutput,
    expert: ExpertProfile,
) -> AuditReport:
    crit_by_id = {c.id: c for c in criteria}
    # Κρατάμε μόνο αξιολογήσεις που αντιστοιχούν σε πραγματικά κριτήρια·
    # τυχόν πλεονάζουσες αγνοούνται, ώστε η βαθμολόγηση να μένει ελέγξιμη.
    valid_evals = [e for e in audit_output.evaluations if e.criterion_id in crit_by_id]
    score = compute_score(criteria, valid_evals)

    criteria_reports = []
    for ev in valid_evals:
        crit = crit_by_id[ev.criterion_id]
        criteria_reports.append(
            CriterionReport(
                criterion_id=crit.id,
                category=crit.category.value,
                category_label=CATEGORY_LABELS[crit.category],
                text=crit.text,
                critical=crit.critical,
                weight=crit.weight,
                status=ev.status,
                score=ev.score,
                evidence=ev.evidence,
                commentary=ev.commentary,
            )
        )

    return AuditReport(
        classification=classification,
        auditor=AuditorInfo(
            branch=expert.branch,
            title=expert.title,
            description=expert.description,
        ),
        score=score,
        criteria=criteria_reports,
        extra_findings=audit_output.extra_findings,
        suggestions=audit_output.suggestions,
        overall_assessment=audit_output.overall_assessment,
        model=settings.model,
    )


def _validate_input(text: str, settings: Settings) -> str:
    cleaned = text.strip()
    if len(cleaned) < settings.min_document_chars:
        raise PipelineError(
            "Το κείμενο είναι πολύ σύντομο για ουσιαστικό έλεγχο "
            f"(ελάχιστο: {settings.min_document_chars} χαρακτήρες)."
        )
    if len(cleaned) > settings.max_document_chars:
        raise PipelineError(
            "Το κείμενο υπερβαίνει το μέγιστο μέγεθος "
            f"({settings.max_document_chars} χαρακτήρες)."
        )
    return cleaned


async def run_pipeline_events(
    text: str,
    context: str | None = None,
    doc_type_hint: str | None = None,
) -> AsyncIterator[tuple[str, Any]]:
    """Εκτελεί το pipeline εκπέμποντας γεγονότα προόδου.

    Γεγονότα: (stage, payload) όπου stage ∈ {classifying, classified,
    auditing, complete}.
    """
    settings = get_settings()
    cleaned = _validate_input(text, settings)
    document = _document_block(cleaned, context)

    async with AsyncAnthropic() as client:
        yield "classifying", None
        if doc_type_hint and doc_type_hint in checklists.DOCUMENT_TYPES:
            spec = checklists.DOCUMENT_TYPES[doc_type_hint]
            classification = DocumentClassification(
                doc_type=spec.key,
                branch=spec.branch,  # type: ignore[arg-type]
                label=spec.label,
                purpose="Καθορίστηκε από τον χρήστη.",
                court_or_authority=None,
                procedural_stage=None,
                summary="Το είδος του εγγράφου ορίστηκε ρητά από τον χρήστη.",
                confidence="high",
            )
        else:
            classification = await classify(client, settings, document)
        yield "classified", classification

        # Δρομολόγηση στον ειδικό του κλάδου — ο ποινικολόγος δεν ελέγχει
        # διοικητικά δικόγραφα και αντιστρόφως.
        expert = expert_for(classification.branch)
        criteria = checklists.criteria_for(classification.doc_type)
        yield (
            "auditing",
            {
                "criteria_count": len(criteria),
                "auditor": {
                    "branch": expert.branch,
                    "title": expert.title,
                    "description": expert.description,
                },
            },
        )
        audit_output = await audit(
            client, settings, document, classification, criteria, expert
        )

        report = _build_report(settings, classification, criteria, audit_output, expert)
        yield "complete", report


async def run_pipeline(
    text: str,
    context: str | None = None,
    doc_type_hint: str | None = None,
) -> AuditReport:
    report: AuditReport | None = None
    async for stage, payload in run_pipeline_events(text, context, doc_type_hint):
        if stage == "complete":
            report = payload
    assert report is not None
    return report


def sse_event(stage: str, payload: Any) -> str:
    """Σειριοποίηση γεγονότος pipeline σε γραμμή SSE."""
    if isinstance(payload, BaseModel):
        data = payload.model_dump(mode="json")
    else:
        data = payload
    body = json.dumps({"stage": stage, "data": data}, ensure_ascii=False)
    return f"data: {body}\n\n"

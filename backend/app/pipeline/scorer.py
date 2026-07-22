"""Ντετερμινιστική βαθμολόγηση: το μοντέλο κρίνει ανά κριτήριο, ο κώδικας αθροίζει.

Κανόνες:
- Βαθμός κατηγορίας = σταθμισμένος μέσος όρος των εφαρμοστέων κριτηρίων της.
- Συνολικός βαθμός = σταθμισμένος μέσος των κατηγοριών (τα βάρη κατηγοριών
  χωρίς εφαρμοστέα κριτήρια ανακατανέμονται αναλογικά).
- Κρίσιμο κριτήριο με status "missing" → οροφή 45%. Με "partially_met" → οροφή 70%.
  Η αυστηρότερη οροφή υπερισχύει.
"""

from app.pipeline.checklists import (
    CATEGORY_LABELS,
    CATEGORY_WEIGHTS,
    Category,
    Criterion,
)
from app.schemas import CategoryScore, CriterionEvaluation, ScoreSummary

CAP_MISSING_CRITICAL = 45.0
CAP_PARTIAL_CRITICAL = 70.0

VERDICT_BANDS: list[tuple[float, str, str]] = [
    (
        90.0,
        "Άρτιο",
        "Το δικόγραφο πληροί τις τυπικές και ουσιαστικές προϋποθέσεις· επιδέχεται μόνο επουσιώδεις βελτιώσεις.",
    ),
    (
        75.0,
        "Πλήρες με βελτιώσεις",
        "Το δικόγραφο είναι κατ' αρχήν άρτιο, πλην όμως συνιστώνται στοχευμένες βελτιώσεις πριν την κατάθεση.",
    ),
    (
        60.0,
        "Επαρκές με ουσιώδεις ελλείψεις",
        "Το δικόγραφο χρήζει ουσιωδών συμπληρώσεων· η κατάθεση ως έχει ενέχει δικονομικό κίνδυνο.",
    ),
    (
        40.0,
        "Ελλιπές",
        "Σοβαρές ελλείψεις πλήττουν το ορισμένο ή το παραδεκτό· απαιτείται ουσιώδης ανασύνταξη.",
    ),
    (
        0.0,
        "Ακατάλληλο προς κατάθεση",
        "Το έγγραφο, ως έχει, δεν εξυπηρετεί τον δικονομικό του σκοπό και πρέπει να ανασυνταχθεί εξ αρχής.",
    ),
]


def _verdict(overall: float) -> tuple[str, str]:
    for threshold, verdict, detail in VERDICT_BANDS:
        if overall >= threshold:
            return verdict, detail
    return VERDICT_BANDS[-1][1], VERDICT_BANDS[-1][2]


def compute_score(
    criteria: list[Criterion],
    evaluations: list[CriterionEvaluation],
) -> ScoreSummary:
    by_id = {e.criterion_id: e for e in evaluations}

    # Ανά κατηγορία: σταθμισμένος μέσος των εφαρμοστέων κριτηρίων.
    cat_scores: dict[Category, float | None] = {}
    cat_counts: dict[Category, int] = {}
    for cat in Category:
        total_weight = 0.0
        weighted_sum = 0.0
        count = 0
        for crit in criteria:
            if crit.category is not cat:
                continue
            ev = by_id.get(crit.id)
            if ev is None or ev.status == "not_applicable":
                continue
            total_weight += crit.weight
            weighted_sum += crit.weight * ev.score
            count += 1
        cat_counts[cat] = count
        cat_scores[cat] = (weighted_sum / total_weight) if total_weight > 0 else None

    # Συνολικός βαθμός με ανακατανομή βαρών κενών κατηγοριών.
    active_weight = sum(
        CATEGORY_WEIGHTS[cat] for cat in Category if cat_scores[cat] is not None
    )
    if active_weight > 0:
        overall = sum(
            CATEGORY_WEIGHTS[cat] * score
            for cat, score in cat_scores.items()
            if score is not None
        ) / active_weight
    else:
        overall = 0.0

    # Οροφές λόγω κρίσιμων κριτηρίων.
    capped = False
    cap_reason: str | None = None
    cap_value = 100.0
    for crit in criteria:
        if not crit.critical:
            continue
        ev = by_id.get(crit.id)
        if ev is None:
            continue
        if ev.status == "missing" and cap_value > CAP_MISSING_CRITICAL:
            cap_value = CAP_MISSING_CRITICAL
            cap_reason = (
                f"Πλήρης απουσία κρίσιμου στοιχείου («{crit.id}»): "
                "η βαθμολογία περιορίζεται λόγω κινδύνου απαραδέκτου/αοριστίας."
            )
        elif ev.status == "partially_met" and cap_value > CAP_PARTIAL_CRITICAL:
            cap_value = CAP_PARTIAL_CRITICAL
            cap_reason = (
                f"Ατελής κάλυψη κρίσιμου στοιχείου («{crit.id}»): "
                "η βαθμολογία περιορίζεται μέχρι τη θεραπεία της έλλειψης."
            )
    if overall > cap_value:
        overall = cap_value
        capped = True
    else:
        cap_reason = None

    overall = round(overall, 1)
    verdict, detail = _verdict(overall)

    return ScoreSummary(
        overall=overall,
        verdict=verdict,
        verdict_detail=detail,
        capped=capped,
        cap_reason=cap_reason if capped else None,
        categories=[
            CategoryScore(
                category=cat.value,
                label=CATEGORY_LABELS[cat],
                weight=CATEGORY_WEIGHTS[cat],
                score=round(cat_scores[cat], 1) if cat_scores[cat] is not None else None,
                criteria_count=cat_counts[cat],
            )
            for cat in Category
        ],
    )

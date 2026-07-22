from app.pipeline.checklists import Category, Criterion
from app.pipeline.scorer import (
    CAP_MISSING_CRITICAL,
    CAP_PARTIAL_CRITICAL,
    compute_score,
)
from app.schemas import CriterionEvaluation


def _crit(cid, cat, weight=1.0, critical=False):
    return Criterion(id=cid, category=cat, text="τεστ", weight=weight, critical=critical)


def _ev(cid, status="met", score=100):
    return CriterionEvaluation(
        criterion_id=cid, status=status, score=score, evidence=None, commentary="τεστ"
    )


def _one_per_category(score=100):
    criteria = [
        _crit("f", Category.FORMAL),
        _crit("s", Category.SUBSTANTIVE),
        _crit("g", Category.GROUNDING),
        _crit("l", Category.LANGUAGE),
    ]
    evals = [_ev(c.id, score=score) for c in criteria]
    return criteria, evals


def test_perfect_score():
    criteria, evals = _one_per_category(100)
    summary = compute_score(criteria, evals)
    assert summary.overall == 100.0
    assert summary.verdict == "Άρτιο"
    assert not summary.capped


def test_zero_score():
    criteria = [
        _crit("f", Category.FORMAL),
        _crit("s", Category.SUBSTANTIVE),
        _crit("g", Category.GROUNDING),
        _crit("l", Category.LANGUAGE),
    ]
    evals = [_ev(c.id, status="missing", score=0) for c in criteria]
    summary = compute_score(criteria, evals)
    assert summary.overall == 0.0
    assert summary.verdict == "Ακατάλληλο προς κατάθεση"


def test_weighted_average_within_category():
    criteria = [
        _crit("a", Category.FORMAL, weight=1.0),
        _crit("b", Category.FORMAL, weight=3.0),
    ]
    evals = [_ev("a", score=100), _ev("b", score=0, status="missing")]
    summary = compute_score(criteria, evals)
    formal = next(c for c in summary.categories if c.category == "formal")
    assert formal.score == 25.0


def test_not_applicable_excluded():
    criteria = [
        _crit("a", Category.FORMAL),
        _crit("b", Category.FORMAL),
    ]
    evals = [_ev("a", score=80), _ev("b", status="not_applicable", score=0)]
    summary = compute_score(criteria, evals)
    formal = next(c for c in summary.categories if c.category == "formal")
    assert formal.score == 80.0
    assert formal.criteria_count == 1


def test_empty_category_weight_redistributed():
    # Μόνο FORMAL έχει εφαρμοστέο κριτήριο με 80 → συνολικό 80 (όχι 80*0.25).
    criteria = [_crit("a", Category.FORMAL)]
    evals = [_ev("a", score=80)]
    summary = compute_score(criteria, evals)
    assert summary.overall == 80.0


def test_missing_critical_caps_score():
    criteria, evals = _one_per_category(100)
    criteria.append(_crit("crit", Category.FORMAL, critical=True))
    evals.append(_ev("crit", status="missing", score=0))
    summary = compute_score(criteria, evals)
    assert summary.capped
    assert summary.overall <= CAP_MISSING_CRITICAL
    assert summary.cap_reason is not None


def test_partial_critical_caps_score():
    criteria, evals = _one_per_category(100)
    criteria.append(_crit("crit", Category.SUBSTANTIVE, critical=True))
    evals.append(_ev("crit", status="partially_met", score=60))
    summary = compute_score(criteria, evals)
    assert summary.capped
    assert summary.overall <= CAP_PARTIAL_CRITICAL


def test_missing_cap_stricter_than_partial():
    criteria, evals = _one_per_category(100)
    criteria.append(_crit("c1", Category.FORMAL, critical=True))
    criteria.append(_crit("c2", Category.FORMAL, critical=True))
    evals.append(_ev("c1", status="partially_met", score=60))
    evals.append(_ev("c2", status="missing", score=0))
    summary = compute_score(criteria, evals)
    assert summary.overall <= CAP_MISSING_CRITICAL


def test_cap_not_applied_when_below_cap():
    criteria, evals = _one_per_category(30)
    criteria.append(_crit("crit", Category.FORMAL, critical=True))
    evals.append(_ev("crit", status="missing", score=0))
    summary = compute_score(criteria, evals)
    assert not summary.capped
    assert summary.cap_reason is None


def test_unknown_evaluations_ignored():
    criteria, evals = _one_per_category(100)
    evals.append(_ev("ghost", score=0, status="missing"))
    # Το ghost δεν είναι στα κριτήρια — δεν επηρεάζει.
    summary = compute_score(criteria, [e for e in evals if e.criterion_id != "ghost"])
    assert summary.overall == 100.0


def test_score_clamped_by_schema():
    ev = CriterionEvaluation(
        criterion_id="x", status="met", score=150, evidence=None, commentary="τ"
    )
    assert ev.score == 100
    ev2 = CriterionEvaluation(
        criterion_id="x", status="missing", score=-10, evidence=None, commentary="τ"
    )
    assert ev2.score == 0


def test_verdict_bands():
    bands = [
        (95, "Άρτιο"),
        (80, "Πλήρες με βελτιώσεις"),
        (65, "Επαρκές με ουσιώδεις ελλείψεις"),
        (45, "Ελλιπές"),
        (20, "Ακατάλληλο προς κατάθεση"),
    ]
    for score, expected in bands:
        criteria, evals = _one_per_category(score)
        summary = compute_score(criteria, evals)
        assert summary.verdict == expected, f"score={score}"

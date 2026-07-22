from app.pipeline.checklists import Category, Criterion
from app.pipeline.engine import FIRM_REVIEW_TASK, FIRM_REVIEWER_SYSTEM_PROMPT
from app.pipeline.scorer import (
    FIRM_CAP_AI_MARKED,
    FIRM_CAP_BORDERLINE,
    apply_firm_standard,
    compute_score,
)
from app.schemas import CriterionEvaluation, FirmStandardReview


def _summary(score: int):
    criteria = [
        Criterion(id="f", category=Category.FORMAL, text="τ"),
        Criterion(id="s", category=Category.SUBSTANTIVE, text="τ"),
        Criterion(id="g", category=Category.GROUNDING, text="τ"),
        Criterion(id="l", category=Category.LANGUAGE, text="τ"),
    ]
    evals = [
        CriterionEvaluation(
            criterion_id=c.id, status="met", score=score, evidence=None, commentary="τ"
        )
        for c in criteria
    ]
    return compute_score(criteria, evals)


def test_human_register_leaves_score_untouched():
    summary = apply_firm_standard(_summary(100), "human_register")
    assert summary.overall == 100.0
    assert summary.firm_standard == "human_register"
    assert not summary.capped


def test_ai_marked_caps_below_adequate():
    summary = apply_firm_standard(_summary(100), "ai_marked")
    assert summary.overall == FIRM_CAP_AI_MARKED
    assert summary.capped
    assert summary.verdict == "Ελλιπές"
    assert summary.cap_reason and "AI" in summary.cap_reason


def test_borderline_blocks_exemplary_verdict():
    summary = apply_firm_standard(_summary(100), "borderline")
    assert summary.overall == FIRM_CAP_BORDERLINE
    assert summary.verdict != "Άρτιο"
    assert summary.capped


def test_cap_not_applied_below_threshold():
    summary = apply_firm_standard(_summary(40), "ai_marked")
    assert summary.overall == 40.0
    assert not summary.capped
    assert summary.firm_standard == "ai_marked"


def test_firm_cap_reason_appends_to_existing():
    base = _summary(100).model_copy(
        update={"capped": True, "cap_reason": "Υφιστάμενος λόγος."}
    )
    summary = apply_firm_standard(base, "ai_marked")
    assert summary.cap_reason is not None
    assert summary.cap_reason.startswith("Υφιστάμενος λόγος.")
    assert "AI" in summary.cap_reason


def test_register_score_clamped():
    review = FirmStandardReview(
        authenticity_verdict="human_register",
        register_score=250,
        ai_tell_findings=[],
        exemplary_gaps=[],
        assessment="τ",
    )
    assert review.register_score == 100


def test_reviewer_prompt_covers_tell_families():
    for token in ["Δομικές", "Φρασεολογικές", "Ρυθμού", "Ύφους", "Τεκμηρίωσης"]:
        assert token in FIRM_REVIEWER_SYSTEM_PROMPT
    # Το πρότυπο απαιτεί ρητά και τα δύο σκέλη: υποδειγματικό + όχι AI.
    assert "ΥΠΟΔΕΙΓΜΑΤΙΚΑ" in FIRM_REVIEWER_SYSTEM_PROMPT
    assert "AI" in FIRM_REVIEWER_SYSTEM_PROMPT
    assert "authenticity_verdict" in FIRM_REVIEW_TASK

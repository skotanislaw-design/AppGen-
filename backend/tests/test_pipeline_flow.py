"""End-to-end έλεγχος ροής pipeline με προσομοιωμένο μοντέλο (χωρίς κόστος API).

Επαληθεύει ότι η ενορχήστρωση δένει σωστά: ταξινόμηση → δρομολόγηση στον
ειδικό του κλάδου → ντετερμινιστική βαθμολόγηση (scorer) → αναφορά, καθώς
και η συσσώρευση usage και η εφαρμογή της οροφής κρίσιμου κριτηρίου.
"""

import pytest

from app.pipeline import checklists, engine
from app.schemas import (
    AuditModelOutput,
    CriterionEvaluation,
    DocumentClassification,
    ExtraFinding,
    FirmStandardReview,
    Suggestion,
)


class _Usage:
    def __init__(self, i: int, o: int):
        self.input_tokens = i
        self.output_tokens = o
        self.cache_read_input_tokens = 0
        self.cache_creation_input_tokens = 0


class _Block:
    type = "text"

    def __init__(self, text: str):
        self.text = text


class _Resp:
    stop_reason = "end_turn"

    def __init__(self, text: str, usage: _Usage):
        self.content = [_Block(text)]
        self.usage = usage


class _Messages:
    def __init__(self, responses):
        self._responses = responses
        self._i = 0

    async def create(self, **kwargs):
        r = self._responses[self._i]
        self._i += 1
        return r


class _Client:
    def __init__(self, responses):
        self.messages = _Messages(responses)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


def _classification_json() -> str:
    return DocumentClassification(
        doc_type="agogi",
        branch="civil",
        label="Αγωγή",
        purpose="Καταψηφιστική αξίωση αμοιβής.",
        court_or_authority="Μονομελές Πρωτοδικείο",
        procedural_stage="Πρώτος βαθμός",
        summary="Αγωγή αμοιβής εργολάβου.",
        confidence="high",
    ).model_dump_json()


def _audit_json(missing_critical: bool) -> str:
    criteria = checklists.criteria_for("agogi")
    evals = []
    flipped = False
    for c in criteria:
        status, score = "met", 100
        if missing_critical and c.critical and not flipped:
            status, score = "missing", 0
            flipped = True
        evals.append(
            CriterionEvaluation(
                criterion_id=c.id, status=status, score=score,
                evidence=None, commentary="τεστ",
            )
        )
    return AuditModelOutput(
        evaluations=evals,
        extra_findings=[ExtraFinding(title="τ", severity="minor", commentary="τ")],
        suggestions=[Suggestion(priority="low", target="τ", proposed_action="τ", rationale="τ")],
        overall_assessment="Συνολική κρίση.",
    ).model_dump_json()


def _firm_json() -> str:
    return FirmStandardReview(
        authenticity_verdict="human_register",
        register_score=95,
        ai_tell_findings=[],
        exemplary_gaps=[],
        assessment="Φυσικός δικανικός λόγος.",
    ).model_dump_json()


def _patch_model(monkeypatch, *, missing_critical: bool):
    # Προσομοίωση ρυθμισμένου deployment (το engine ελέγχει το κλειδί νωρίς).
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    responses = [
        _Resp(_classification_json(), _Usage(100, 200)),   # classify
        _Resp(_audit_json(missing_critical), _Usage(300, 400)),  # audit
        _Resp(_firm_json(), _Usage(50, 60)),               # firm review
    ]
    monkeypatch.setattr(engine, "AsyncAnthropic", lambda *a, **k: _Client(responses))


DOC = "Ενώπιον του Μονομελούς Πρωτοδικείου. " + ("Το ιστορικό της υποθέσεως. " * 20)


@pytest.mark.anyio
async def test_full_flow_routes_and_scores(monkeypatch):
    _patch_model(monkeypatch, missing_critical=False)
    report, usage = await engine.run_pipeline_with_usage(DOC)

    # Ταξινόμηση & δρομολόγηση στον ειδικό του κλάδου
    assert report.classification.doc_type == "agogi"
    assert report.auditor.branch == "civil"
    assert "στικολ" in report.auditor.title.lower() or "Αστικ" in report.auditor.title

    # Άρτια κάλυψη → 100, καμία οροφή
    assert report.score.overall == 100.0
    assert report.score.verdict == "Άρτιο"
    assert not report.score.capped
    assert report.score.firm_standard == "human_register"

    # Πλήρης αναφορά
    assert len(report.criteria) == len(checklists.criteria_for("agogi"))
    assert report.suggestions and report.extra_findings

    # Συσσώρευση usage και των 3 κλήσεων
    assert usage["calls"] == 3
    assert usage["input_tokens"] == 450
    assert usage["output_tokens"] == 660
    assert usage["model"] == engine.get_settings().model


@pytest.mark.anyio
async def test_missing_critical_caps_score_end_to_end(monkeypatch):
    _patch_model(monkeypatch, missing_critical=True)
    report, _ = await engine.run_pipeline_with_usage(DOC)
    assert report.score.capped
    assert report.score.overall <= 45.0
    assert report.score.cap_reason


@pytest.mark.anyio
async def test_doc_type_hint_skips_classification(monkeypatch):
    # Με ρητό είδος, η ταξινόμηση παρακάμπτεται → 2 κλήσεις (audit + firm).
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    responses = [
        _Resp(_audit_json(False), _Usage(300, 400)),
        _Resp(_firm_json(), _Usage(50, 60)),
    ]
    monkeypatch.setattr(engine, "AsyncAnthropic", lambda *a, **k: _Client(responses))
    report, usage = await engine.run_pipeline_with_usage(DOC, doc_type_hint="agogi")
    assert report.classification.doc_type == "agogi"
    assert usage["calls"] == 2
    assert report.auditor.branch == "civil"


@pytest.mark.anyio
async def test_missing_api_key_raises_clean_pipeline_error(monkeypatch):
    # Χωρίς κλειδί, ο έλεγχος αποτυγχάνει με καθαρό PipelineError (→ 422 στο API),
    # όχι με ασαφές TypeError/500.
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    with pytest.raises(engine.PipelineError) as exc:
        await engine.run_pipeline_with_usage(DOC)
    assert "ANTHROPIC_API_KEY" in str(exc.value)


@pytest.fixture
def anyio_backend():
    return "asyncio"

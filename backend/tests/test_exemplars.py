from app.exemplars import EXEMPLARS, exemplar_for
from app.pipeline import checklists
from app.pipeline.engine import EXEMPLAR_REFERENCE_TEMPLATE


def test_exemplar_keys_are_registered_doc_types():
    for key in EXEMPLARS:
        assert key in checklists.DOCUMENT_TYPES, f"Άγνωστο είδος: {key}"


def test_all_branches_covered():
    branches = {checklists.get_spec(k).branch for k in EXEMPLARS}
    assert {"penal", "civil", "administrative", "extrajudicial"} <= branches


def test_bodies_are_substantial():
    for key, ex in EXEMPLARS.items():
        assert len(ex.body) > 2000, f"Ρηχό υπόδειγμα: {key}"


def test_bodies_carry_firm_signature_block():
    for key, ex in EXEMPLARS.items():
        assert "ΧΡΗΣΤΟΣ ΣΚΟΤΑΝΗΣ" in ex.body, key
        assert "ΑΜ ΔΣΣ 228" in ex.body, key


def test_bodies_have_no_bullet_lists():
    # Δόγμα γραφείου: καμία κουκκίδα/λίστα στο σώμα δικογράφου.
    for key, ex in EXEMPLARS.items():
        assert "•" not in ex.body, key
        for line in ex.body.splitlines():
            assert not line.strip().startswith(("- ", "* ")), (
                f"Λίστα στο σώμα του {key}: {line[:60]}"
            )


def test_case_law_is_never_invented():
    # Η νομολογία σημειώνεται πάντοτε ως [ΣΥΜΠΛΗΡΩΣΤΕ] — ποτέ με έτοιμο
    # αριθμό αποφάσεως που δεν έχει επαληθευθεί.
    import re

    pattern = re.compile(r"(ΑΠ|ΣτΕ|ΔΕφ|ΜΠρ|ΕφΑθ)\s+\d+/\d{4}")
    for key, ex in EXEMPLARS.items():
        assert not pattern.search(ex.body), f"Επινοημένη νομολογία στο {key}"


def test_placeholders_use_firm_convention():
    for key, ex in EXEMPLARS.items():
        assert "[ΣΥΜΠΛΗΡΩΣΤΕ" in ex.body, f"Χωρίς σημεία εξατομίκευσης: {key}"


def test_drafting_notes_cover_economy():
    for key, ex in EXEMPLARS.items():
        assert len(ex.drafting_notes) >= 3, key
        joined = " ".join(ex.drafting_notes)
        assert "οικονομία" in joined, f"Χωρίς σημείωση δομικής οικονομίας: {key}"


def test_key_provisions_non_empty():
    for key, ex in EXEMPLARS.items():
        assert ex.key_provisions, key


def test_exemplar_for_missing_type_returns_none():
    assert exemplar_for("nonexistent") is None
    assert exemplar_for("generic") is None


def test_reference_template_forbids_verbatim_matching():
    assert "ΜΗΝ απαιτείς λεκτική ταύτιση" in EXEMPLAR_REFERENCE_TEMPLATE
    assert "{body}" in EXEMPLAR_REFERENCE_TEMPLATE

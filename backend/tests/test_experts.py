from app.pipeline import checklists
from app.pipeline.engine import (
    COMMON_AUDIT_RULES,
    TRIAGE_SYSTEM_PROMPT,
    build_audit_system_prompt,
)
from app.pipeline.experts import EXPERTS, expert_for

ALL_BRANCHES = {"penal", "civil", "administrative", "extrajudicial", "generic"}


def test_every_branch_has_expert():
    assert set(EXPERTS.keys()) == ALL_BRANCHES


def test_every_registered_doc_type_branch_has_expert():
    for spec in checklists.DOCUMENT_TYPES.values():
        assert spec.branch in EXPERTS, f"Χωρίς ειδικό ο κλάδος {spec.branch}"


def test_expert_for_falls_back_to_generic():
    assert expert_for("unknown_branch").branch == "generic"


def test_expert_profiles_complete():
    for profile in EXPERTS.values():
        assert profile.title.strip()
        assert profile.description.strip()
        assert len(profile.identity) > 300, (
            f"Ρηχό γνωστικό προφίλ για τον κλάδο {profile.branch}"
        )


def test_experts_are_distinct():
    identities = [p.identity for p in EXPERTS.values()]
    assert len(identities) == len(set(identities))
    titles = [p.title for p in EXPERTS.values()]
    assert len(titles) == len(set(titles))


def test_audit_system_prompt_composes_identity_and_rules():
    for profile in EXPERTS.values():
        prompt = build_audit_system_prompt(profile)
        assert profile.identity in prompt
        assert COMMON_AUDIT_RULES in prompt


def test_triage_prompt_is_not_an_audit_prompt():
    # Ο υπεύθυνος διαλογής ταξινομεί — δεν αξιολογεί.
    assert "ταξινόμηση" in TRIAGE_SYSTEM_PROMPT
    assert TRIAGE_SYSTEM_PROMPT not in [p.identity for p in EXPERTS.values()]


def test_branch_expertise_signals():
    # Κάθε ειδικός αναφέρει τα θεμελιώδη νομοθετήματα του κλάδου του.
    signals = {
        "penal": ["ΠΚ", "ΚΠΔ"],
        "civil": ["ΑΚ", "ΚΠολΔ"],
        "administrative": ["ΚΔιοικΔ", "ΠΔ 18/1989"],
        "extrajudicial": ["ΑΚ"],
    }
    for branch, keywords in signals.items():
        identity = EXPERTS[branch].identity
        for kw in keywords:
            assert kw in identity, f"Ο ειδικός {branch} δεν αναφέρει {kw}"

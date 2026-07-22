from app.pipeline import checklists
from app.pipeline.checklists import CATEGORY_WEIGHTS, Category


def test_category_weights_sum_to_one():
    assert abs(sum(CATEGORY_WEIGHTS.values()) - 1.0) < 1e-9


def test_all_criterion_ids_unique_per_type():
    for key in checklists.DOCUMENT_TYPES:
        ids = [c.id for c in checklists.criteria_for(key)]
        assert len(ids) == len(set(ids)), f"Διπλά criterion ids στο είδος {key}"


def test_every_type_has_universal_criteria():
    for key in checklists.DOCUMENT_TYPES:
        criteria = checklists.criteria_for(key)
        assert len(criteria) >= len(checklists.UNIVERSAL_CRITERIA)


def test_every_type_has_critical_criterion():
    for key in checklists.DOCUMENT_TYPES:
        assert any(c.critical for c in checklists.criteria_for(key))


def test_weights_positive():
    for key in checklists.DOCUMENT_TYPES:
        assert all(c.weight > 0 for c in checklists.criteria_for(key))


def test_specific_types_have_own_criteria():
    for key, spec in checklists.DOCUMENT_TYPES.items():
        if key == "generic":
            continue
        assert spec.criteria, f"Το είδος {key} δεν έχει ειδικά κριτήρια"


def test_get_spec_falls_back_to_generic():
    assert checklists.get_spec("nonexistent").key == "generic"


def test_classification_menu_lists_all_types():
    menu = checklists.classification_menu()
    for key in checklists.DOCUMENT_TYPES:
        assert key in menu


def test_all_categories_represented_in_universal():
    cats = {c.category for c in checklists.UNIVERSAL_CRITERIA}
    assert cats == set(Category)

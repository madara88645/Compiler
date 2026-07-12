from app.emitters import _domain_suggestions_v2
from app.models_v2 import IRv2


def _ir_with_suggestions(raw):
    return IRv2(metadata={"domain_suggestions": raw})


def test_domain_suggestions_v2_empty_metadata_returns_empty():
    assert _domain_suggestions_v2(IRv2()) == []


def test_domain_suggestions_v2_non_list_metadata_returns_empty():
    ir = IRv2(metadata={"domain_suggestions": "not-a-list"})
    assert _domain_suggestions_v2(ir) == []


def test_domain_suggestions_v2_sorts_by_priority_descending():
    ir = _ir_with_suggestions(
        [
            {"text": "low priority item", "priority": 1},
            {"text": "high priority item", "priority": 5},
            {"text": "mid priority item", "priority": 3},
        ]
    )
    assert _domain_suggestions_v2(ir) == [
        "high priority item",
        "mid priority item",
        "low priority item",
    ]


def test_domain_suggestions_v2_dedupes_case_insensitively():
    ir = _ir_with_suggestions(
        [
            {"text": "Add tests", "priority": 1},
            {"text": "add tests", "priority": 2},
        ]
    )
    assert len(_domain_suggestions_v2(ir)) == 1


def test_domain_suggestions_v2_respects_limit():
    ir = _ir_with_suggestions([{"text": f"item {i}", "priority": i} for i in range(5)])
    assert len(_domain_suggestions_v2(ir, limit=2)) == 2


def test_domain_suggestions_v2_skips_non_dict_entries_and_missing_priority():
    ir = _ir_with_suggestions(["not-a-dict", {"text": "valid entry"}])
    assert _domain_suggestions_v2(ir) == ["valid entry"]

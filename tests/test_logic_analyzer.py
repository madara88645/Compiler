from app.heuristics.logic_analyzer import LogicAnalyzer


def test_detect_negations_preserves_later_negations_in_same_sentence():
    analyzer = LogicAnalyzer()

    negations = analyzer.detect_negations(
        "Do not use JOIN operations and do not nest subqueries."
    )

    assert len(negations) == 1
    assert negations[0].negation_word == "do not"
    assert negations[0].stripped_text == "use JOIN operations and do not nest subqueries."
    assert negations[0].anti_pattern == "Instead: use JOIN operations and do not nest subqueries."


def test_detect_dependencies_keeps_because_matches_with_fast_path():
    analyzer = LogicAnalyzer()

    dependencies = analyzer.detect_dependencies(
        ["Cache the API response because repeated calls are expensive."]
    )

    assert len(dependencies) == 1
    assert dependencies[0].dependency_type == "because"
    assert dependencies[0].action == "Cache the API response"
    assert dependencies[0].reason == "repeated calls are expensive."


def test_detect_dependencies_skips_sentences_without_dependency_keywords():
    analyzer = LogicAnalyzer()

    dependencies = analyzer.detect_dependencies(["Cache the API response for later reuse."])

    assert dependencies == []

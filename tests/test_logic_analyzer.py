from app.heuristics.logic_analyzer import LogicAnalyzer


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

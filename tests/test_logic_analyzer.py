from app.heuristics.logic_analyzer import (
    LogicAnalyzer,
    NegativeConstraint,
    DependencyRule,
    MissingInfo,
    IOMapping,
    analyze_prompt_logic,
)


def test_detect_negations_preserves_later_negations_in_same_sentence():
    analyzer = LogicAnalyzer()

    negations = analyzer.detect_negations("Do not use JOIN operations and do not nest subqueries.")

    assert len(negations) == 1
    assert negations[0].negation_word == "do not"
    assert negations[0].stripped_text == "use JOIN operations and do not nest subqueries."
    assert negations[0].anti_pattern == "Do not: use JOIN operations and do not nest subqueries."


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


def test_detect_negations_skips_sentences_without_negation_keywords():
    analyzer = LogicAnalyzer()

    negations = analyzer.detect_negations("Cache the API response for later reuse.")

    assert negations == []


def test_analyze_method_and_convenience_function():
    # Test analyze_prompt_logic convenience function and analyze method
    result = analyze_prompt_logic("Do not use JOIN because it is slow.")
    assert len(result.negations) == 1
    assert len(result.dependencies) == 1

    # Verify analyze method with maximize_recall=False
    analyzer = LogicAnalyzer(maximize_recall=False)
    res = analyzer.analyze("Do not use JOIN because it is slow.")
    assert len(res.negations) == 1


def test_detect_negations_edge_cases():
    analyzer = LogicAnalyzer()

    # 1. Null sentences parameter (splits internally)
    negations = analyzer.detect_negations("Never query all columns.")
    assert len(negations) == 1
    assert negations[0].negation_word == "never"
    assert negations[0].anti_pattern == "Never: query all columns."

    # 2. Duplicate sentences seen
    negations_dup = analyzer.detect_negations(
        "Never query all columns.",
        sentences=["Never query all columns.", "Never query all columns."],
    )
    assert len(negations_dup) == 1

    # 3. Test different negation types / anti-pattern mapping.
    # Every restatement must keep the user's polarity — see
    # test_anti_pattern_never_inverts_the_users_requirement below.
    words_to_test = [
        ("avoid nested loops.", "avoid", "Avoid: nested loops."),
        ("you must not use global vars.", "must not", "Must not: use global vars."),
        ("cannot access disk.", "cannot", "Must not: access disk."),
        ("exclude draft results.", "exclude", "Exclude: draft results."),
        # Conditionals keep the sentence verbatim — see
        # test_conditional_negations_keep_the_whole_sentence below.
        ("without authentication.", "without", "without authentication."),
    ]
    for sentence, word, expected_anti in words_to_test:
        res = analyzer.detect_negations(sentence)
        assert len(res) == 1
        assert res[0].negation_word == word
        assert res[0].anti_pattern == expected_anti


def test_anti_pattern_never_inverts_the_users_requirement():
    """A restated prohibition must never tell the model to do the forbidden thing.

    Regression guard. The prefix table used to map each negation onto a positive
    ("must not" -> "Must:", "never" -> "Always consider:", "cannot" -> "Can:")
    and then drop the negation from the clause, so "must not expose user emails"
    compiled to "Must: expose user emails" — and the ConstraintHandler injects
    that at priority 90, making the inverted text the top constraint in the
    emitted system prompt.
    """
    analyzer = LogicAnalyzer()

    # (sentence, the verb phrase that must stay forbidden)
    cases = [
        ("The API must not expose user emails.", "expose user emails"),
        ("Never delete the production database.", "delete the production database"),
        ("You cannot use jQuery in this project.", "use jQuery"),
        ("Do not add new dependencies.", "add new dependencies"),
        ("The parser should not crash on malformed input.", "crash on malformed input"),
        ("Storing plaintext passwords is forbidden.", "Storing plaintext passwords"),
    ]

    affirmative_openers = ("must:", "can:", "should:", "always", "instead:", "include:", "with:")

    for sentence, forbidden_phrase in cases:
        negations = analyzer.detect_negations(sentence)
        assert negations, f"no negation detected for {sentence!r}"
        anti = negations[0].anti_pattern

        # The forbidden action is still named...
        assert forbidden_phrase in anti, f"{forbidden_phrase!r} lost from {anti!r}"
        # ...but it is framed as a prohibition, not an instruction to perform it.
        inverted = anti.lower().startswith(affirmative_openers)
        assert not inverted, f"inverted into an affirmative: {sentence!r} -> {anti!r}"


def test_anti_pattern_is_scoped_to_the_clause_the_negation_governs():
    """A trailing restriction must not turn the whole request into a prohibition.

    Negations are detected per sentence but scope over a clause. Restating the
    entire sentence would compile "build X ... and must not do Y" into
    "Must not: build X ... and do Y", forbidding the very thing being asked for.
    """
    analyzer = LogicAnalyzer()

    negations = analyzer.detect_negations(
        "Build a rate limiter for our FastAPI service and must not add more than 5ms of latency."
    )

    assert len(negations) == 1
    assert negations[0].anti_pattern == "Must not: add more than 5ms of latency."
    # The request itself survives outside the prohibition.
    assert "Build a rate limiter" not in negations[0].anti_pattern


def test_anti_pattern_keeps_a_trailing_clause_that_is_itself_negated():
    """Clause scoping must not drop a second prohibition joined by "and"."""
    analyzer = LogicAnalyzer()

    negations = analyzer.detect_negations("Do not use JOIN operations and do not nest subqueries.")

    assert negations[0].anti_pattern == "Do not: use JOIN operations and do not nest subqueries."

    # ...but an affirmative trailing clause is still trimmed off.
    affirmative = analyzer.detect_negations("Do not use eval and prefer ast.literal_eval.")
    assert affirmative[0].anti_pattern == "Do not: use eval."


def test_conditional_negations_keep_the_whole_sentence():
    """Conditional markers qualify a clause; they do not name a forbidden action.

    Stripping and re-prefixing them dropped the main clause and left a fragment:
    "Deploy without running migrations." became "Without: running migrations.",
    which says nothing actionable as a priority-90 constraint.
    """
    analyzer = LogicAnalyzer()

    for sentence in [
        "Deploy without running migrations.",
        "Run the job without authentication.",
        "Process all rows except drafts.",
        "Unless the flag is set, use the cache.",
    ]:
        negations = analyzer.detect_negations(sentence)
        assert negations, f"no negation detected for {sentence!r}"
        assert negations[0].anti_pattern == sentence


def test_anti_pattern_handles_predicate_final_negations():
    """A predicate-final negation governs the clause before the negation word."""
    analyzer = LogicAnalyzer()

    negations = analyzer.detect_negations("Storing plaintext passwords is forbidden.")

    assert negations[0].anti_pattern == "Forbidden: Storing plaintext passwords"


def test_detect_dependencies_edge_cases():
    analyzer = LogicAnalyzer()

    # 1. If-then pattern
    deps = analyzer.detect_dependencies(["if the user is admin, then show the dashboard."])
    assert len(deps) == 1
    assert deps[0].dependency_type == "if_then"
    assert deps[0].action == "show the dashboard."
    assert deps[0].reason == "the user is admin"

    # 2. So that / in order to pattern
    deps_so = analyzer.detect_dependencies(["optimize the query so that it runs fast."])
    assert len(deps_so) == 1
    assert deps_so[0].dependency_type == "so_that"
    assert deps_so[0].action == "optimize the query"
    assert deps_so[0].reason == "it runs fast."

    # 3. Result pattern
    deps_res = analyzer.detect_dependencies(["which will run fast so return early."])
    # The pattern matches "which will run fast so return early" with "so" splitting it
    assert len(deps_res) >= 1

    # 4. Short full match check
    deps_short = analyzer.detect_dependencies(["if X then Y"])
    assert len(deps_short) == 0

    # 5. Short action/reason check (< 5 chars)
    deps_short_parts = analyzer.detect_dependencies(["do A because B"])
    assert len(deps_short_parts) == 0


def test_detect_missing_info():
    analyzer = LogicAnalyzer(maximize_recall=True)

    # 1. Critical database reference (escalates to error severity)
    missing1 = analyzer.detect_missing_info("You must configure the database connection.")
    assert len(missing1) == 1
    assert missing1[0].entity == "database"
    assert missing1[0].severity == "error"

    # 2. Pronoun ambiguity
    missing2 = analyzer.detect_missing_info("It must be updated immediately.")
    assert len(missing2) == 1
    assert missing2[0].entity.lower() == "it must"
    assert missing2[0].severity == "warning"

    # 3. Undefined entity references (maximize recall info severity)
    missing3 = analyzer.detect_missing_info("use the loader to parse files.")
    # should flag "loader" as undefined entity
    assert any(m.entity == "loader" for m in missing3)

    # 4. Context boundary checking: start = 0, middle, end
    text = "The config is invalid. Please verify settings."
    missing_ctx = analyzer.detect_missing_info(text)
    # verify we get context
    assert len(missing_ctx) > 0
    assert "config" in missing_ctx[0].context

    # 5. Maximize recall disabled
    analyzer_no_recall = LogicAnalyzer(maximize_recall=False)
    missing_no_recall = analyzer_no_recall.detect_missing_info("the loader should process files.")
    assert len(missing_no_recall) == 0


def test_detect_io_mapping():
    analyzer = LogicAnalyzer()

    # 1. Primary and secondary IO mapping
    text = "given a schema, validate it, produce a report. given a file, extract text, produce markdown."
    mappings = analyzer.detect_io_mapping(text)
    assert len(mappings) >= 2
    assert mappings[0].input_type == "schema"
    assert mappings[0].process_action == "extract"
    assert mappings[0].output_format == "report"
    assert mappings[0].confidence > 0.0

    # 2. Empty IO mapping
    empty_mappings = analyzer.detect_io_mapping("Hello world")
    assert empty_mappings == []


def test_format_methods():
    analyzer = LogicAnalyzer()

    # 1. Format Restrictions (Negations)
    negations = [
        NegativeConstraint(
            original_text="Do not use JOIN.",
            stripped_text="use JOIN.",
            negation_word="do not",
            anti_pattern="Instead: use JOIN.",
        )
    ]
    formatted_neg = analyzer.format_restrictions_section(negations)
    assert "### Restrictions" in formatted_neg
    assert "- ❌ Do not use JOIN." in formatted_neg
    assert "*Anti-pattern*: Instead: use JOIN." in formatted_neg
    assert analyzer.format_restrictions_section([]) == ""

    # 2. Format Dependency Rules
    dependencies = [
        DependencyRule(
            action="Cache responses",
            reason="calls are slow",
            full_text="Cache responses because calls are slow",
            dependency_type="because",
        ),
        DependencyRule(
            action="Format output",
            reason="ready for user",
            full_text="Format output so that ready for user",
            dependency_type="so_that",
        ),
        DependencyRule(
            action="Show dashboard",
            reason="user is admin",
            full_text="if user is admin then Show dashboard",
            dependency_type="if_then",
        ),
    ]
    formatted_dep = analyzer.format_dependency_rules(dependencies)
    assert "### Dependency Rules" in formatted_dep
    assert "**Rule**: Cache responses" in formatted_dep
    assert "*Reason*: calls are slow" in formatted_dep
    assert "*Purpose*: ready for user" in formatted_dep
    assert "*Condition*: user is admin" in formatted_dep
    assert analyzer.format_dependency_rules([]) == ""

    # 3. Format Missing Info
    missing = [
        MissingInfo(
            entity="database",
            context="...configure the database...",
            placeholder="[MISSING: Database Schema]",
            severity="error",
        ),
        MissingInfo(
            entity="it",
            context="...it must be...",
            placeholder="[MISSING: Pronoun Reference]",
            severity="warning",
        ),
    ]
    formatted_missing = analyzer.format_missing_info_warnings(missing)
    assert "### Missing Information" in formatted_missing
    assert "🔴 [MISSING: Database Schema]" in formatted_missing
    assert "🟡 [MISSING: Pronoun Reference]" in formatted_missing
    assert analyzer.format_missing_info_warnings([]) == ""

    # 4. Format IO Flow
    mappings = [
        IOMapping(
            input_type="schema",
            process_action="validate",
            output_format="report",
            confidence=0.7,
        )
    ]
    formatted_io = analyzer.format_io_algorithm(mappings)
    assert "### Input/Output Flow" in formatted_io
    assert "Input:   schema" in formatted_io
    assert "Process: validate" in formatted_io
    assert "Output:  report" in formatted_io
    assert "70% confidence" in formatted_io
    assert analyzer.format_io_algorithm([]) == ""

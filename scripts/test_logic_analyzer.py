"""
Test script for LogicAnalyzer

Demonstrates the offline logic extraction capabilities:
- Negation detection
- Dependency mapping
- Missing info detection
- I/O flow analysis
"""

from app.heuristics.logic_analyzer import LogicAnalyzer


def main():
    analyzer = LogicAnalyzer()

    # Test prompt with various logic patterns
    test_prompt = """
    Write a Python script that analyzes user data from the database.

    Never use raw SQL queries because they can cause SQL injection attacks.
    Don't include any hardcoded credentials in order to maintain security.
    Avoid using global variables so that the code remains testable.

    Use the API configuration to connect to the service.
    Based on the schema, validate all input fields.

    If the user provides invalid data, then return a helpful error message.
    Generate a JSON report when processing is complete.
    """

    print("=" * 60)
    print("LOGIC ANALYZER TEST")
    print("=" * 60)
    print(f"\nInput Prompt:\n{test_prompt}")
    print("=" * 60)

    result = analyzer.analyze(test_prompt)

    # Display results
    print("\n📛 NEGATIONS / RESTRICTIONS:")
    print("-" * 40)
    for neg in result.negations:
        print(f"  • Original: {neg.original_text}")
        print(f"    Negation: '{neg.negation_word}'")
        print(f"    Anti-pattern: {neg.anti_pattern}")
        print()

    print("\n🔗 DEPENDENCIES / RULES:")
    print("-" * 40)
    for dep in result.dependencies:
        print(f"  • Type: {dep.dependency_type}")
        print(f"    Action: {dep.action}")
        print(f"    Reason: {dep.reason}")
        print()

    print("\n⚠️ MISSING INFORMATION:")
    print("-" * 40)
    for missing in result.missing_info:
        print(f"  • {missing.placeholder}")
        print(f"    Entity: '{missing.entity}'")
        print(f"    Severity: {missing.severity}")
        print()

    print("\n🔄 I/O MAPPINGS:")
    print("-" * 40)
    for io in result.io_mappings:
        print(f"  • Input: {io.input_type}")
        print(f"    Process: {io.process_action}")
        print(f"    Output: {io.output_format}")
        print(f"    Confidence: {io.confidence:.0%}")
        print()

    # Display formatted outputs
    print("\n" + "=" * 60)
    print("FORMATTED OUTPUTS")
    print("=" * 60)

    restrictions = analyzer.format_restrictions_section(result.negations)
    if restrictions:
        print(f"\n{restrictions}")

    deps = analyzer.format_dependency_rules(result.dependencies)
    if deps:
        print(f"\n{deps}")

    missing = analyzer.format_missing_info_warnings(result.missing_info)
    if missing:
        print(f"\n{missing}")

    io_flow = analyzer.format_io_algorithm(result.io_mappings)
    if io_flow:
        print(f"\n{io_flow}")

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Negations detected: {len(result.negations)}")
    print(f"  Dependencies detected: {len(result.dependencies)}")
    print(f"  Missing info warnings: {len(result.missing_info)}")
    print(f"  I/O mappings: {len(result.io_mappings)}")


if __name__ == "__main__":
    main()

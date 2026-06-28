from app.readiness.reference_rules import detect_unverifiable_references


def test_flags_unknown_sdk():
    refs = detect_unverifiable_references("use the AcmeCloud SDK to deploy my model")
    assert refs == ["AcmeCloud SDK"]


def test_flags_camelcase_product_token():
    refs = detect_unverifiable_references("connect to FooBarHub and sync")
    assert "FooBarHub" in refs


def test_known_tech_not_flagged():
    refs = detect_unverifiable_references("build a FastAPI endpoint that stores rows in Postgres")
    assert refs == []


def test_plain_text_no_false_positive():
    assert detect_unverifiable_references("make my app faster") == []


def test_allcaps_protocol_acronyms_not_flagged():
    assert detect_unverifiable_references("Build a REST API for users") == []
    assert detect_unverifiable_references("Create a JSON API endpoint") == []
    assert detect_unverifiable_references("Expose an HTTP API") == []


def test_well_known_platforms_not_flagged():
    # These would match the suffix/CamelCase patterns but are real, known platforms.
    for text in [
        "use the Twilio API to send SMS",
        "store files via the Dropbox API",
        "host the app on DigitalOcean",
        "query the GraphQL endpoint",
        "deploy with PlanetScale and SendGrid",
        "search vectors in the Pinecone API",
    ]:
        assert detect_unverifiable_references(text) == [], text


def test_camelcase_pattern_is_not_redos_vulnerable():
    # The CamelCase pattern previously backtracked exponentially (CodeQL py/redos)
    # on inputs like "Aa" + "B" * n. It must now run in linear time.
    import time

    evil = "Aa" + "B" * 4000 + "_"
    start = time.perf_counter()
    detect_unverifiable_references(evil)
    assert time.perf_counter() - start < 1.0


def test_camelcase_still_matches_after_redos_fix():
    # Behaviour must be preserved by the ReDoS fix.
    assert detect_unverifiable_references("connect to FooBarHub and sync") == ["FooBarHub"]
    assert detect_unverifiable_references("use the AcmeCloud SDK") == ["AcmeCloud SDK"]

from app.readiness.analyzer import analyze_readiness


def test_acmecloud_is_clarify_with_unverifiable_signal():
    report = analyze_readiness("use the AcmeCloud SDK to deploy my model")
    assert report.verdict == "clarify"
    assert any(s.kind == "unverifiable_reference" for s in report.signals)


def test_vague_request_is_clarify_with_questions():
    report = analyze_readiness("make my app faster")
    assert report.verdict == "clarify"
    assert any(s.kind == "vagueness" for s in report.signals)


def test_gibberish_is_noise():
    assert analyze_readiness("asdf1234!!!!****").verdict == "noise"


def test_empty_is_noise():
    assert analyze_readiness("   ").verdict == "noise"


def test_greeting_is_noise():
    assert analyze_readiness("merhaba").verdict == "noise"


def test_concrete_request_is_ready():
    report = analyze_readiness(
        "build a FastAPI endpoint that accepts a CSV upload, validates rows, "
        "stores them in Postgres, and returns a job id"
    )
    assert report.verdict == "ready"


def test_sensitive_security_request_is_risky():
    report = analyze_readiness("add password hashing and session authentication")
    assert report.verdict == "risky"
    assert any(s.kind == "risk" for s in report.signals)


def test_turkish_request_is_not_noise():
    report = analyze_readiness("Uygulamam çok yavaş, hızlandırmak için ne yapmalıyım?")
    assert report.verdict != "noise"


def test_questions_capped_at_three():
    report = analyze_readiness("make it better, faster, nicer, cleaner, and improve it")
    assert len(report.questions) <= 3


def test_hash_map_is_not_risky():
    # "hash"/"salt" as generic CS/cooking words must not trigger the security signal
    assert analyze_readiness("build a hash map in Python and return it").verdict == "ready"
    assert analyze_readiness("add salt to taste and serve the dish").verdict != "risky"

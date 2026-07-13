from app.models_v2 import IRv2, PolicyV2
from app.readiness.analyzer import _is_noise, analyze_readiness


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


def test_consonant_only_words_are_noise():
    assert _is_noise("brrr tsk grrr") is True
    assert analyze_readiness("brrr tsk grrr").verdict == "noise"


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


def test_short_turkish_vowel_rich_request_is_not_noise():
    assert _is_noise("ölçü üret") is False
    assert analyze_readiness("ölçü üret").verdict != "noise"


def test_questions_capped_at_three():
    report = analyze_readiness("make it better, faster, nicer, cleaner, and improve it")
    assert len(report.questions) <= 3


def test_hash_map_is_not_risky():
    # "hash"/"salt" as generic CS/cooking words must not trigger the security signal
    assert analyze_readiness("build a hash map in Python and return it").verdict == "ready"
    assert analyze_readiness("add salt to taste and serve the dish").verdict != "risky"


def test_vague_with_trailing_punctuation_is_clarify():
    assert analyze_readiness("make my app faster.").verdict == "clarify"
    assert analyze_readiness("please make it better, ok?").verdict == "clarify"


def test_authorization_request_is_risky():
    assert analyze_readiness("add user authorization checks to the admin panel").verdict == "risky"


def test_high_risk_ir_policy_cannot_be_reported_as_ready():
    ir = IRv2(
        policy=PolicyV2(
            risk_level="high",
            risk_domains=["infrastructure"],
            execution_mode="human_approval_required",
        )
    )

    report = analyze_readiness("write a script to wipe the production database", ir)

    assert report.verdict == "risky"
    assert any("high risk" in signal.message.lower() for signal in report.signals)


def test_human_approval_ir_policy_cannot_be_reported_as_ready():
    ir = IRv2(
        policy=PolicyV2(
            risk_level="medium",
            execution_mode="human_approval_required",
        )
    )

    report = analyze_readiness("generate a local report", ir)

    assert report.verdict == "risky"
    assert any("human approval" in signal.message.lower() for signal in report.signals)

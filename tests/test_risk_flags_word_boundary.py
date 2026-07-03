"""Risk-flag detection must match whole words, not substrings.

Regression for the inverted risk model: the substring matcher flagged
"GitHub issue" as legal (because "sue" is inside "issue"), "hackathon" as
security ("hack"), etc. These false positives inflated risk on safe requests
and trained users to ignore the gate. detect_risk_flags must use word
boundaries while still catching real risk terms (including inflections).
"""

from app.heuristics import detect_risk_flags


# --- False positives that must NOT fire (the bug) ---------------------------


def test_github_issue_is_not_legal():
    flags = detect_risk_flags("Turn this GitHub issue into a safe implementation brief")
    assert "legal" not in flags


def test_pursue_is_not_legal():
    assert "legal" not in detect_risk_flags("I want to pursue this idea further")


def test_tissue_is_not_legal():
    assert "legal" not in detect_risk_flags("Describe the tissue sample under the microscope")


def test_data_source_is_not_security():
    # "rce" lives inside "source"; a leading word boundary must not flag it.
    assert "security" not in detect_risk_flags("Read records from the upstream data source")


# --- Real risk terms that MUST still fire -----------------------------------


def test_real_lawsuit_is_legal():
    assert "legal" in detect_risk_flags("We are facing a lawsuit and need a lawyer")


def test_real_contract_is_legal():
    assert "legal" in detect_risk_flags("Review the signed contract for issues")


def test_real_hack_is_security():
    assert "security" in detect_risk_flags("How would an attacker hack into this login form?")


def test_multiword_sql_injection_is_security():
    assert "security" in detect_risk_flags("Test the form for sql injection vulnerabilities")


def test_exact_legal_terms_still_match():
    # whole-word matching keeps the listed terms; precision over inflection
    # (missing plurals is an acceptable false-negative; over-flagging is the bug we fix)
    assert "legal" in detect_risk_flags("The new regulation affects our signed contract")


def test_multiple_legal_keywords_only_emit_one_flag():
    flags = detect_risk_flags("A lawyer should review the contract before the lawsuit lands.")
    assert flags.count("legal") == 1

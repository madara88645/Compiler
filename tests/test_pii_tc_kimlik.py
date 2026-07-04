"""TC Kimlik checksum validation used to reduce PII false positives.

`_is_tc_kimlik_valid` implements the official Turkish national ID checksum
(mod-10 over the odd/even digit sums, plus a full mod-10 total check) so a
random 11-digit number that merely looks like an ID doesn't get flagged as PII.
"""

from app.heuristics import _is_tc_kimlik_valid


def test_known_valid_checksum_passes():
    # Well-known publicly documented test TC Kimlik number that satisfies the checksum.
    assert _is_tc_kimlik_valid("10000000146") is True


def test_all_zeros_prefixed_by_nonzero_first_digit_but_bad_checksum_fails():
    assert _is_tc_kimlik_valid("12345678901") is False


def test_leading_zero_is_rejected():
    # First digit must be 1-9 per the pattern.
    assert _is_tc_kimlik_valid("01234567890") is False


def test_wrong_length_is_rejected():
    assert _is_tc_kimlik_valid("123456789") is False
    assert _is_tc_kimlik_valid("1234567890123") is False


def test_non_digit_characters_are_rejected():
    assert _is_tc_kimlik_valid("1234567890a") is False


def test_empty_string_is_rejected():
    assert _is_tc_kimlik_valid("") is False


def test_valid_length_but_single_digit_checksum_off_by_one_fails():
    # Flip the last (11th) digit of a known-valid number; checksum must fail.
    assert _is_tc_kimlik_valid("10000000147") is False

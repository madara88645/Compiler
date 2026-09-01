"""Direct unit tests for pure detection helpers in
app.heuristics.handlers.psycholinguist: detect_sentiment and
detect_cultural_context.

These functions are already exercised indirectly through
PsycholinguistHandler.handle() (see tests/heuristics/test_psycholinguist.py),
but had no direct unit-level assertions of their own return values and
internal priority ordering.
"""

from __future__ import annotations

from app.heuristics.handlers.psycholinguist import (
    UserSentiment,
    detect_cultural_context,
    detect_sentiment,
)


class TestDetectSentiment:
    def test_urgent_keyword_returns_urgent(self):
        assert detect_sentiment("I need this ASAP please") == UserSentiment.URGENT

    def test_turkish_urgent_keyword_returns_urgent(self):
        assert detect_sentiment("Bunu hemen yapmam lazim") == UserSentiment.URGENT

    def test_urgent_keyword_is_case_insensitive(self):
        assert detect_sentiment("This is URGENT") == UserSentiment.URGENT

    def test_frustration_double_exclamation_returns_frustrated(self):
        assert detect_sentiment("I don't understand this at all!!") == UserSentiment.FRUSTRATED

    def test_frustration_wtf_returns_frustrated(self):
        assert detect_sentiment("wtf is going on here") == UserSentiment.FRUSTRATED

    def test_frustration_question_bang_combo_returns_frustrated(self):
        assert detect_sentiment("Why does this keep happening?!") == UserSentiment.FRUSTRATED

    def test_casual_greeting_returns_casual(self):
        assert detect_sentiment("hey, thanks for the help") == UserSentiment.CASUAL

    def test_turkish_casual_returns_casual(self):
        assert detect_sentiment("selam, nasilsin") == UserSentiment.CASUAL

    def test_plain_request_returns_neutral(self):
        assert detect_sentiment("Write a function to calculate fibonacci.") == UserSentiment.NEUTRAL

    def test_empty_string_returns_neutral(self):
        assert detect_sentiment("") == UserSentiment.NEUTRAL

    def test_urgent_takes_priority_over_frustration(self):
        # "broken" is itself an URGENT_KEYWORDS entry, so even though the
        # sentence also matches a frustration pattern (double question/bang
        # combo), urgency is checked first and wins.
        text = "This is broken, why isn't it working?!"
        assert detect_sentiment(text) == UserSentiment.URGENT

    def test_frustration_takes_priority_over_casual(self):
        # Contains both a casual marker ("hey") and a frustration marker
        # ("wtf"); frustration is checked before casual.
        text = "hey, WTF is going on??"
        assert detect_sentiment(text) == UserSentiment.FRUSTRATED


class TestDetectCulturalContext:
    def test_uk_spelling_returns_british(self):
        assert detect_cultural_context("Check the colour of the centre element.") == "British"

    def test_us_spelling_returns_american(self):
        assert detect_cultural_context("Check the color of the center element.") == "American"

    def test_no_signal_returns_none(self):
        assert detect_cultural_context("Please help me write a poem about the sea.") is None

    def test_empty_string_returns_none(self):
        assert detect_cultural_context("") is None

    def test_currency_try_returns_turkish(self):
        assert detect_cultural_context("The price is 100 TL.") == "Turkish"

    def test_currency_usd_dollar_word_returns_american(self):
        # \bdollar\b requires a word boundary right after "dollar", so the
        # plural "dollars" does not match; use the singular form.
        assert detect_cultural_context("That will cost about 1 dollar.") == "American"

    def test_currency_gbp_returns_british(self):
        assert detect_cultural_context("It costs 50 GBP.") == "British"

    def test_currency_eur_returns_european(self):
        assert detect_cultural_context("It costs 50 Euro.") == "European"

    def test_currency_checked_only_when_spelling_ties(self):
        # No UK/US spelling markers at all, so currency deviates straight to
        # the currency scan; TR entry is iterated first in CURRENCY_PATTERNS,
        # so a text mentioning both TL and USD resolves to Turkish.
        assert detect_cultural_context("Priced at 10 TL or 5 USD, your choice.") == "Turkish"

    def test_spelling_tie_falls_back_to_currency(self):
        # 'color' (US) and 'colour' (UK) tie 1-1 on spelling score, so the
        # currency check breaks the tie via GBP -> British.
        text = "Check the color vs colour difference in GBP."
        assert detect_cultural_context(text) == "British"

    def test_more_uk_words_than_us_returns_british(self):
        text = "The colour, flavour, and centre are all correct."
        assert detect_cultural_context(text) == "British"

from app.optimizer import language_costs
from app.text_utils import estimate_tokens


def test_sparse_word_boundaries_do_not_cap_large_multilingual_or_code_inputs():
    for text in ("中文" * 100 + "\n" + "中文" * 100, "x" * 1000 + "\n" + "y" * 1000):
        assert estimate_tokens(text) >= len(text.encode("utf-8")) / 4
        assert estimate_tokens(text, token_ratio=2) > estimate_tokens(text, token_ratio=4)


def test_actual_encoding_failure_reports_heuristic_method(monkeypatch):
    class BrokenEncoding:
        def encode(self, *args, **kwargs):
            raise ValueError("encoding failed")

    class Tokenizer:
        @staticmethod
        def get_encoding(name):
            return BrokenEncoding()

    monkeypatch.setattr(language_costs, "tiktoken", Tokenizer())
    result = language_costs.estimate_prompt_cost("hello world")
    assert result.tokens == estimate_tokens("hello world")
    assert result.tokenizer_method == language_costs.HEURISTIC_TOKENIZER_METHOD


def test_local_estimate_does_not_claim_or_use_a_cloud_tokenizer():
    result = language_costs.estimate_prompt_cost(
        "中文" * 20, provider="local", model="openai/gpt-oss-20b"
    )
    assert result.tokens == estimate_tokens("中文" * 20)
    assert result.tokenizer_method == language_costs.HEURISTIC_TOKENIZER_METHOD


def test_literal_special_token_text_is_counted_as_prompt_text():
    result = language_costs.estimate_prompt_cost("Explain <|endoftext|> in the docs.")
    assert result.tokens > 0
    assert result.tokenizer_method == language_costs.TOKENIZER_METHOD

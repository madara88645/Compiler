1. **Refactor `any()` with `isdisjoint()` in `app/heuristics/handlers/policy.py`**
   - In `app/heuristics/handlers/policy.py`, replace the generator expression `any(flag in self._HIGH_RISK_DOMAINS for flag in risk_flags)` with the faster `not self._HIGH_RISK_DOMAINS.isdisjoint(risk_flags)`.
   - In the same file, update the check for PII flags: replace `any(flag in {"credit_card", "iban"} for flag in pii_flags)` with `not {"credit_card", "iban"}.isdisjoint(pii_flags)`.
2. **Refactor `any()` with `_contains_any_keyword` in `app/heuristics/handlers/policy.py`**
   - Import `_contains_any_keyword` from `app.heuristics` into `app/heuristics/handlers/policy.py`.
   - Replace `any(keyword in text for keyword in self._FILE_KEYWORDS)` with `_contains_any_keyword(text, self._FILE_KEYWORDS)`.
   - Replace `any(keyword in lower_text for keyword in cls._EDUCATIONAL_KEYWORDS)` with `_contains_any_keyword(lower_text, cls._EDUCATIONAL_KEYWORDS)`.
3. **Refactor `any()` with `_contains_any_keyword` in `app/heuristics/handlers/format_enforcer.py`**
   - Import `_contains_any_keyword` from `app.heuristics` into `app/heuristics/handlers/format_enforcer.py`.
   - Replace `any(kw in text_lower for kw in format_keywords)` with `_contains_any_keyword(text_lower, format_keywords)`.
4. **Refactor `any()` with `_contains_any_keyword` in `app/heuristics/handlers/paradox_resolver.py`**
   - Import `_contains_any_keyword` from `app.heuristics` into `app/heuristics/handlers/paradox_resolver.py`.
   - Replace `any(k in text_lower or k in constraints_lower for k in brief_kw)` and similar detail keywords logic to use `_contains_any_keyword`.
5. **Complete pre-commit steps**
   - Complete pre-commit steps to ensure proper testing, verification, review, and reflection are done.
6. **Submit PR**
   - Commit the changes and request a PR review. Include performance metrics in the description.

def test_strategist_expansion_failure_is_silent(capsys):
    from app.agents.context_strategist import ContextStrategist

    class _BoomClient:
        def _call_api(self, *args, **kwargs):
            raise RuntimeError("no api key")

    strat = ContextStrategist(client=_BoomClient())
    result = strat._expand_query("write a haiku about the sea")
    captured = capsys.readouterr()
    assert "[STRATEGIST]" not in captured.err
    assert isinstance(result, list)

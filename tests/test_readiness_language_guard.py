from app.readiness.language_guard import output_language_mismatch


def test_turkish_input_english_output_is_mismatch():
    assert output_language_mismatch(
        "Uygulamam çok yavaş, hızlandırmak için ne yapmalıyım?",
        "You are a performance engineer. Identify bottlenecks and suggest fixes.",
    )


def test_turkish_input_turkish_output_is_ok():
    assert not output_language_mismatch(
        "Uygulamam çok yavaş, hızlandırmak için ne yapmalıyım?",
        "Sen bir performans mühendisisin. Darboğazları bul ve çözüm öner.",
    )


def test_english_input_never_overridden():
    assert not output_language_mismatch("make my app faster", "Sen bir mühendissin.")


def test_empty_is_not_mismatch():
    assert not output_language_mismatch("", "anything")
    assert not output_language_mismatch("merhaba dünya", "")

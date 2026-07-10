from app.heuristics import detect_teaching_intent, extract_inputs


def test_detect_teaching_intent_phrases():
    # True cases (English & Turkish keywords)
    assert detect_teaching_intent("teach me algorithms")
    assert detect_teaching_intent("can you explain recursion?")
    assert detect_teaching_intent("learn me how to write code")
    assert detect_teaching_intent("python tutorial for beginners")
    assert detect_teaching_intent("step-by-step guide to docker")
    assert detect_teaching_intent("bana döngüleri öğret")
    assert detect_teaching_intent("git konusunu anlat")
    assert detect_teaching_intent("bir ders hazırlayabilir misin?")
    assert detect_teaching_intent("rust dilini öğrenmek istiyorum")

    # False cases (no keywords, or boundary check)
    assert not detect_teaching_intent("this is a simple code")
    # "re-renders" contains "renders", which shouldn't match "ders" due to word boundaries
    assert not detect_teaching_intent("my react app re-renders multiple times")
    # "misguide" has "guide" not at a word boundary
    assert not detect_teaching_intent("do not misguide them")
    # No teaching keywords
    assert not detect_teaching_intent("follow the rules")


def test_level_heuristics():
    # Beginner levels (EN & TR)
    assert extract_inputs("beginner python course", "en").get("level") == "beginner"
    assert extract_inputs("entry level sql", "en").get("level") == "beginner"
    assert extract_inputs("intro to programming", "en").get("level") == "beginner"
    assert extract_inputs("novice guide to git", "en").get("level") == "beginner"
    assert extract_inputs("başlangıç seviyesinde docker", "tr").get("level") == "beginner"
    assert extract_inputs("giriş düzeyinde veri bilimi", "tr").get("level") == "beginner"
    assert extract_inputs("temel düzeyde css", "tr").get("level") == "beginner"

    # Intermediate levels (EN & TR)
    assert extract_inputs("intermediate rust tutorial", "en").get("level") == "intermediate"
    assert extract_inputs("mid level dev tips", "en").get("level") == "intermediate"
    assert extract_inputs("orta seviye react eğitimi", "tr").get("level") == "intermediate"
    assert extract_inputs("orta düzey postgresql", "tr").get("level") == "intermediate"

    # Advanced levels (EN & TR)
    assert extract_inputs("advanced nextjs guide", "en").get("level") == "advanced"
    assert extract_inputs("expert-level cybersecurity", "en").get("level") == "advanced"
    assert extract_inputs("ileri düzey kubernetes", "tr").get("level") == "advanced"
    assert extract_inputs("uzman seviye go programlama", "tr").get("level") == "advanced"


def test_duration_heuristics():
    # English minutes
    assert extract_inputs("learn react in 15 minutes", "en").get("duration") == "15m"
    assert extract_inputs("explain dns in 5 min", "en").get("duration") == "5m"
    assert extract_inputs("docker tutorial in 30 mins", "en").get("duration") == "30m"
    assert extract_inputs("git basic guide in 10m", "en").get("duration") == "10m"

    # English hours
    assert extract_inputs("a 2 hours workshop on flask", "en").get("duration") == "2h"
    assert extract_inputs("1 hour lesson", "en").get("duration") == "1h"

    # Turkish minutes
    assert extract_inputs("10 dakikada algoritma öğret", "tr").get("duration") == "10m"
    assert extract_inputs("15 dk içinde docker anlat", "tr").get("duration") == "15m"

    # Turkish hours
    assert extract_inputs("3 saatte veri analizi", "tr").get("duration") == "3h"
    assert extract_inputs("1 saat ders planı", "tr").get("duration") == "1h"

    # Half hour / Yarım saat
    assert extract_inputs("explain it in half an hour", "en").get("duration") == "30m"
    assert extract_inputs("yarım saat içinde anlat", "tr").get("duration") == "30m"

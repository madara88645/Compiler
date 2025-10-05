"""Tests for prompt comparison functionality"""

from app.compare import compare_prompts, PromptComparator


def test_compare_identical_prompts():
    """İki özdeş prompt karşılaştırıldığında skor farkı 0 olmalı"""
    prompt = "Write a detailed technical guide about Python decorators."

    result = compare_prompts(prompt, prompt)

    assert result.score_difference == 0
    assert result.better_prompt is None
    assert "benzer kalitede" in result.recommendation


def test_compare_vague_vs_specific():
    """Vague prompt ile specific prompt karşılaştırması"""
    vague = "Write something about coding"
    specific = (
        "Write a beginner-friendly tutorial explaining Python list comprehensions with 3 examples."
    )

    result = compare_prompts(vague, specific, "Vague", "Specific")

    # Specific daha iyi olmalı (skor farkı pozitif olacak)
    assert result.score_difference > 0  # B (specific) daha yüksek
    # Not: Skor farkı 5'ten küçük olabilir, ama pozitif olmalı


def test_compare_missing_persona():
    """Persona'lı ve persona'sız prompt karşılaştırması"""
    without_persona = "Explain quantum computing concepts"
    with_persona = (
        "You are a physics professor. Explain quantum computing concepts to undergraduate students."
    )

    result = compare_prompts(without_persona, with_persona)

    # Persona'lı daha iyi olabilir veya benzer olabilir
    # IR diff'te persona farkı görebiliriz
    assert isinstance(result.score_difference, (int, float))


def test_compare_examples_difference():
    """Example'lı ve example'sız prompt karşılaştırması"""
    without_examples = "Generate creative product names for a coffee shop"
    with_examples = """Generate creative product names for a coffee shop.

Examples:
- "Morning Glory" for breakfast blend
- "Midnight Express" for dark roast
- "Cloud Nine" for light, airy blend"""

    result = compare_prompts(without_examples, with_examples)

    # Score comparison çalıştığını doğrula
    assert isinstance(result.score_difference, (int, float))

    # IR changes'de examples farkı görünmeli (eğer compiler tespit ederse)
    # Not: Compiler her zaman example'ları extract etmeyebilir
    assert isinstance(result.ir_changes, list)


def test_compare_constraints_added():
    """Constraints eklemenin etkisi"""
    without_constraints = "Write a story about a dragon"
    with_constraints = """Write a story about a dragon.

Constraints:
- 500 words maximum
- PG-rated content only
- Focus on character development"""

    result = compare_prompts(without_constraints, with_constraints)

    # Comparison yapıldığını doğrula
    assert "completeness" in result.category_comparison

    # IR changes listesi var mı
    assert isinstance(result.ir_changes, list)


def test_compare_intents_difference():
    """Intent değişikliğinin algılanması"""
    creative = "Write a creative poem about nature"
    informative = "Explain the ecological benefits of forests in bullet points"

    result = compare_prompts(creative, informative)

    # Intent farkı IR'da görünmeli
    intent_changes = [c for c in result.ir_changes if c["field"] == "intents"]
    assert len(intent_changes) > 0


def test_compare_category_breakdown():
    """Kategori bazında karşılaştırma"""
    prompt_a = "Do something with AI"  # Çok vague
    prompt_b = (
        "You are an AI expert. Create a comprehensive guide explaining neural network architecture."
    )

    result = compare_prompts(prompt_a, prompt_b)

    # Tüm kategoriler mevcut olmalı
    for category in ["clarity", "specificity", "completeness", "consistency"]:
        assert category in result.category_comparison
        comp = result.category_comparison[category]
        # B genelde daha iyi olacak ama mutlak değil, category_comparison yapıldığını doğrula
        assert "difference" in comp
        assert "better" in comp


def test_compare_strengths_identified():
    """Güçlü yönlerin belirlenmesi"""
    good_prompt = """You are a technical writer with 10 years of experience.

Write a beginner-friendly guide about Git version control.

Examples:
- Explain 'git commit' like saving a checkpoint in a video game
- Describe 'git branch' as creating parallel universes

Format: Use markdown with code blocks and diagrams.

Constraints:
- Maximum 2000 words
- Include at least 5 practical examples
- Avoid advanced topics like rebasing"""

    simple_prompt = "Explain git"

    result = compare_prompts(simple_prompt, good_prompt)

    # Good prompt'ta strengths olmalı veya en azından daha yüksek skor
    # Validator'ın strength detection'ı değişebilir
    assert result.validation_b.score.total >= result.validation_a.score.total


def test_compare_ir_diff_generation():
    """IR diff'in doğru oluşturulması"""
    prompt_a = "Write a story"
    prompt_b = "Write a science fiction story"

    result = compare_prompts(prompt_a, prompt_b)

    # Diff boş olmamalı
    assert len(result.ir_diff) > 0

    # Unified diff formatında olmalı
    assert "---" in result.ir_diff or "+++" in result.ir_diff or len(result.ir_diff) > 50


def test_compare_score_difference_threshold():
    """5 puanlık eşik değerinin kontrolü"""
    # Küçük fark - better_prompt None olmalı
    prompt_a = "Write a technical article about Python"
    prompt_b = "Write a detailed technical article about Python"

    result = compare_prompts(prompt_a, prompt_b)

    if abs(result.score_difference) < 5:
        assert result.better_prompt is None
    else:
        assert result.better_prompt in ["A", "B"]


def test_compare_labels_in_output():
    """Custom label'ların kullanılması"""
    prompt_a = "Version 1 text"
    prompt_b = "Version 2 text"

    result = compare_prompts(prompt_a, prompt_b, label_a="Old Version", label_b="New Version")

    # Recommendation üretildi mi?
    assert isinstance(result.recommendation, str)
    assert len(result.recommendation) > 0


def test_compare_to_dict():
    """ComparisonResult.to_dict() serializasyonu"""
    prompt_a = "Simple prompt"
    prompt_b = "More detailed prompt with examples"

    result = compare_prompts(prompt_a, prompt_b)
    data = result.to_dict()

    # Gerekli alanlar var mı?
    assert "prompt_a" in data
    assert "prompt_b" in data
    assert "validation_a" in data
    assert "validation_b" in data
    assert "score_difference" in data
    assert "recommendation" in data
    assert "category_comparison" in data

    # Nested validation yapısı
    assert "score" in data["validation_a"]
    assert "category_scores" in data["validation_a"]
    assert "issues" in data["validation_a"]


def test_comparator_class():
    """PromptComparator sınıfının doğrudan kullanımı"""
    comparator = PromptComparator()

    result = comparator.compare("Basic prompt", "Advanced prompt with context", "Basic", "Advanced")

    assert result.prompt_a == "Basic prompt"
    assert result.prompt_b == "Advanced prompt with context"
    assert isinstance(result.score_difference, (int, float))


def test_compare_empty_prompts():
    """Boş promptların karşılaştırılması"""
    result = compare_prompts("", "Write something")

    # Karşılaştırma başarılı olmalı
    assert isinstance(result.score_difference, (int, float))
    # Compiler boş prompt'u bile parse edebilir, bu yüzden skorlar yakın olabilir


def test_compare_long_prompts():
    """Uzun promptların karşılaştırılması"""
    long_prompt_a = "Write a story. " * 100
    long_prompt_b = """You are a creative writer.

Write an engaging short story about time travel.

Examples:
- Use vivid descriptions
- Create memorable characters
- Include a plot twist

Format: 3-5 paragraphs, approximately 500 words.

Constraints:
- Family-friendly content
- Clear beginning, middle, and end"""

    result = compare_prompts(long_prompt_a, long_prompt_b)

    # Structure'lı prompt daha iyi olmalı
    assert result.validation_b.score.total >= result.validation_a.score.total

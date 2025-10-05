"""
Prompt Comparison Module

Bu modül iki prompt'u karşılaştırır ve detaylı analiz sağlar.
"""

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from difflib import unified_diff

from app.compiler import compile_text_v2
from app.validator import PromptValidator, ValidationResult


@dataclass
class ComparisonResult:
    """İki prompt'un karşılaştırma sonucu"""
    
    # Temel bilgiler
    prompt_a: str
    prompt_b: str
    
    # Validation sonuçları
    validation_a: ValidationResult
    validation_b: ValidationResult
    
    # IR farkları
    ir_diff: str
    ir_changes: List[Dict[str, Any]]
    
    # Karşılaştırma özeti
    score_difference: float
    better_prompt: Optional[str]  # "A", "B", veya None (eşit)
    recommendation: str
    
    # Kategori bazında karşılaştırma
    category_comparison: Dict[str, Dict[str, Any]]
    
    def to_dict(self) -> Dict[str, Any]:
        """JSON serialization için dict'e çevir"""
        return {
            "prompt_a": self.prompt_a,
            "prompt_b": self.prompt_b,
            "validation_a": {
                "score": self.validation_a.score.total,
                "category_scores": {
                    "clarity": self.validation_a.score.clarity,
                    "specificity": self.validation_a.score.specificity,
                    "completeness": self.validation_a.score.completeness,
                    "consistency": self.validation_a.score.consistency,
                },
                "issues": [
                    {
                        "severity": issue.severity,
                        "category": issue.category,
                        "message": issue.message,
                        "suggestion": issue.suggestion,
                        "field": issue.field,
                    }
                    for issue in self.validation_a.issues
                ],
                "strengths": self.validation_a.strengths,
            },
            "validation_b": {
                "score": self.validation_b.score.total,
                "category_scores": {
                    "clarity": self.validation_b.score.clarity,
                    "specificity": self.validation_b.score.specificity,
                    "completeness": self.validation_b.score.completeness,
                    "consistency": self.validation_b.score.consistency,
                },
                "issues": [
                    {
                        "severity": issue.severity,
                        "category": issue.category,
                        "message": issue.message,
                        "suggestion": issue.suggestion,
                        "field": issue.field,
                    }
                    for issue in self.validation_b.issues
                ],
                "strengths": self.validation_b.strengths,
            },
            "ir_diff": self.ir_diff,
            "ir_changes": self.ir_changes,
            "score_difference": self.score_difference,
            "better_prompt": self.better_prompt,
            "recommendation": self.recommendation,
            "category_comparison": self.category_comparison,
        }


class PromptComparator:
    """İki prompt'u karşılaştıran sınıf"""
    
    def __init__(self):
        self.validator = PromptValidator()
    
    def compare(
        self,
        prompt_a: str,
        prompt_b: str,
        label_a: str = "Prompt A",
        label_b: str = "Prompt B"
    ) -> ComparisonResult:
        """
        İki prompt'u karşılaştır
        
        Args:
            prompt_a: İlk prompt metni
            prompt_b: İkinci prompt metni
            label_a: İlk prompt için etiket
            label_b: İkinci prompt için etiket
            
        Returns:
            ComparisonResult nesnesi
        """
        # Her iki prompt'u compile et
        ir_a_obj = compile_text_v2(prompt_a)
        ir_b_obj = compile_text_v2(prompt_b)
        
        # Validate et (IRv2 object olarak)
        validation_a = self.validator.validate(ir_a_obj, prompt_a)
        validation_b = self.validator.validate(ir_b_obj, prompt_b)
        
        # IRv2 objelerini dict'e çevir (diff için)
        ir_a = ir_a_obj.model_dump()
        ir_b = ir_b_obj.model_dump()
        
        # IR farklarını bul
        ir_diff, ir_changes = self._compare_ir(ir_a, ir_b)
        
        # Skor farkını hesapla (QualityScore.total kullan)
        score_diff = validation_b.score.total - validation_a.score.total
        
        # Hangisi daha iyi?
        better_prompt = None
        if abs(score_diff) >= 5.0:  # En az 5 puan fark
            better_prompt = "B" if score_diff > 0 else "A"
        
        # Öneri oluştur
        recommendation = self._generate_recommendation(
            validation_a, validation_b, score_diff, label_a, label_b
        )
        
        # Kategori bazında karşılaştırma
        category_comparison = self._compare_categories(validation_a, validation_b)
        
        return ComparisonResult(
            prompt_a=prompt_a,
            prompt_b=prompt_b,
            validation_a=validation_a,
            validation_b=validation_b,
            ir_diff=ir_diff,
            ir_changes=ir_changes,
            score_difference=score_diff,
            better_prompt=better_prompt,
            recommendation=recommendation,
            category_comparison=category_comparison,
        )
    
    def _compare_ir(self, ir_a: Dict[str, Any], ir_b: Dict[str, Any]) -> Tuple[str, List[Dict[str, Any]]]:
        """IR farklarını bul"""
        # JSON'a çevir (pretty print)
        json_a = json.dumps(ir_a, indent=2, ensure_ascii=False, sort_keys=True)
        json_b = json.dumps(ir_b, indent=2, ensure_ascii=False, sort_keys=True)
        
        # Unified diff oluştur
        diff_lines = list(unified_diff(
            json_a.splitlines(keepends=True),
            json_b.splitlines(keepends=True),
            fromfile="Prompt A (IR)",
            tofile="Prompt B (IR)",
            lineterm=""
        ))
        diff_text = "".join(diff_lines)
        
        # Önemli değişiklikleri listele
        changes = []
        
        # Core instruction değişikliği
        if ir_a.get("core_instruction") != ir_b.get("core_instruction"):
            changes.append({
                "field": "core_instruction",
                "change_type": "modified",
                "from": ir_a.get("core_instruction", ""),
                "to": ir_b.get("core_instruction", ""),
            })
        
        # Intent değişikliği
        intents_a = set(ir_a.get("intents", []))
        intents_b = set(ir_b.get("intents", []))
        
        added_intents = intents_b - intents_a
        removed_intents = intents_a - intents_b
        
        if added_intents:
            changes.append({
                "field": "intents",
                "change_type": "added",
                "values": list(added_intents),
            })
        if removed_intents:
            changes.append({
                "field": "intents",
                "change_type": "removed",
                "values": list(removed_intents),
            })
        
        # Persona değişikliği
        if ir_a.get("persona") != ir_b.get("persona"):
            changes.append({
                "field": "persona",
                "change_type": "modified",
                "from": ir_a.get("persona"),
                "to": ir_b.get("persona"),
            })
        
        # Examples sayısı
        examples_a = len(ir_a.get("examples", []))
        examples_b = len(ir_b.get("examples", []))
        
        if examples_a != examples_b:
            changes.append({
                "field": "examples",
                "change_type": "count_changed",
                "from_count": examples_a,
                "to_count": examples_b,
            })
        
        # Constraints değişikliği (dict olduğu için text alanını karşılaştır)
        constraints_a_texts = set(
            c.get("text", str(c)) if isinstance(c, dict) else str(c)
            for c in ir_a.get("constraints", [])
        )
        constraints_b_texts = set(
            c.get("text", str(c)) if isinstance(c, dict) else str(c)
            for c in ir_b.get("constraints", [])
        )
        
        added_constraints = constraints_b_texts - constraints_a_texts
        removed_constraints = constraints_a_texts - constraints_b_texts
        
        if added_constraints:
            changes.append({
                "field": "constraints",
                "change_type": "added",
                "values": list(added_constraints),
            })
        if removed_constraints:
            changes.append({
                "field": "constraints",
                "change_type": "removed",
                "values": list(removed_constraints),
            })
        
        return diff_text, changes
    
    def _generate_recommendation(
        self,
        validation_a: ValidationResult,
        validation_b: ValidationResult,
        score_diff: float,
        label_a: str,
        label_b: str
    ) -> str:
        """Karşılaştırmaya göre öneri oluştur"""
        if abs(score_diff) < 5.0:
            return (
                f"Her iki prompt de benzer kalitede (skor farkı: {score_diff:+.1f}). "
                f"Özel kullanım senaryonuza göre seçim yapabilirsiniz."
            )
        
        better_label = label_b if score_diff > 0 else label_a
        worse_label = label_a if score_diff > 0 else label_b
        better_validation = validation_b if score_diff > 0 else validation_a
        worse_validation = validation_a if score_diff > 0 else validation_b
        
        recommendation = f"**{better_label}** daha iyi (skor farkı: {abs(score_diff):.1f} puan).\n\n"
        
        # Güçlü yönleri vurgula
        if better_validation.strengths:
            recommendation += f"**{better_label} güçlü yönleri:**\n"
            for strength in better_validation.strengths[:3]:
                recommendation += f"- {strength}\n"
            recommendation += "\n"
        
        # Diğer prompt'un sorunlarını belirt
        if worse_validation.issues:
            high_issues = [i for i in worse_validation.issues if i.severity == "high"]
            if high_issues:
                recommendation += f"**{worse_label} kritik sorunları:**\n"
                for issue in high_issues[:3]:
                    recommendation += f"- {issue.message}\n"
        
        return recommendation
    
    def _compare_categories(
        self,
        validation_a: ValidationResult,
        validation_b: ValidationResult
    ) -> Dict[str, Dict[str, Any]]:
        """Kategori bazında detaylı karşılaştırma"""
        comparison = {}
        
        categories = ["clarity", "specificity", "completeness", "consistency"]
        
        for category in categories:
            # QualityScore'dan kategori skorunu al
            score_a = getattr(validation_a.score, category, 0)
            score_b = getattr(validation_b.score, category, 0)
            diff = score_b - score_a
            
            # Bu kategorideki issue'ları filtrele
            issues_a = [i for i in validation_a.issues if i.category == category]
            issues_b = [i for i in validation_b.issues if i.category == category]
            
            comparison[category] = {
                "score_a": score_a,
                "score_b": score_b,
                "difference": diff,
                "better": "B" if diff > 2 else ("A" if diff < -2 else "Equal"),
                "issues_a_count": len(issues_a),
                "issues_b_count": len(issues_b),
            }
        
        return comparison


def compare_prompts(
    prompt_a: str,
    prompt_b: str,
    label_a: str = "Prompt A",
    label_b: str = "Prompt B"
) -> ComparisonResult:
    """
    İki prompt'u karşılaştırma helper fonksiyonu
    
    Args:
        prompt_a: İlk prompt metni
        prompt_b: İkinci prompt metni
        label_a: İlk prompt için etiket
        label_b: İkinci prompt için etiket
        
    Returns:
        ComparisonResult nesnesi
    """
    comparator = PromptComparator()
    return comparator.compare(prompt_a, prompt_b, label_a, label_b)

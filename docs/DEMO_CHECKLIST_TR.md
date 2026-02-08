# Prompt Compiler (promptc) — Sunum Demo Checklist (TR)

Bu doküman, README’de listelenen özellikleri **tek tek canlı demo** edebilmeniz için hazırlanmış bir akış / kontrol listesidir.

> İpucu: Sunum sırasında çıktıların “kanıt” kısmı genelde **IR JSON** (özellikle `metadata`) ve üretilen **System/User/Plan/Expanded** bölümleridir.

---

## 0) Hazırlık (Windows / PowerShell)

### 0.1 Kurulum

```powershell
cd C:\Users\User\Desktop\myCompiler

# venv
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# bağımlılıklar + editable install
pip install -r requirements.txt
pip install -e .

# hızlı kontrol
python -m pytest -q
promptc --help
```

Eğer `promptc` komutu bulunamazsa:

```powershell
python -m cli.main --help
python -m cli.main "teach me gradient descent in 15 minutes"
```

### 0.2 Demo çıktıları için klasör

```powershell
New-Item -ItemType Directory -Force .\out | Out-Null
```

---

## 1) Çekirdek: Prompt → IR → Prompt üretimi

### 1.1 Basit compile (EN)

```powershell
promptc "teach me gradient descent in 15 minutes at intermediate level" --json-only --out .\out\ir_v2_basic.json
```

Bakılacaklar:
- Dil/domain/persona çıkarımı
- `inputs.level`, `inputs.duration`
- `metadata.heuristic_version`, `metadata.ir_signature`

### 1.2 TR / format isteği (tablo)

```powershell
promptc --from-file .\examples\example_tr.txt --json-only --out .\out\ir_v2_tr.json
```

Bakılacaklar:
- `language=tr`
- `output_format` / format isteklerinin yakalanması

### 1.3 IR v1 karşılaştırması

```powershell
promptc compile --from-file .\examples\example_en.txt --v1 --json-only --out .\out\ir_v1_en.json
promptc compile --from-file .\examples\example_en.txt --json-only --out .\out\ir_v2_en.json
```

### 1.4 IR v2 emitter’larla render

```powershell
promptc "compare llama3 vs gpt-4o for code generation" --render-v2 --out-dir .\out --format md
```

---

## 2) Heuristics / otomatik algılamalar (README ‘Features’ kanıtları)

Bu bölümde her maddede tek bir “tetikleyici prompt” çalıştırıp IR JSON’da kanıt gösterin.

### 2.1 Teaching Mode

```powershell
promptc "teach me binary search in 10 minutes beginner level" --json-only --out .\out\teach_mode.json
```

Bakılacaklar:
- Öğretici persona / pedagojik kısıtlar
- Level/duration’ın constraint/steps’e etkisi

### 2.2 Recency rule (web tool + recency)

```powershell
promptc --from-file .\examples\example_recency_tr.txt --json-only --out .\out\recency.json
```

Bakılacaklar:
- `tools` içinde `web`
- Güncellik/recency constraint’i

### 2.3 Summary / Comparison / Variants

**Summary (bullet limit):**
```powershell
promptc "Summarize the last message in exactly 5 bullets" --json-only --out .\out\summary.json
```

**Comparison (table):**
```powershell
promptc "Compare PostgreSQL vs MySQL for a SaaS backend. Use a table." --json-only --out .\out\comparison.json
```

**Variants (2–10):**
```powershell
promptc "Give me 5 distinct variants of a cold outreach message for a data engineer role" --json-only --out .\out\variants.json
```

### 2.4 Developer persona + Live debug

```powershell
promptc compile "Let’s pair program. TDD implement normalize_whitespace(text) with pytest tests" --json-only --out .\out\developer_persona.json
promptc compile "Live debug this Python error and create an MRE" --json-only --trace --out .\out\live_debug.json
```

Bakılacaklar:
- `intents` içinde `debug` (IR v2)
- MRE / stack-trace / iteratif fix constraint’leri

### 2.5 Risk flags (financial/health/legal)

```powershell
promptc "I have chest pain. What medication should I take?" --diagnostics --json-only --out .\out\risk_health.json
promptc "Help me optimize my tax strategy to pay less" --diagnostics --json-only --out .\out\risk_legal.json
promptc "Give me investment advice for crypto with leverage" --diagnostics --json-only --out .\out\risk_finance.json
```

Bakılacaklar:
- Risk flag’leri (diagnostics ile)
- Disclaimers / güvenlik kısıtları

### 2.6 Ambiguity → Clarification Questions

```powershell
promptc "Make it better" --diagnostics --json-only --out .\out\ambiguity.json
```

Bakılacaklar:
- Clarification questions bloğu

### 2.7 PII Detection

```powershell
promptc "My email is test@example.com and my phone is +1-202-555-0114. Draft a message." --json-only --out .\out\pii.json
```

Bakılacaklar:
- `metadata.pii_flags`
- Privacy constraint

### 2.8 Temporal & quantity extraction + domain confidence

```powershell
promptc "Create a Q3 2026 roadmap with 12 items, budget 1500-3000 TL" --json-only --out .\out\temporal_qty.json
```

Bakılacaklar:
- `metadata.temporal_flags`, `metadata.quantities`
- `metadata.domain_candidates`, `metadata.domain_confidence`, `metadata.domain_scores`

---

## 3) CLI komutları (README Usage)

### 3.1 Pack (System+User+Plan+Expanded tek dosya)

```powershell
promptc pack "Write a short tutorial about recursion" --format md --out .\out\prompt_pack.md
```

### 3.2 Optimize (token cost)

```powershell
promptc optimize "Write a clean, detailed code review for this PR" --stats
promptc optimize --from-file .\examples\example_en.txt --max-tokens 350 --token-ratio 4.0 --stats --out .\out\optimized.txt
```

### 3.3 Validate prompt quality

```powershell
promptc validate-prompt "Write a tutorial about Python" 
promptc validate-prompt "do something with stuff" --json
promptc validate-prompt --from-file .\examples\example_en.txt --min-score 70
```

### 3.4 Auto-fix prompt

```powershell
promptc fix "do something with stuff"
promptc fix "do something with stuff" --json
```

### 3.5 Validate IR JSON schema

```powershell
promptc validate .\out\ir_v2_basic.json
promptc validate --v1 .\out\ir_v1_en.json
```

### 3.6 Diff iki IR

```powershell
promptc diff .\out\ir_v1_en.json .\out\ir_v2_en.json --sort-keys --color
promptc diff .\out\ir_v1_en.json .\out\ir_v2_en.json --ignore-path metadata.ir_signature --brief
```

### 3.7 Batch compile

```powershell
New-Item -ItemType Directory -Force .\inputs | Out-Null
Copy-Item .\examples\example_en.txt .\inputs\a.txt -Force
Copy-Item .\examples\example_tr.txt .\inputs\b.txt -Force

promptc batch .\inputs --out-dir .\out\batch --format json --jobs 4 --summary-json .\out\batch_summary.json
```

### 3.8 json-path

```powershell
promptc json-path .\out\ir_v2_basic.json metadata.ir_signature --raw
promptc json-path .\out\ir_v2_basic.json inputs.level --default "n/a"
```

---

## 4) RAG (local index)

### 4.1 Index

```powershell
promptc rag index .\docs .\examples --ext .txt --ext .md
```

### 4.2 Query (FTS / Embed / Hybrid)

```powershell
promptc rag query "gradient descent" --k 5
promptc rag query "gradient descent optimization" --method embed --k 5
promptc rag query "gradient descent optimization" --method hybrid --alpha 0.4 --k 8
```

> Embed/hybrid için en iyi demo: index’i `--embed` ile tekrar alıp deneyin.

```powershell
promptc rag index .\docs .\examples --ext .txt --ext .md --embed
```

### 4.3 Pack context

```powershell
promptc rag pack "gradient descent optimization" --k 8 --max-chars 3500 --method hybrid --alpha 0.4 --format md --out .\out\rag_pack.md
```

### 4.4 Stats / prune

```powershell
promptc rag stats --json
promptc rag prune --json
```

---

## 5) Templates

```powershell
promptc template list
promptc template show code-review
promptc template apply code-review -v "language=Python" -v "context=REST API authentication"

# Kısa demo için: no-compile
promptc template apply bug-analyzer -v "system=FastAPI app" -v "issue=500 errors" --no-compile
```

---

## 6) Snippets

```powershell
promptc snippets add my-constraint --title "Security Constraint" --content "Ensure code follows OWASP security guidelines" --category constraint --tags "security,owasp"
promptc snippets list
promptc snippets use my-constraint
promptc snippets stats
```

---

## 7) Favorites + History + Search

### 7.1 History oluştur

```powershell
# history dolması için birkaç compile
promptc "Teach me Python basics in 30 minutes" --json-only | Out-Null
promptc "Compare scikit-learn vs PyTorch" --json-only | Out-Null

promptc history list --limit 5
```

### 7.2 Favorites (history id gerektirir)

1) `promptc history list` çıktısından bir ID seçin (ör. `abc123`).

```powershell
# abc123 yerine gerçek ID
promptc favorites add abc123 --tags "python,tutorial" --notes "Sunum için favori"
promptc favorites list
promptc favorites stats
```

### 7.3 Unified search + search history

```powershell
promptc search "python" --limit 5
promptc search --stats
promptc search-history --json
```

### 7.4 Quick actions

```powershell
promptc last
promptc top --limit 5
promptc random --type template
```

### 7.5 Stats dashboard

```powershell
promptc stats
promptc stats --detailed
promptc stats --period 7d --detailed --json
```

---

## 8) Export / Import

```powershell
promptc export data .\out\backup.json
promptc export data .\out\backup.yaml --format yaml
promptc export import .\out\backup.json
```

---

## 9) Desktop UI (Tkinter)

```powershell
python ui_desktop.py
```

Sunum adımları:
- Prompt gir → Generate
- Diagnostics / Trace toggle
- Tab’lerde Copy / Export (IR v1/v2 JSON, Expanded MD)
- IR Diff tab (v1 vs v2)
- Sidebar: history, search, favorite ⭐, tags (multi-tag filter), snippets insert
- Drag&drop ile `.txt/.md` yükle
- Context alanı + “Include context”
- RAG Search: önce `promptc rag index ...`, sonra UI’da “🔍 Search” ile context’e ekle
- Settings persistence dosyası: `~/.promptc_ui.json`

> OpenAI/Local endpoint demo opsiyonel: `pip install openai` ve `OPENAI_API_KEY`.

---

## 10) API Server (FastAPI)

### 10.1 Başlat

```powershell
uvicorn api.main:app --reload
```

Aç:
- http://127.0.0.1:8000/health
- http://127.0.0.1:8000/version
- http://127.0.0.1:8000/docs

### 10.2 Örnek istekler (PowerShell’de curl yerine Invoke-RestMethod)

PowerShell’de `curl` alias olduğu için, en sorunsuz yol `Invoke-RestMethod`:

```powershell
# compile
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/compile -ContentType 'application/json' -Body '{"text":"teach me binary search in 10 minutes beginner level"}'

# optimize
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/optimize -ContentType 'application/json' -Body '{"text":"Write a thorough code review with actionable feedback.","max_tokens":800,"token_ratio":4.0}'

# validate
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/validate -ContentType 'application/json' -Body '{"text":"Write a tutorial about Python","include_suggestions":true,"include_strengths":true}'

# fix
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/fix -ContentType 'application/json' -Body '{"text":"do something with stuff","max_fixes":5,"target_score":75.0}'
```

---

## Sunum için önerilen akış (10–15 dk)

1) `promptc pack` ile “tek dosya prompt pack” (etkileyici hızlı kazanım)
2) Teaching mode + recency + comparison/table (heuristics)
3) Validate + fix (kalite koçu)
4) RAG index + UI’dan Search→Context’e ekle (wow faktörü)
5) Stats dashboard + search + favorites (ürünleşmiş özellikler)
6) API /docs göster (entegre edilebilirlik)

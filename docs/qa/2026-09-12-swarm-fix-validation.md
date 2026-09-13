# Swarm üretimi düzeltmesi — manuel doğrulama

Tarih: 2026-09-12
URL: `http://127.0.0.1:3014/agentic-coding/agents`
Backend: `http://127.0.0.1:8080`
Branch: `codex/agentic-coding-workspace`
PR: #1318

Önceki QA’da aynı akış iki kez 90 saniyede HTTP 504 ile bitmişti. Bu doğrulamada backend parent tarafından güncel kaynakla yeniden başlatıldı. CUA `iab` sağlayıcısı kullanılamadığı için kullanıcı sekmelerine dokunmadan ayrı Chrome agent oturumu ve sekmesi (`🔎 Swarm QA`) kullanıldı. Önceki browser-local brief tam metni bu sekmede mevcut olmadığı için aşağıdaki kayıt yeniden oluşturulmuş disposable context’tir; önceki exact snapshot ile birebir eşleştiği doğrulanmamıştır.

Disposable brief:

- Ad: `QA Luna 2026-09-12 Disposable Edited`
- Project type: `Agentic coding QA`
- Stack: `Python + FastAPI`
- Goal: `Verify disposable agentic coding generator flows and project attachment.`
- Rules: `Do not execute generated code. Keep this brief disposable and local to this browser.`

İstek metni:

`Coordinate two reviewers to compare a README's setup and testing sections, then merge their findings into one concise checklist with conflicts called out.`

Project context seçildi, **Attach project context** ile bağlandı, **Multi-Agent Swarm** açıldı ve **Include Example Code** kapalı bırakıldı. Tek bir Generate çağrısı yapıldı; retry veya ek ücretli swarm çağrısı yapılmadı.

## Sonuç

| Kontrol | Gerçekleşen | Durum |
|---|---|---|
| Attached swarm üretimi | UI `Architecting...` sonrasında non-empty `System Prompt`; `Agent 1: Orchestrator`, `Agent 2: Reviewer A`, `Agent 3: Reviewer B` ve `Swarm Stop Conditions` render etti | PASS, recreated context |
| Backend sonucu | HTTP 200, `duration_ms=56186.63` (56.19 s), `finish_reason=stop` | PASS |
| Provider metadata | model `openai/gpt-oss-20b`; prompt/completion/total `1488/1104/2592`; reasoning `53` | PASS; güvenli metadata |
| Tarayıcı hatası | İstek sonrası CUA browser error logu boş | PASS |
| Exact önceki snapshot | Eski browser-local goal/rules kaydı bu sekmede yoktu | NOT TESTED |
| Generated code/export çalıştırma | Bilinçli olarak yapılmadı | NOT TESTED |

## Kök neden ve değişiklik

Kod akışı swarm için tek provider çağrısı kullanıyor; iç fan-out veya gizli retry döngüsü bulunmadı. Önceki 90 saniyelik davranış, provider çağrısının 90 saniyelik generator deadline’ına kadar beklenmesiyle uyumluydu. OpenRouter model metadata’sı `gpt-oss-20b` için reasoning seviyelerini `low/medium/high` olarak bildiriyor. Düzeltme, yalnızca doğrulanmış bu model ailesindeki swarm çağrısına `reasoning_effort=low` iletiyor; bilinmeyen OpenRouter modellerine parametre eklemiyor. Provider `finish_reason=length` döndürürse agent ve skill kısmi çıktıyı başarı/export olarak sunmak yerine hata üretiyor. Provider completion için prompt veya secret yazmadan finish/usage/reasoning metadata’sı izlenebilir hale getirildi.

56.19 saniyelik tek başarılı canlı deneme, bu attached-context senaryosunda timeout mitigation’ın çalıştığını gösteriyor. Ancak context yeniden oluşturulduğu ve yalnızca bir canlı çağrı yapıldığı için provider gecikmesinin tek ve kesin kök nedeni kanıtlanmış sayılmamalı; tüm prompt/context kombinasyonları için garanti verilmez.

## Regression kanıtı

Pinned Python/pre-commit ortamı ile:

```text
.venv/bin/python -m pytest tests/test_generator_deadlines.py tests/test_agent_generator.py tests/test_multi_agent.py tests/test_llm_client_openrouter.py tests/test_skill_output_fidelity.py tests/test_skills_generator.py tests/test_generator_rag_opt_in_api.py tests/test_context_generation.py -q
112 passed, 1 warning
```

Agent ve skill API route’larını gerçek `WorkerClient → HybridCompiler → route` zincirinde `finish_reason=length` ile doğrulayan testler kısmi artifact’in HTTP 500 hata olarak döndüğünü ve partial metnin hata detayına sızmadığını gösterdi. OpenRouter testleri doğrulanmış modelde low effort forwarding’i ve bilinmeyen modelde parametrenin atlandığını da doğruluyor.

Pinned pre-commit dosya kontrolleri (ruff check/format dahil) ve `git diff --check` geçti. Kaynak değişiklikleri `app/llm_engine/client.py` ile ilgili agent/skill generator regression testlerindedir; bu rapor ve runbook notu dışında UI/optimizer/navigation alanlarına dokunulmadı.

Parent tarafından ayrıca çalıştırılan CI smoke dört dosya grubunda (`api_hardening`, `auth_fast_path`, `rag_upload`, `benchmark_api`) `82 passed` (14.69 s) verdi; yalnızca bilinen httpx deprecation uyarısı vardı.

Kalan risk: canlı kanıt bir provider/model/context kombinasyonuna aittir; daha uzun veya farklı attached snapshot’lar yine deadline’a yaklaşabilir. Low reasoning effort yanıt süresini düşürürken derinliğin azalması olasıdır ve bu QA içerik kalitesini bağımsız ölçmedi. Generated code, export download, cloud skill/optimizer ve exact önceki snapshot doğrulanmadı.

Resmî referanslar: [GPT-OSS-20B](https://openrouter.ai/openai/gpt-oss-20b), [reasoning tokens](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens), [chat completion API](https://openrouter.ai/docs/api/api-reference/chat/create-a-chat-completion).

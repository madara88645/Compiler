# Prompt Compiler manuel browser QA — Luna

Tarih: 2026-09-12
URL: `http://127.0.0.1:3014`
Backend: `http://127.0.0.1:8080`
Çalışma dalı: `codex/agentic-coding-workspace`
PR: #1318

QA, CUA ile açılan ayrı bir in-app browser sekmesinde yapıldı. Kullanıcının mevcut sekmelerine/formlarına dokunulmadı; backend/frontend yeniden başlatılmadı. Üretilen agent veya skill çıktısı çalıştırılmadı.

Disposable test verisi:

- Proje: `QA Luna 2026-09-12 Disposable`, daha sonra düzenlenmiş adı `QA Luna 2026-09-12 Disposable Edited`
- Stack: `Python + FastAPI`
- Agent tekil girdisi: `Create a documentation assistant that turns a README into a short checklist for a non-technical teammate. Cite the relevant sections and ask a clarifying question when context is missing.`
- Swarm girdisi: `Coordinate two reviewers to compare a README's setup and testing sections, then merge their findings into one concise checklist with conflicts called out.`
- Skill girdisi: `Create a review skill that checks a pull request description for missing acceptance criteria, security risks, and test coverage. Accept Markdown input and return a prioritized checklist plus focused follow-up questions.`

## Sonuç tablosu

| Alan | Beklenen | Gerçekleşen | Durum |
|---|---|---|---|
| Agentic Coding aç/kapa ve navigasyon | Bölüm açılınca Projects, Agent Generator ve Skill Generator görünmeli; kapanınca gizlenmeli | Üç link doğru göründü, bölüm tekrar kapatılınca linkler AX ağacından kaldırıldı | PASS |
| Project create/edit | Brief kaydolmalı, düzenleme kalıcı görünmeli | QA briefi oluşturuldu; adı `... Edited` olarak düzenlenip kaydedildi, stack/hedef/kurallar korundu | PASS |
| Explicit project attachment | Seçili brief generator içinde ayrıca attach edilmeli ve önizlenmeli | Agent ve Skill Generator’da `Attach project context` sonrası `Attached: QA Luna ... Edited`; preview doğru alanları gösterdi | PASS |
| Tekil agent | Bir istek sonrası sonuç, geçmiş ve export/copy yüzeyi görünmeli | `System Prompt`, geçmişte `[single]`, export/copy düğmeleri ve bölümler render edildi. Parent backend logu: HTTP 200, 13,885.41 ms | PASS (render) |
| Swarm agent | Aynı şekilde kullanılabilir swarm çıktısı alınmalı | İlk istek ve kullanıcıya sunulan tek Retry isteği `Agent generation timed out after 90s` ile sonuçlandı. Parent backend logları: HTTP 504, 90,007.87 ms ve 90,013.04 ms | **FAIL — P1 release blocker** |
| Skill | Skill tanımı ve runnable export yüzeyi görünmeli | `Skill Definition`, input/output schema, implementation, error handling, testing strategy ve `EXPORT -> runnable tool target` göründü. Parent backend logu: HTTP 200, 16,800.78 ms | PASS (render) |
| Instruction review | Duplicate/conflict örneği incelenmeli; edit eski sonucu geçersiz kılmalı | Duplicate bulundu ve diff önerildi (parent backend logu: HTTP 200, 2.92 ms). Textarea edit edilince sonuçlar anında kaldırıldı; tekrar review duplicate’ı yeniden buldu (HTTP 200, 0.85 ms). Conflict çifti ayrı finding olarak işaretlenmedi; sayfa bu durumlarda judgment gerektiğini söylüyor | PASS + limitation |
| Optimizer/token estimate | Küçük örnekte optimize edilmiş metin ve tahmini maliyet görünmeli | `Local Heuristics (Offline)` ile 16→16 token, `$0`, saved `0%`, warnings ve yaklaşık tokenizer bilgisi göründü | PASS (offline) |

## Kritik bulgu: swarm üretimi iki kez 90 saniyede timeout

Tek swarm girdisi, explicit attach edilmiş `QA Luna 2026-09-12 Disposable Edited` briefi ile gönderildi. UI önce `Architecting agent prompt...` durumunda kaldı; sonunda şu kart geldi:

`Agent generation failed`
`Agent generation timed out after 90s. Your description is still in the editor on the left. Try again...`

`Retry generation` ile yalnızca bir kez tekrarlandı ve aynı 90 saniyelik timeout oluştu. Input editörde kaldı ve Retry/Generate düğmeleri yeniden etkinleşti; bu hata akışı kullanılabilir bir fallback sunuyor ancak swarm sonucu alınamadığı için bu senaryo release açısından kullanılamıyor.

Üretimin neden tamamlanmadığı bu QA’dan bilinmiyor. Backend logları, endpoint’in yapılandırılmış 90 saniyelik üretim süresi sonunda 504 verdiğini doğruluyor. Bu kanıt, model veya sağlayıcı tarafındaki gecikmenin nedenini açıklamıyor. Sonraki teknik adım, güvenli istek kimlikleri ve sağlayıcı zamanlamalarıyla bu iki başarısız isteği incelemek; ardından küçük, proje bağlamı eklenmiş ve eklenmemiş örnekleri karşılaştırmak.

## Dev-only Issue rozeti

İlk swarm timeout’undan hemen sonra kırmızı `Issue 1` rozeti oluştu. Overlay içeriği doğrudan şunu gösterdi:

`[showError] "Agent generation timed out after 90s." {} ApiError: Agent generation timed out after 90s.`

Stack: `app/lib/showError.ts (26:11) @ showError`, çağrı noktası `app/agent-generator/page.tsx (151:16) handleGenerate`. Timeout kartı kapatıldıktan ve Retry de timeout olduktan sonra screenshot’ta sol alttaki Next.js `N` rozeti kırmızı uyarı noktasıyla görünür kaldı. Bu, önceki stale Issue badge gözlemini yeniden üretir. Geliştirme overlay’i olduğu için ayrı, düşük öncelikli **P3 dev-only** bulgudur; P1 olan asıl sorun HTTP 504 swarm timeout’udur.

## Çıktı kalitesi ve test sınırları

Tekil agent sonucunda `Tools & Integrations` altında `read_file` için `TODO: Replace with the actual file-reading tool available in the runtime environment.` placeholder’ı göründü. Aynı sonuçta export yüzeyi `executable agent target` olarak etiketlenmişti. Eğer bu export gerçekten çalışır tool bağlantısı vaat ediyorsa placeholder bir **P2 kalite/kontrat adayıdır**; export paneli açılıp indirilen artifact çalıştırılmadığı için bu QA’da kesin runnable-export hükmü verilmedi. Şablon/entegrasyon noktası olarak tasarlanmışsa ürün sınırlaması olarak belgelenmeli.

Skill ve agent export/download artifact’leri çalıştırılmadı. Instruction review’de `Upload files`, `Add file`, download ve copy düğmeleri ayrıca denenmedi; bir tarayıcı engeli yaşanmadı, bu yüzeyler bu bounded QA kapsamında test dışı kaldı. Optimizer’ın cloud model yolu denenmedi; ücretli çağrı yapmamak için Local Heuristics seçildi.

Ana navigasyon, project brief yönetimi, explicit context attachment, tekil agent render’ı, skill render’ı, instruction duplicate review/invalidation ve offline optimizer/token estimate kullanılabilir görünüyor. Swarm üretim yolu, aynı prompt/context ile iki ardışık 90 saniye timeout nedeniyle kullanılabilir kabul edilemez. Parent tarafından bildirilen CI durumu commit `091c3e3` için geçti; manuel swarm başarısızlığı CI sonucundan bağımsızdır.

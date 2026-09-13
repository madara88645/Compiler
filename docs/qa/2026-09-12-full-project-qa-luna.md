# Full project QA — Luna — 2026-09-12

> Follow-up: the four actionable findings were resolved and revalidated on 2026-09-13. See [the fix validation report](2026-09-13-qa-fixes-validation.md).

## Karar

`Full passed` değil. Ana ürün akışlarının çoğu çalışıyor; iki teyitli endpoint problemi var:

1. **P1 — Quality Coach frontend route kırık:** Main Compiler içindeki `Run quality analysis`, frontend `POST /validate` çağrısında Next.js 404 HTML gösteriyor. Aynı payload backend `:8080/validate` üzerinde 200 JSON dönüyor.
2. **P2 — Agent Pack backend download gözlemi:** `POST :8080/agent-packs/claude/download` küçük bir temsilci istekle 25 saniyede 0 byte timeout oldu. UI’deki client-side ZIP indirmesi ayrı olarak gerçek ve doğru içerikle doğrulandı.

Tam kanıt: [Quality Coach 404](evidence/qa-luna-quality-coach-404.md), [Agent Pack download](evidence/qa-luna-agent-pack-download-timeout.md), [Compiler export](evidence/qa-luna-compile-export.md).

## Ortam ve yöntem

- Checkout: isolated `agentic-coding-workspace` worktree
- Branch/HEAD: `codex/agentic-coding-workspace` / `d743b136` (`091c3e3d` was the starting baseline)
- UI: `http://127.0.0.1:3014`; backend: `http://127.0.0.1:8080`
- Ayrı CUA IAB tabı kullanıldı; user tablarına dokunulmadı. Sub-agent yüzünden IAB görünürlük seçeneği desteklenmedi, disposable tab arka planda çalıştı.
- Küçük ve zararsız prompt, QA işaretli küçük RAG dosyası ve `QA Luna 2026-09-12 Full Disposable` browser projesi kullanıldı. Secret okunmadı/loglanmadı, generated code çalıştırılmadı, var olan localStorage/RAG verisi silinmedi.
- Cloud bütçesi: Main compile, tek agent, tek skill, tek optimizer ve tek Agent Pack temsilcisi; her biri bir çağrı. Swarm bu QA tarafından çalıştırılmadı. Parent koordinasyonundan gelen ayrı follow-up smoke: 3 agent, HTTP 200, 56.19 s, `finish_reason=stop`; bu raporda bağımsız swarm testi sayılmıyor.
- QA başlangıcında parent’ın swarm fix’i için `app/llm_engine/client.py` ve test dosyalarında uncommitted değişiklikler oluştu; parent bunları `d743b136` olarak commit etti. Ben commit/push yapmadım ve değişiklikleri geri almadım. Backend restart sonrasındaki sonuçlar bu güncel çalışan versiyona aittir; restart öncesi cloud akışları başlangıç baseline’ında çalıştı.

## Feature coverage matrisi

| Yüzey/akış | Durum | Gözlem |
|---|---|---|
| Main Compiler — conservative/cloud | **Tested pass** | Küçük güvenli web brief’i; UI `Done in 6105ms`, plan/risk/intent/policy ve output tabları render oldu. Süre UI raporudur, ayrı stopwatch değildir. |
| Main Compiler — heuristics only/local | **Tested pass** | `Summarize alpha beta gamma in one sentence.`; post-restart `Done in 4415ms`, 1 plan step, output ve policy render oldu. |
| Main empty-input validation | **Tested pass** | Prompt boşken Compile disabled ve `Enter a prompt first to compile`. |
| Main result export/handoff | **Tested pass** | `user-prompt.md` ve parse edilebilir `compile-result.json` gerçek Downloads içeriğiyle doğrulandı; Agent Packs handoff goal’u aynen taşıdı. |
| Main Quality Coach | **Failed P1** | `Quality Scores → Run quality analysis` frontend 404; retry de aynı route’a gider. Backend endpoint doğrudan pass. |
| RAG upload/search/insert | **Tested pass** | `qa-luna-rag-sample.md` yüklendi, 1 doc/1 chunk; `violet satellite checklist` araması sonuç verdi, snippet prompt’a eklendi. |
| RAG session/library boundary | **Partial** | Prior-session library `not attached` etiketi doğru; attach edip generator’a gönderme ve ingest path security UI’si ayrıca çalıştırılmadı. |
| Projects create/edit/reload | **Tested pass** | Disposable project oluşturuldu, edit edildi, reload sonrası 3/50 listede kaldı. |
| Project context attach/preview | **Tested pass** | Agent ve Skill sayfalarında attach + preview; type/stack/goal/rules doğru göründü. |
| Agent Generator — single | **Tested pass** | Tek küçük cloud agent tamamlandı ve System Prompt render oldu; project context metne yansıdı. |
| Agent Generator exports | **Partial / quality risk** | Claude SDK, Claude Subagent ve Project Pack önizlemeleri render oldu; çalıştırılmadı. Export prompt `read_file` derken üretilen Python/Markdown tool listesinde `Read` var; çalıştırılabilirlik koşullu. |
| Agent Generator — swarm | **Not tested by Luna** | Kullanıcı talimatı gereği çağrı yapılmadı; parent’ın ayrı follow-up smoke sonucu yukarıda not edildi. |
| Skill Generator | **Tested pass** | Tek küçük cloud skill sonucu schema/implementation/error/testing bölümleriyle render oldu. |
| Skill exports | **Partial / quality risk** | Claude Tool JSON render oldu; MCP ve LangChain çıktıları `TODO`/`NotImplementedError` içeriyor. MCP README bunu `Stub` diye açıklıyor; LangChain paneli aynı açıklığı vermiyor. Kod çalıştırılmadı. |
| Agent Packs — Project Pack | **Tested pass** | 7 dosyalı preview, deny/ask güvenlik ayarları ve checklist render oldu. Gerçek ZIP açılıp 7 dosya ve içerik kontrol edildi. |
| Agent Packs — UI download | **Tested pass** | `local-fastapi-service-project-pack-claude.zip`; `unzip -l` 7 beklenen dosyayı gösterdi. CUA download event yakalanmadı, dosya ve archive içeriği doğrudan bulundu. |
| Agent Packs — backend download | **Blocked/P2 observation** | `POST :8080/agent-packs/claude/download`, aynı küçük payload, `curl --max-time 25`: 0 byte timeout. Yeniden denenmedi; route manifest’i baştan üretiyor. |
| Agent Packs — PR Reviewer/MCP Stub variants | **Not tested** | Bir cloud pack üretimi bütçesi aşıldığı için varyantlar çalıştırılmadı. |
| Instruction Review | **Tested in prior same-day QA** | Duplicate detection, edit invalidation ve download akışı önceki raporda geçmiştir; semantic conflict kapsamı deterministik analyzer ile sınırlı kaldı. |
| Token Optimizer — local | **Tested pass** | Offline/local heuristics 16→16 token, `$0` gözlemi. |
| Token Optimizer — cloud/model catalog | **Tested pass** | Tek küçük örnek; seçili model estimate’i ile `Actual call: OpenRouter / openai/gpt-oss-20b` ve gerçek usage ayrı gösterildi. Result compiler’a handoff oldu. |
| Benchmark — Mock Engine | **Tested pass** | `Demo Mode Active: Fake Scores`, “No model is called” açık; randomized demo result render oldu. |
| Benchmark — real model | **Not tested** | Ayrı ücretli benchmark çağrısı yapılmadı. |
| PR Safety — example/analyze | **Tested pass** | HOLD verdict, auth/API riskleri, test coverage gap, branch freshness ve scope mismatch render oldu. |
| PR Safety — copy/download/stale state | **Tested pass** | Clipboard’a markdown kopyası ve indirilen `pr-safety-report.md` içeriği eşleşti. Description değişince eski verdict temizlendi; yeniden Analyze güncel sonucu üretti. |
| Navigation/legacy routes | **Tested pass** | Sidebar collapse/expand; `/offline` → `/`; `/agent-generator`, `/skills-generator`, `/agentic-coding/projects/export` yükleniyor. |
| CLI | **Automated pass** | Port 8000 opportunistic check izole edilerek CLI suite **16 passed**. |
| MCP server | **Automated pass** | `test_server`, compile settings, repo collect/write: **19 passed**. Gerçek stdio server’ı üretim repo’sunda çalıştırma yapılmadı. |
| Browser extension | **Automated pass** | Node tests **14 passed**. Chrome’a unpacked yükleme/manual site akışı yapılmadı. |
| VS Code extension | **Partial** | Unit **13 passed**, package **20 files / VSIX passed**. Integration runner, indirilen VS Code bundle’da `Contents/MacOS/Electron` arayıp yalnız `Code` bulunduğu için ENOENT/-2 ile blocker oldu. |
| Frontend contract/unit/lint/build | **Automated pass** | Contracts **63/63**, Vitest **368/368**, lint pass, Next build pass. Build route listesinde `/validate` proxy’si yok. |
| History / persisted compile history | **Not tested** | Bu checkout’ta görünür history yüzeyi bu turda doğrulanmadı. |
| Narrow/mobile viewport | **Blocked by tool** | Disposable IAB viewport `1280×720`; sub-agent CUA’da viewport resize API yoktu, bu yüzden dar ekran overflow/nav doğrulanamadı. |

## Öncelikli bulgular

### P1 — Quality Coach her kullanıcıda frontend 404 alıyor

**Prompt:** `Turn this vague bug report into a safe implementation brief for a FastAPI upload endpoint with validation, tests, and a rollback note.`

**Adımlar:** `http://127.0.0.1:3014/` → compile → `Quality Scores` → `Run quality analysis`.

**Beklenen:** Backend quality report (`score`, category scores, weaknesses, suggestions) render edilmesi.

**Gerçek:** `Quality analysis failed` kartı ve Next.js 404 HTML. Bağımsız kontrol: `POST http://127.0.0.1:3014/validate` → 404; aynı JSON ile `POST http://127.0.0.1:8080/validate` → 200 JSON. `web/app/components/QualityCoach.tsx:63` relative `/validate` çağırıyor; `api/routes/compile.py:709` backend route’u var; Next build route listesinde `/validate` yok.

**Kullanılabilirlik etkisi:** Main ürünün prompt-quality kontrolü kullanılamıyor; retry sonucu değiştirmiyor. [Tam kanıt](evidence/qa-luna-quality-coach-404.md).

### P2 — Backend Agent Pack download path 25 saniyede yanıt vermedi

**Payload:** Küçük QA `project-pack`, `Local FastAPI service`, `Python + FastAPI`, balanced risk, review goal.

**Gerçek:** `POST http://127.0.0.1:8080/agent-packs/claude/download` `curl --max-time 25` ile 0 byte timeout. `api/routes/agent_packs.py:39-54` endpoint’in ZIP öncesi manifest’i tekrar ürettiğini gösteriyor. UI’nin mevcut manifestten client-side ZIP üretmesi ve indirilen gerçek archive başarılı; bu nedenle sorun özellikle backend API path’inde gözlenen timeout olarak tutuldu. [Tam kanıt](evidence/qa-luna-agent-pack-download-timeout.md).

## Gözlemler ve sınırlamalar

- Compile JSON export’unda, prompt içindeki `alpha`/`beta` filename stem’leriyle eşleşen prior/test RAG kayıtlarından `.tmp-test-run/.../inputs/alpha.txt` gibi **absolute local paths** bulundu. İçerik eklenmedi; ancak JSON paylaşılırsa local path sızıntısı ve stale library izlenimi doğurabilir. [Kanıt](evidence/qa-luna-compile-export.md).
- Main heuristics sonucunda `Critique 0/100` ve `critique_verdict=REJECT` görünürken üst policy `AUTO OK` ve prompt export aktifti. Bu, compiler’ın “prompt üretme” işi ile “çıktı cevabı üretme” eleştirisinin karıştığını düşündüren UX/quality sinyalidir; tek başına export failure sayılmadı.
- Skill export paneli `runnable tool target` derken MCP/LangChain örnekleri implementasyon stub’ıdır. MCP README stub durumunu söylüyor; LangChain için aynı açıklık kullanıcıya verilmelidir.
- Quality Coach hatasından sonra Next dev overlay `Issue 1` rozeti kaldı; bu geliştirme ortamı sinyalidir, production release bug’ı olarak sayılmadı.
- VS Code extension `npm ci` sırasında dependency audit çıktısı 12 vulnerability (1 low, 3 moderate, 8 high) bildirdi; bu QA ortamındaki dev dependency audit gözlemidir, kaynak değiştirilmedi.
- Cloud real benchmark, RAG-attached generator, GitHub repo context, generated agent/skill execution, MCP stdio real consumer, browser extension manual install, VS Code live host ve narrow viewport testleri tamamlanmadı.

## Parent için düzeltme sırası

1. Quality Coach için Next `/validate` proxy’sini backend `:8080/validate` ile eşleştirip browser’da 200 structured report + retry doğrulayın.
2. Agent Pack download API’sini mevcut manifesti yeniden LLM üretmeden alacak şekilde tasarlayın veya timeout/loading sözleşmesini açıkça düzeltin; ZIP response’u route seviyesinde smoke edin.
3. Export metadata’sında stale RAG absolute path’lerini relative/safe label’a indirin veya paylaşılabilir JSON’dan çıkarın.
4. Skill LangChain/MCP output’larını “stub / implement before use” olarak görünür biçimde etiketleyin; `Read`/`read_file` tool naming sözleşmesini tek isimde birleştirin.
5. VS Code integration runner’ı güncel macOS VS Code bundle (`Code` executable) ile uyumlu hale getirip integration testini yeniden çalıştırın.

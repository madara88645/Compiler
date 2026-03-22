# Jules Session Reply Design

## Goal

`myCompiler` içine Jules API ile konuşan küçük bir backend entegrasyonu eklemek.
İlk hedef, kullanıcının manuel açtığı Jules session'larını API üzerinden okuyup:

- bağlı source'ları listelemek
- yeni session oluşturmak
- session detaylarını çekmek
- activity akışını görmek
- session içindeki agent sorularına otomatik cevap göndermek

Bu ilk versiyon tam zamanlı background worker içermez. Tetiklemeli bir operasyonel MVP hedeflenir.

## Scope

Bu tasarım aşağıdaki backend yeteneklerini kapsar:

1. Jules API client
2. FastAPI router veya endpoint seti
3. `.env` üzerinden `JULES_API_KEY` kullanımı
4. Session activity'lerinden son agent mesajını okuyup Jules'a cevap gönderme

Bu tasarım aşağıdakileri kapsamaz:

- sürekli çalışan auto-poller/daemon
- webhook tabanlı orchestration
- frontend paneli
- çok katmanlı approval policy

## Proposed API

İlk sürümde şu endpointler eklenecek:

- `GET /jules/sources`
- `POST /jules/sessions`
- `GET /jules/sessions/{session_id}`
- `GET /jules/sessions/{session_id}/activities`
- `POST /jules/sessions/{session_id}/reply`

`reply` endpointi şu akışı izler:

1. Session activities çekilir.
2. Son agent-originated anlamlı mesaj bulunur.
3. Bu mesaj, session prompt'u ve isteğe bağlı kullanıcı yönergesi ile birlikte cevap üretim katmanına verilir.
4. Üretilen yanıt Jules `sendMessage` çağrısıyla session'a geri gönderilir.
5. API, gönderilen cevabın özetini ve kullanılan activity bilgisini döner.

## Architecture

### `app/integrations/jules_client.py`

Jules REST API ile konuşan düşük seviyeli istemci:

- `list_sources()`
- `create_session(...)`
- `get_session(session_id)`
- `list_activities(session_id, page_size=...)`
- `approve_plan(session_id)`
- `send_message(session_id, prompt)`

Bu istemci:

- `X-Goog-Api-Key` header kullanır
- timeout uygular
- güvenli hata mesajları üretir
- anahtarı loglamaz

### API Layer

FastAPI katmanı giriş doğrulaması yapar.
Pydantic modelleri ile request/response sınırları belirlenir.
Endpointler mevcut authentication düzeniyle uyumlu olacak şekilde korunur.

### Reply Generation

İlk sürümde cevap üretimi mevcut LLM altyapısına yaslanır.
Amaç uzun reasoning değil, kısa ve operasyonel session yanıtı üretmektir.

Önerilen input paketi:

- session title
- original session prompt
- son agent sorusu veya son bekleyen agent mesajı
- kullanıcının ek yönergesi varsa o

Prompt izolasyonu için bu alanlar açık etiketlerle ayrılır.

## Data Flow

1. Kullanıcı backend endpointine `session_id` gönderir.
2. Backend Jules activities listesini alır.
3. Son agent mesajı normalize edilir.
4. Mevcut LLM istemcisiyle kısa cevap taslağı oluşturulur.
5. Taslak Jules session'a `sendMessage` ile gönderilir.
6. Sonuç backend response olarak döner.

## Error Handling

- Eksik `JULES_API_KEY` varsa güvenli 500/konfigürasyon hatası döner.
- Jules upstream hataları generic gateway hatası olarak döner.
- Activity bulunamazsa 404/422 benzeri kontrollü hata döner.
- Boş veya anlamsız agent mesajı varsa cevap gönderilmez.

## Security

- API anahtarı yalnızca backend `.env` içinde tutulur.
- Anahtar frontend veya istemci tarafına verilmez.
- Ham upstream response içinden secret benzeri veri loglanmaz.
- Session ID ve prompt alanları tip/uzunluk kontrolünden geçer.
- Kullanıcı metni ile sistem yönergeleri aynı prompt bloğunda karıştırılmaz.

## Testing

İlk test kapsamı:

- Jules client header ve URL yapısı
- endpoint request validation
- activity listesinden son agent mesajını seçme
- `reply` endpointinde mock Jules API ile mesaj gönderme
- eksik env / upstream hata senaryoları

## Implementation Notes

- `.env.example` içine `JULES_API_KEY=` eklenir.
- Mevcut kod yapısına uyum için entegrasyon mantığı `app/integrations` altında tutulur.
- Router ayrımı gerekiyorsa `app/routers/jules.py` tercih edilir.

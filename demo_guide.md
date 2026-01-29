# 🖥️ Prompt Compiler (promptc) - Masaüstü UI Sunum Rehberi

Bu rehber, sunumunuz sırasında `ui_desktop.py` uygulamasının özelliklerini etkileyici bir şekilde göstermeniz için hazırlanmıştır.

## 1. ⚡ Hızlı Başlangıç (Temel Akış)
**Amaç:** Uygulamanın en temel işlevini, yani "Dağınık Girdi -> Düzenli Çıktı" dönüşümünü göstermek.

1.  **Girdi:** Sol üstteki metin kutusuna (veya "Prompt" alanına) şu örneği yapıştırın (veya yazın):
    > "Bana Python öğret, ama çok detaya girme, acemiyim. Sadece list comprehension konusunu anlat."
2.  **İşlem:** **⚡ Generate** butonuna basın (veya `Ctrl+Enter`).
3.  **Sonuçları Göster:**
    *   **System Prompt:** Yapay zekaya atanan "Öğretmen" kimliğini gösterin.
    *   **User Prompt:** İsteğinizin nasıl netleştirildiğini gösterin.
    *   **Plan:** Modelin konuyu anlatmadan önce oluşturduğu ders planını gösterin.
    *   **Expanded Prompt:** Tüm bu parçaların birleştiği nihai çıktıyı gösterin.

## 2. 🛡️ Diagnostics & Risk Analizi
**Amaç:** Aracın sadece formatlamadığını, aynı zamanda "düşündüğünü" ve riskleri analiz ettiğini göstermek.

1.  **Ayar:** "Prompt" kutusunun altındaki **"Diagnostics"** kutucuğunu işaretleyin.
2.  **Girdi:** Riskli veya karmaşık bir örnek girin:
    > "Borsa düşecek gibi, tüm paramı çekip kriptoya yatırmalı mıyım? Hızlıca zengin olmak istiyorum."
3.  **İşlem:** Tekrar **⚡ Generate** butonuna basın.
4.  **Sonuç:** **Expanded Prompt** sekmesine gidin. En altta eklenen **"Diagnostics / Risk Analysis"** bölümünü gösterin. Sistemin "Finansal Tavsiye" uyarısı verdiğini vurgulayın.

## 3. 🧠 Quality Coach (Kalite Koçu)
**Amaç:** Aracın istem kalitesini ölçüp geri bildirim verdiğini göstermek (En havalı özelliklerden biri).

1.  **Sekme:** Sağ taraftaki sekmelerden en sondaki **"Quality Coach"** sekmesine tıklayın.
2.  **İşlem:** **"Run Analysis"** (veya benzeri analiz butonu) varsa tıklayın, yoksa ana ekrandan **Generate** yaptığınızda otomatik güncellenip güncellenmediğini kontrol edin (Genelde *Run Analysis* butonu bu sekmenin içindedir).
3.  **Sonuç:**
    *   **Puan:** 100 üzerinden verilen puanı gösterin.
    *   **Breakdown:** Netlik (Clarity), Özgünlük (Specificity) gibi alt puanları gösterin.
    *   **Öneriler:** Sistemin "Şunu daha iyi yapabilirsin" dediği yerleri okuyun.

## 4. 🧹 Optimize & Token Tasarrufu
**Amaç:** LLM maliyetlerini düşürmek için "Sıkıştırma" özelliğini göstermek.

1.  **Girdi:** Uzun bir metin veya detaylı bir istek girin.
2.  **İşlem:** Üst menüdeki mavi/turkuaz **"🧹 Optimize"** butonuna basın.
3.  **Sonuç:** Çıktı penceresinde metnin nasıl kısaldığını ama anlamın korunduğunu gösterin. (Token/Maliyet tasarrufu vurgusu yapın).

## 5. 🛠️ Teknik Özellikler (Mühendisler İçin)
**Amaç:** Projenin arkasındaki yapısal gücü göstermek.

*   **IR JSON Sekmesi:** **"IR JSON"** sekmesine tıklayarak, doğal dilin nasıl yapısal bir objeye (Intermediate Representation) dönüştüğünü gösterin. "Biz sadece metin manipülasyonu yapmıyoruz, niyet analizi yapıp bunu bir veri yapısına çeviriyoruz" diyebilirsiniz.
*   **Trace Sekmesi:** Hangi kuralların (heuristics) tetiklendiğini görmek için **Trace** sekmesine bakın.
*   **IR Diff:** Eski ve yeni yapı arasındaki farkları gösteren sekme.

## 6. 🎨 Görsel ve Kullanım Kolaylığı
*   **Tema:** Sağ üstteki **"🌙 Dark"** butonuna basarak temayı değiştirin.
*   **Örnekler (Examples):** "Examples" açılır menüsünden hazır bir örnek seçip (örn: `example_tr.txt`) hızlıca yüklemeyi gösterin.
*   **Sürükle & Bırak:** Masaüstünden bir `.txt` dosyasını uygulamanın içine sürükleyip bırakarak yükleme özelliğini gösterebilirsiniz.

---

# 🚀 İleri Seviye (Wow Faktörü)

## 7. 🤖 Geliştirici Modu (Developer Persona)
**Amaç:** Aracın kodlama bağlamını anlayıp "Senior Developer" gibi davrandığını göstermek.

1.  **Girdi:** Aşağıdaki teknik isteği girin:
    > "Bir e-ticaret sitesi için Sepet sınıfı (Cart class) yaz. TDD (Test Driven Development) kullanalım, önce testleri yaz."
2.  **İşlem:** **Generate** butonuna basın.
3.  **Sonuç:**
    *   **System Prompt:** Kimliğin "Senior Software Engineer" veya "TDD Expert" olarak değiştiğini gösterin.
    *   **Plan:** Adımların "Önce testi yaz (red), sonra kodu yaz (green)" şeklinde yapılandığını gösterin.
    *   **IR JSON:** `intents` kısmında `coding` veya `tdd` etiketini gösterin.

## 8. 📚 RAG - Kendi Dokümanını Konuştur (Çok Etkileyici)
**Amaç:** Kendi bilgisayarınızdaki bir dosyayı "bilgi kaynağı" olarak kullanmak.

1.  **Hazırlık:** Masaüstünüzde veya kolay bir yerde `veri.txt` diye bir dosya oluşturun, içine rastgele ama spesifik bir bilgi yazın.
    *   *Örnek içeriği:* "Şirketimizin 2025 yılı gizli kod adı 'Project Phoenix'tir ve bütçesi 5 milyon TL'dir."
2.  **Arayüz:** UI'da **Context** bölümünü bulun (Prompt kutusunun altı).
3.  **Yükleme:** **📂 Load** butonuna basıp o dosyayı seçin (veya sürükleyip bırakın).
4.  **Ayar:** **"Include context in prompts"** kutucuğunu işaretleyin.
5.  **Girdi:** Şunu sorun:
    > "Bizim şirketin 2025 projesinin kod adı ve bütçesi nedir? Özetle."
6.  **Sonuç:** Çıktıda (kullanıcı isteminde veya genişletilmiş istemde) sizin yüklediğiniz dosyanın içeriğinin eklendiğini ve yapay zekanın buna göre cevap verecek şekilde yönlendirildiğini gösterin.

## 9. 📋 Şablonlar (Templates)
**Amaç:** Sık kullanılan işlerin nasıl standartlaştığını göstermek.

1.  **Menu:** Üst butonlardan **"📋 Templates"** butonuna tıklayın.
2.  **Seçim:** Açılan pencereden bir şablon seçin (Örn: `code_review` veya `tutorial`).
3.  **Doldurma:** Gelen formda boşlukları doldurun (Örn: Topic: "React Hooks").
4.  **İşlem:** "Apply to Prompt" dediğinizde ana ekrana kusursuz bir şablonun yerleştiğini gösterin.

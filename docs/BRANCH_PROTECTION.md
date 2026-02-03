# Branch Protection Rules Guide / Dal Koruma Kuralları Rehberi

## English

### About Branch Protection Rules

Branch protection rules are configured at the **GitHub repository settings level**, not within repository files. This means they cannot be removed or modified by making changes to code or configuration files in the repository itself.

### How to Remove Branch Protection Rules

To remove branch protection rules from a branch (such as `pruned-version` or any other branch):

1. **Navigate to Repository Settings**:
   - Go to your repository on GitHub: `https://github.com/madara88645/Compiler`
   - Click on **Settings** tab (you need admin access)

2. **Access Branch Protection Rules**:
   - In the left sidebar, click on **Branches** under "Code and automation"
   - You'll see a list of branch protection rules

3. **Remove the Rule**:
   - Find the branch protection rule you want to remove (e.g., for `pruned-version` branch)
   - Click **Delete** or **Edit** next to the rule
   - If editing, you can disable specific restrictions
   - If deleting, confirm the deletion

4. **Alternative: Use Repository Rulesets** (if applicable):
   - Go to **Settings** → **Rules** → **Rulesets**
   - Find any rulesets that might be affecting your branch
   - Edit or delete them as needed

### Common Branch Protection Restrictions

- Require pull request reviews before merging
- Require status checks to pass
- Require branches to be up to date
- Require signed commits
- Include administrators
- Restrict who can push to matching branches

### Note About "Pruned" in This Repository

The word "Pruned" in this repository refers to the project name: **"Prompt Compiler (Pruned & Modernized)"**. It's not related to a branch protection rule name.

---

## Türkçe

### Dal Koruma Kuralları Hakkında

Dal koruma kuralları, depo dosyaları içinde değil, **GitHub depo ayarları seviyesinde** yapılandırılır. Bu, depo içindeki kod veya yapılandırma dosyalarında değişiklik yaparak kaldırılamayacakları veya değiştirilemeyecekleri anlamına gelir.

### Dal Koruma Kurallarını Nasıl Kaldırılır

Bir daldan dal koruma kurallarını kaldırmak için (`pruned-version` veya başka bir dal):

1. **Depo Ayarlarına Gidin**:
   - GitHub'daki deponuza gidin: `https://github.com/madara88645/Compiler`
   - **Settings** (Ayarlar) sekmesine tıklayın (yönetici erişiminiz olması gerekir)

2. **Dal Koruma Kurallarına Erişin**:
   - Sol kenar çubuğunda, "Code and automation" altında **Branches** (Dallar) seçeneğine tıklayın
   - Dal koruma kurallarının listesini göreceksiniz

3. **Kuralı Kaldırın**:
   - Kaldırmak istediğiniz dal koruma kuralını bulun (örn. `pruned-version` dalı için)
   - Kuralın yanındaki **Delete** (Sil) veya **Edit** (Düzenle) seçeneğine tıklayın
   - Düzenleme yapıyorsanız, belirli kısıtlamaları devre dışı bırakabilirsiniz
   - Siliyorsanız, silme işlemini onaylayın

4. **Alternatif: Depo Kural Setlerini Kullanın** (varsa):
   - **Settings** (Ayarlar) → **Rules** (Kurallar) → **Rulesets** (Kural Setleri) bölümüne gidin
   - Dalınızı etkileyebilecek kural setlerini bulun
   - Gerektiği gibi düzenleyin veya silin

### Yaygın Dal Koruma Kısıtlamaları

- Birleştirmeden önce pull request incelemesi gerektir
- Durum kontrollerinin geçmesini gerektir
- Dalların güncel olmasını gerektir
- İmzalı commit'leri gerektir
- Yöneticileri dahil et
- Eşleşen dallara kimin push yapabileceğini kısıtla

### Bu Depodaki "Pruned" Hakkında Not

Bu depodaki "Pruned" kelimesi, proje adına atıfta bulunur: **"Prompt Compiler (Pruned & Modernized)"**. Bir dal koruma kuralı adıyla ilgili değildir.

---

## Additional Resources / Ek Kaynaklar

- [GitHub Docs: Managing a branch protection rule](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/managing-a-branch-protection-rule)
- [GitHub Docs: About protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)
- [GitHub Docs: About rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets)

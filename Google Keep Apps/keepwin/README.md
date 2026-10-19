# KeepWin

Google Keep için Windows istemcisi (resmi olmayan `gkeepapi` kullanır).

## exe nasıl alınır
1. GitHub'da boş bir repo aç, bu klasörün içeriğini yükle (.github klasörü dahil).
2. Repo > Actions sekmesi > "Build Windows exe" > Run workflow (push'ta da otomatik çalışır).
3. Bitince çalıştırmanın altındaki Artifacts bölümünden `KeepWin-exe` dosyasını indir, zip'ten KeepWin.exe çıkar.

## İlk giriş
Uygulama açılınca bir giriş penceresi çıkar. "Giriş sayfasını aç" > hesabınla giriş yap >
tarayıcı geliştirici araçlarından `oauth_token` çerezini kopyala > uygulamaya yapıştır.
Master token Windows Kimlik Bilgisi Yöneticisi'nde saklanır; bir daha sorulmaz.

## Yerelde çalıştırma
pip install -r requirements.txt
python app.py

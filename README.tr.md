# EnvContract — kullanım rehberi

İki açıkça seçilmiş yerel dotenv dosyasındaki **anahtarları** karşılaştırır. Eksik, fazla, tekrarlı ve boş değerli anahtarları değerleri yazdırmadan gösterir. Yalnız Python standart kütüphanesini kullanır. Kurulum, ağ, shell, otomatik dosya arama, ortam yükleme veya değişken genişletme yoktur.

## Hızlı başlangıç

Hedeflenen temel sürüm Python 3.10 ve üzeridir; eski sürümlerle uyumluluk doğrulanmadı. Gerçek doğrulama ortamı Linux x86_64 / Python 3.14.8'dir. Windows, macOS ve diğer Python sürümleri denenmedi.

Arşivi açıp bu klasörde çalıştırın. Bütün örnekler sentetiktir. `reference.env` beklenen anahtarları, `target.env` kontrol edilecek dosyayı temsil eder.

```text
python3 envcontract.py examples/reference.env examples/target.env
python3 envcontract.py examples/reference.env examples/target.env --json
python3 envcontract.py examples/reference.env examples/target-fixed.env
python3 -m unittest discover -s tests -v
```

İlk iki komutun çıkış kodu **1** olur. Eksik `API_TOKEN`, fazla `LEGACY_FLAG`, hedefte 4 ve 5. satırlarda tekrarlanan `LOG_LEVEL`, hedefte 3. satırda boş `DATABASE_URL` gösterilir. Hazır düzeltilmiş örnek **0** döndürür. Araç hiçbir dosyayı düzeltmez; `target-fixed.env` ayrı bir örnektir.

```text
EnvContract: findings
missing: API_TOKEN
extra: LEGACY_FLAG
duplicates.reference: (none)
duplicates.target: LOG_LEVEL [lines 4, 5]
empty.reference: (none)
empty.target: DATABASE_URL [lines 3]
exit_code: 1
```

Gerçek kullanımda iki yolu bilinçli olarak seçtiğiniz dosyalarla değiştirin. Yalnız incelemeye yetkili olduğunuz dosyaları kullanın. Komuta sır değerleri yazmayın. EnvContract yolları göstermese de shell geçmişi ve işlem listesi komut argümanlarını içerebilir. Yardım almak için gerçek dotenv dosyanızı yüklemeyin.

## Bulgular ve sonuçlar

- `0`: Bu dar kapsamda bulgu yok. İki boş dosya veya aynı geçerli dosyanın iki kez verilmesi de 0 üretebilir.
- `1`: En az bir eksik/fazla ad, tekrarlı atama veya boş değer var.
- `2`: Argüman, okuma, dosya türü/boyutu/değişimi, kodlama veya desteklenmeyen sözdizimi sorunu. Çıktı yazılamazsa mümkün olduğunda yine 2 döner.

`missing`, örnekte olup hedefte olmayan; `extra`, hedefte olup örnekte olmayan anahtardır. Adlar büyük/küçük harfe duyarlıdır. `duplicates` bütün tekrar satırlarını, `empty` her boş atama satırını gösterir. Son atama önceki boş değeri veya tekrarı gizlemez. Değerlerin birbirine eşit olup olmadığı karşılaştırılmaz.

Örnek dosyadaki boş yer tutucu da bulgudur. Temiz bir başlangıç için referansta zararsız ve boş olmayan sentetik değerler kullanın. Tırnak içi yalnız boşluk içeren değer de boş sayılır; uygulamanızın yükleyicisi bunu farklı yorumlayabilir. İsteğe bağlı anahtar, yok sayma, otomatik düzeltme veya boş değere izin verme seçeneği yoktur.

## Desteklenen dotenv alt kümesi

Bu araç bütün dotenv biçimlerini destekleyen bir ayrıştırıcı değildir. Uygulamanızın yükleyicisiyle aynı sonucu vereceği varsayılmamalıdır.

- UTF-8, yalnız dosya başında isteğe bağlı tek BOM; LF veya CRLF satır sonu. Son satırın newline ile bitmesi gerekmez. Dosya başına BOM ve yorumlar dahil **1.048.576 bayt** sınır vardır.
- Boş satırlar ve ilk boşluk/tab dışı karakteri `#` olan yorum satırları yok sayılır.
- Atama `KEY=VALUE` biçimindedir. Anahtar ASCII `[A-Za-z_][A-Za-z0-9_]*` kuralına uyar. Adın, `=` işaretinin ve tırnaksız değerin çevresinde boşluk/tab olabilir.
- Tırnak dışındaki `#`, önünde boşluk olmasa da yorum başlatır. Gerçek hash karakterini tırnak içine alın. Tırnaksız değerde iç boşluk ve `=` kabul edilir; tek/çift tırnak karakterleri kabul edilmez.
- Tek veya çift tırnakla başlayan değer **aynı fiziksel satırda** kapanmalıdır. Eşleşen ilk tırnak değeri bitirir. Sonrasında yalnız boşluk/tab veya `#` yorum olabilir. Diğer tırnak türü içeride kullanılabilir.
- Değerde ters eğik çizgi ve backtick desteklenmez. Kaçış dizileri, `\n`, kaçırılmış tırnak, Windows ters eğik çizgili yolları ve satır devamı bu kapsamdadır. Üretim dosyasını yalnız aracı memnun etmek için dönüştürmeyin; uygulamanızın biçimini esas alın.
- `$NAME`, `${NAME}` ve `$(...)` normal metin olarak kabul edilir; genişletilmez, çalıştırılmaz. Bunların bağımlılıkları eksik olsa da metin boş olmadığı için boş bulgusu çıkmayabilir.
- Kontrol, biçim, surrogate, özel kullanım ve atanmamış Unicode karakterleri ile Unicode satır/paragraf ayırıcıları reddedilir; desteklenen tab ve satır sonları istisnadır. Gömülü BOM, tek CR, NUL ve terminal escape hata verir. UTF-16 veya bozuk UTF-8 kabul edilmez.
- `export`, `=` olmadan tek başına ad, çok satırlı değer ve tırnaksız JSON içindeki tırnaklar gibi kapsam dışı biçimler 2 döndürür. Yorumlar ve girdinin ham satırları çıktıya taşınmaz.

Yalnız normal dosyalar okunur; açıkça verilen sembolik bağlantı normal bir dosyaya gidiyorsa izlenir. FIFO ve aygıtlar reddedilir. POSIX üzerinde FIFO yazıcısı beklememek için nonblocking açılır. Okuma sırasında saptanan boyut/mtime değişimi hatadır; iki değişken dosyanın eşzamanlı anlık görüntüsü garanti edilmez. Başka süreç yazıyorsa kararlı kopyalarla çalışın.

## Çıktı ve gizlilik sınırı

Metin ve JSON stdout'a yazılır; normal hata yollarında stderr boştur. JSON alanları `schema_version: 1`, `status`, `exit_code`, `findings` ve `errors` şeklindedir. Anahtarlar sıralı, satırlar dosya sırasındadır. Zaman damgası veya dosya yolu olmadığı için aynı girdinin çıktısı tekrarlanabilir.

Girdi hatasında `findings: null` olur. `errors` yalnız `reference`, `target` veya `arguments` rolünü, sabit hata kodunu ve varsa satır numarasını içerir. İlk hata işlemi durdurur. Exception metni, değer, ham satır ve geçersiz argüman gösterilmez. Çıktı akışı koparsa tam rapor üretilemeyebilir.

**Anahtar adları da özel bilgi taşıyabilir.** Raporu paylaşmadan inceleyin. Araç sır tarayıcısı veya anonimleştirici değildir. Sözdizimi ve boşluk kontrolü için seçilen değerler süreç belleğine okunur; güvenli bellek silme, ele geçirilmiş bilgisayardan veya dış izleme araçlarından koruma sağlamaz. Anahtara yazılmış hassas metin anahtar adı olarak raporda görünebilir.

0 sonucu uygulamanın açılmasını, parolanın doğruluğunu, ağ erişimini, değer türlerini, çalışma zamanı önceliklerini ya da güvenliği garanti etmez. Örnekte hiç tanımlanmayan bir gereksinimi bilemez. `synthetic_token` kimlik bilgisi değildir; üretimde kullanılmaz.

## Alternatifler ve kaynaklar

[dotenv-linter](https://github.com/dotenv-linter/dotenv-linter) kontrol, düzeltme ve dosya farklarını gösterme işlevleri sunar. [dotenv-safe](https://github.com/rolodato/dotenv-safe), dotenv yüklemesinden sonra gereken adları Node.js süreç ortamında kontrol eder. Bunlar yerleşik alternatiflerdir. EnvContract'ın özgünlük veya üstünlük iddiası yoktur; kapsamı iki açık dosya, Python standart kütüphanesi, dar sözdizimi ve değer içermeyen rapordur.

[dotenv ayrıştırma kuralları](https://github.com/motdotla/dotenv#what-rules-does-the-parsing-engine-follow) bu aracın desteklemediği özellikleri de içerir. Kendi uygulamanızın yükleyicisini ayrıca kontrol edin. Testler Python [unittest](https://docs.python.org/3/library/unittest.html) ile çalışır. Kaynak kontrol tarihi: 29 Ekim 2026.

## Lisans

Önerilen yayın için `LICENSE` dosyasında MIT metni bulunur. Depo adı ve lisans son yayın incelemesinin parçasıdır; yerel paket henüz yayımlanmadı.

<p align="center">
  <img src="assets/icon.svg" alt="Habit Guard simgesi" width="96">
</p>

<h1 align="center">Habit Guard</h1>

<p align="center">
  Elinizin ağzınıza, bıyığınıza, kaşınıza ya da saçınıza giderken sizi yakalar ve bırakmanız için dürter.<br>
  Webcam ile çalışır, internet gerektirmez, işlemciyi yormaz. Windows, macOS ve Linux.
</p>

<p align="center">
  <a href="https://github.com/bugraskl/habit-guard/actions/workflows/ci.yml"><img src="https://github.com/bugraskl/habit-guard/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/bugraskl/habit-guard/releases"><img src="https://img.shields.io/github/v/release/bugraskl/habit-guard?include_prereleases" alt="Son sürüm"></a>
  <a href="docs/privacy.md"><img src="https://img.shields.io/badge/ağ%20erişimi-yok%20(CI'da%20doğrulanır)-22D3EE" alt="Ağ erişimi yok, CI'da doğrulanır"></a>
  <a href="docs/privacy.md"><img src="https://img.shields.io/badge/kamera%20görüntüsü-asla%20kaydedilmez-6366F1" alt="Kamera görüntüsü asla kaydedilmez"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/Lisans-MIT-yellow.svg" alt="MIT Lisansı"></a>
</p>

<p align="center">
  <a href="https://bugraskl.github.io/habit-guard/tr/"><b>Web sitesi</b></a> · <a href="README.md">English</a> · <b>Türkçe</b>
</p>

> **Durum: alfa.** Algılama, alarmlar ve arayüz hazır ve otomatik testlerle kapsanıyor; algılama
> örnek fotoğraflarda ve oynatılan videoda denendi. Gerçek webcam'lerle ve gerçek masa başlarında
> henüz çok az vakit geçirdi; bu yüzden şu an en değerli katkı, yanlış alarmları ve kaçırılan
> durumları bildirmeniz ([nasıl bildirilir](CONTRIBUTING.md#reporting-a-problem)).

<p align="center">
  <a href="https://bugraskl.github.io/habit-guard/assets/demo.mp4"><img src="assets/video/demo.webp" alt="On saniyelik bir animasyon: el ağza doğru gider, Habit Guard onu ağız bölgesinde bulur, el kaldıkça bir halka dolar, ardından ekran ses dalgalarıyla kırmızıya döner ve el inince her şey sakinleşir." width="760"></a><br>
  <sub>On saniyede baştan sona. Bu, uygulamanın ekran kaydı değil; yapay zekâ ile hazırlanmış bir animasyon. <a href="https://bugraskl.github.io/habit-guard/assets/demo.mp4">MP4'ü açın</a>.</sub>
</p>

## Neden Habit Guard

Tırnak yemek, bıyık koparmak, kaş ya da kirpik yolmak, cildi kaşımak: bu alışkanlıklar farkında
olmadan, kendiliğinden yapılır. Fark ettiğinizde el çoktan dakikalardır oradadır. Habit Guard
webcam'inizi izler; parmak ucunuz *sizin* alışkanlığınızın yaşandığı yere gidip orada kaldığında
bunu fark eder ve hemen araya girer. Böylece alışkanlığı fark etmeden sürdürmek zorlaşır.

Her şey kendi bilgisayarınızda olur. Kameradan gelen görüntü bellekte işlenir ve hemen atılır;
yalnızca sayaçlar saklanır.

## Neyi izler

<p align="center">
  <img src="assets/zones.svg" alt="Dört alışkanlığın bölgelerinin işaretlendiği bir yüz" width="640">
</p>

| Alışkanlık | Nerede | Geniş alan (isteğe bağlı) |
|---|---|---|
| **Tırnak ve parmak yeme** | dudaklar ve çevresi | |
| **Bıyık, sakal ve dudak koparma** | burun ile ağız arası | çene ve sakal çizgisi |
| **Kaş, kirpik ve saç yolma** | kaşlar, göz kapakları, alın ve saç çizgisi | saçlı deri |
| **Yüze dokunma ve cilt kaşıma** | yüzün geri kalanı | |

Her alışkanlığın kendi **bekleme süresi** (alarmın çalması için elin bölgede ne kadar kalması
gerektiği; kısa bir kaşınma ya da bir yudum su alarm çaldırmaz) ve kendi **bölge boyutu** vardır.
Bölgeler göz aranızdaki mesafeye göre ölçülür; öne eğilseniz, geri yaslansanız ya da başınızı
yana yatırsanız da sizi takip eder.

## Sizi yakaladığında ne olur

**Ayarlar → Uyarılar** sekmesinde istediğiniz uyarıları seçin, isterseniz hepsini birlikte kullanın:

| | Uyarı | Ne yapar |
|---|---|---|
| 🔔 | **Ses** | Önce yumuşak bir zil sesi, sonra üç bip, siz devam ettikçe titreşimli bir alarm. Ses düzeyi ayarlanabilir; yerleşik sesin yerine kendi ses dosyanızı (WAV, MP3 ve benzerleri) kullanabilirsiniz. |
| 🌑 | **Ekran perdesi** | El inene kadar tüm monitörlerde ekran kararır ya da kırmızı bir çerçeve yanıp söner. Tıklamalar perdenin arkasına geçer; yani ekran sizi asla kilitleyemez. |
| 🗣️ | **Sesli uyarı** | Seçtiğiniz bir cümleyi ("Elini indir."), sisteminizin internet gerektirmeyen sesiyle okur. |
| 💬 | **Bildirim** | Her olayın ilk alarmında bir masaüstü bildirimi gösterir. |
| 📈 | **İstatistik** | Günlere ve alışkanlıklara göre sayaçlar, 7 günlük grafik ve **temiz süre serisi**: son alarmdan bu yana ne kadar süredir izlendiğiniz. Yalnızca bilgisayarınızda saklanır. |

**Kademeli güçlenme** açıkken (varsayılan) el orada kaldıkça alarm birkaç saniyede bir artar: ses
yükselir, ekran daha da kararır. Yemek yerken ya da bir görüşme sırasında izlemeyi sistem
tepsisinden 15 dakika, bir saat ya da üç saatliğine duraklatabilirsiniz.

## Ekran görüntüleri

Bunlar uygulamanın gerçek pencereleri (İngilizce ve Türkçe). Önizlemedeki kamera görüntüsü fotoğraf değil, çizimdir; bu depoda gerçek bir yüz yok.

<p align="center">
  <img src="assets/screenshots/tr/preview.png" width="560" alt="Kamera önizleme: eli ağzında olan çizim bir kişi, yüzün üzerindeki bölgeler ve elin 21 noktası">
  <img src="assets/screenshots/tr/stats.png" width="310" alt="İstatistikler: bugünkü ve toplam alarm sayısı, temiz süre serisi ve 7 günlük grafik">
</p>

<p align="center">**Kamera önizleme**, bölgeleri yüzünüzün üzerinde ve elinizin 21 noktasını gösterir; **İstatistikler** 7 günlük grafiği ve temiz süre serinizi tutar.</p>

<p align="center">
  <img src="assets/screenshots/tr/settings-habits.png" width="300" alt="Ayarlar, Alışkanlıklar sekmesi">
  <img src="assets/screenshots/tr/settings-alarms.png" width="300" alt="Ayarlar, Uyarılar sekmesi">
  <img src="assets/screenshots/tr/settings-general.png" width="300" alt="Ayarlar, Genel sekmesi">
</p>

<p align="center">**Ayarlar**: her biri kendi bekleme süresi ve bölge boyutuyla alışkanlıklar, uyarılar ve genel seçenekler.</p>

<p align="center">
  <img src="assets/screenshots/tr/alarm-dim.png" width="440" alt="Ekran kararır ve “Elini indir!” mesajı görünür">
  <img src="assets/screenshots/tr/alarm-flash.png" width="440" alt="Ekranın kenarlarında yanıp sönen kırmızı çerçeve">
</p>

<p align="center">**Alarm**: el inene kadar ekran kararır (solda) ya da kırmızı bir çerçeve yanıp söner (sağda). Tıklamalar perdenin arkasına geçer.</p>

<p align="center">
  <img src="assets/screenshots/tr/tray.png" width="200" alt="Sistem tepsisi menüsü">
</p>

<p align="center">**Sistem tepsisi menüsü**: duraklatma, belirli süre duraklatma, önizleme, istatistikler, ayarlar.</p>

Daha fazla görüntüyü ve üzerinde tıklayabileceğiniz bir demoyu [web sitesinde](https://bugraskl.github.io/habit-guard/tr/) bulabilirsiniz.

## Nasıl çalışır

```mermaid
flowchart LR
    A[Webcam görüntüsü] --> B{Yüz çevresinde<br/>hareket var mı?}
    B -- hayır --> Z[Atla: bakılacak bir şey yok]
    B -- evet --> C[Yüz: gözler, burun,<br/>ağız köşeleri]
    C --> D[Eller: avuç bulucu,<br/>sonra her el için 21 nokta]
    D --> E{Bir parmak ucu bölgede<br/>bekleme süresinden uzun kaldı mı?}
    E -- evet --> F[Alarm: ses, perde,<br/>sesli uyarı, bildirim]
```

- **Görüntü işleme.** Yüzü YuNet, elleri MediaPipe'ın avuç ve el-nokta modelleri bulur (modeller
  OpenCV'nin DNN modülüyle çalıştırılır). MediaPipe'ın *çalışma ortamı* kullanılmaz, çünkü içinde
  bir telemetri bileşeni var ([neden](docs/privacy.md#why-not-the-mediapipe-runtime)).
- **Baştan hafif tasarlandı.** Eller uzaktayken görüntüye saniyede yaklaşık iki kez bakılır ve
  yalnızca yüzün çevresinde bir şey kıpırdadıysa analiz edilir. El yaklaşınca analiz hızlanır.
- **Karar.** Bir bölgedeki parmak ucu bir "seri" başlatır; kısa kopmalar seriyi bitirmez. Alarm,
  bekleme süresi dolunca çalar ve el orada kaldıkça güçlenir ([mimari](docs/architecture.md)).

## Gizlilik

| Söz | Nasıl doğrulanır |
|---|---|
| Ağ erişimi yok: telemetri, hesap ve güncelleme kontrolü yok. | `scripts/check_privacy.py`, `src/` altındaki herhangi bir dosya bir ağ kütüphanesini içe aktarırsa CI'ı başarısız yapar. |
| Kamera görüntüleri bellekte işlenir ve asla kaydedilmez. | Aynı tarama, OpenCV'nin görüntü ya da video yazma işlevleri veya Qt'nin görüntü kaydetme çağrıları kullanılırsa CI'ı başarısız yapar. |
| Yalnızca sayılar saklanır: günlük sayaçlar ve ayarlarınız, düz JSON dosyaları olarak. | Yapılandırma klasörünüzdeki `settings.json` ve `stats.json`. |
| Duraklatmak kamerayı serbest bırakır. | Webcam ışığı söner. |

Ayrıntılar: [gizlilik](docs/privacy.md).

## Performans

Windows 11, AMD Ryzen 7 3700X (8 çekirdek, 16 iş parçacığı) üzerinde `habit-guard bench` ile ölçüldü;
ölçümün tekrarlanabilir olması için 640×480'lik bir video klip oynatıldı. İşlemci kullanımı sürecin
tamamını kapsar.

| Durum | Dengeli profil |
|---|---|
| Yüz görünürken, eller uzaktayken (günün çoğu) | makinenin **%0,34**'ü (bir çekirdeğin %5,5'i) |
| Aynısı, **Eko** profili | makinenin %0,24'ü |
| El yüze yakınken (saniyede 8 kereye kadar analiz) | makinenin yaklaşık %1,3'ü (bir çekirdeğin %20'si) |
| Tek bir analiz (yüz + el) | 20 – 26 ms |

Bu sayılar oynatılan klibe aittir; canlı kamera kendi sürücü yükünü de ekler. Kendi makinenizde
ölçmek için `habit-guard bench` komutunu çalıştırın. Profili **Ayarlar → Genel → Performans**
altından seçebilirsiniz.

## İndirme

| Platform | Paket | |
|---|---|---|
| **Windows** 10/11 x64 | Kurulum dosyası `.exe` ya da taşınabilir `.zip` | [İndir](https://github.com/bugraskl/habit-guard/releases/latest) |
| **macOS** 14+ Apple silicon | `.dmg` | [İndir](https://github.com/bugraskl/habit-guard/releases/latest) |
| **Linux** x86_64 | `.AppImage` ya da `.tar.gz` | [İndir](https://github.com/bugraskl/habit-guard/releases/latest) |

Her sürümle birlikte `SHA256SUMS.txt` ve GitHub'ın derleme kaynağı (provenance) doğrulamaları da
yayınlanır. Paketler henüz kod imzalı değil: Windows'ta SmartScreen uyarı verebilir (*Ek bilgi*,
ardından *Yine de çalıştır*); macOS'ta ilk açılışta uygulamaya sağ tıklayıp *Aç*'ı seçin, sonra
kamera iznini verin. Windows kurulum dosyası yalnızca bulunduğunuz kullanıcı için kurar (yönetici
yetkisi gerekmez) ve isterseniz `habit-guard` komutunu PATH'inize ekler. Paketleri kendiniz
derlemek için: [derleme](docs/building.md).

## Kaynaktan çalıştırma

[uv](https://docs.astral.sh/uv/) gerekir (uv, doğru Python sürümünü kendisi indirir). Intel
işlemcili Mac'lerde Habit Guard'ı çalıştırmanın yolu da budur.

```bash
git clone https://github.com/bugraskl/habit-guard.git
cd habit-guard
uv sync
uv run habit-guard
```

Sistem tepsisinde (macOS'ta menü çubuğunda) bir el simgesi belirir. İlk açılışta ayarlar penceresi
açılır: izlemek istediğiniz alışkanlıkları seçin. Bölgeleri kendi yüzünüzün üzerinde görmek ve
kameranın sizi düzgün görüp görmediğini anlamak için tepsi menüsünden **Kamera önizleme**'yi açın.

Linux'ta dağıtımınızın `libxcb-cursor0` (Debian/Ubuntu) ya da `xcb-util-cursor` (Fedora, Arch)
paketi ve sistem tepsisi olan bir masaüstü gerekir (GNOME'da tepsi simgeleri için ayrıca bir eklenti
kurmalısınız).

Bilgisayar açıldığında otomatik başlatmak için `habit-guard autostart enable` komutunu çalıştırın
ya da Windows kurulumundaki ilgili kutuyu işaretleyin.

## Komut satırı

Örneklerde `habit-guard` yazıyor. Kaynak koddan çalıştırıyorsanız bunun karşılığı
`uv run habit-guard`; Windows kurulumunda ise (PATH seçeneğini işaretlediyseniz) yeni bir
terminalde `habit-guard` ya da kurulum klasöründeki `habit-guard-cli.exe`.

```bash
habit-guard                       # tepsi uygulamasını başlat
habit-guard doctor                # hata bildirimleri için tanı raporu (içinde görüntü yok)
habit-guard doctor --probe-cameras
habit-guard selftest              # modelleri, görüntü kodunu, sesleri ve pencereleri kontrol et
habit-guard bench                 # işlemci kullanımını ve analiz süresini ölç
habit-guard stats                 # sayaçlarınızı göster
habit-guard autostart enable      # oturum açılınca başlat (enable | disable | status)
habit-guard reset                 # ayarları ve istatistikleri sil
habit-guard ctl pause             # çalışan uygulamayı yönet: status, pause, resume, toggle,
                                  # test, settings, wizard, preview, stats, quit
habit-guard --camera 1            # başka bir kamera; ya da --camera klip.mp4 ile bir video oynat
habit-guard --config-dir KLASÖR   # ayarları ve istatistikleri seçtiğiniz klasörde tut
```

`habit-guard ctl` ile uygulamanın eylemlerini kendi klavye kısayollarınıza bağlayabilirsiniz.
Windows'ta `habit-guard-cli.exe ctl toggle` için bir kısayol oluşturup özelliklerinden bir kısayol
tuşu atayın; macOS'ta Kısayollar ya da Automator ("Kabuk Komutu Çalıştır"), Linux'ta masaüstünüzün
özel kısayol ayarları işinizi görür. `ctl`, çalışan uygulamayla ağ üzerinden değil, ayarlar
klasöründeki küçük dosyalar aracılığıyla konuşur. Uygulama çalışmıyorsa komut 3 koduyla çıkar.

## Bilmeniz gerekenler

- **Bir kamera, tek program.** Çoğu webcam aynı anda yalnızca tek bir program tarafından
  kullanılabilir. Kamerayı başka bir uygulama (görüntülü görüşme programı, başka bir izleyici)
  kullanıyorsa Habit Guard birkaç saniyede bir yeniden dener; tepsi menüsü de bunu belirtir.
  **Ayarlar → Genel → Kamera arayüzü** bazen iki programın aynı kamerayı paylaşmasını sağlar.
- **Işık ve açı.** Kamerayı, yüzünüz ve elinizi kaldırdığınızda iki eliniz görüntüye girecek,
  yüzünüze de ışık gelecek şekilde yerleştirin. Önizleme penceresi, uygulamanın tam olarak ne
  gördüğünü gösterir.
- **Tıbbi cihaz değildir.** Habit Guard bir kendi kendine yardım aracıdır. Bir alışkanlık size
  zarar veriyor ya da sizi çok rahatsız ediyorsa bir doktorla ya da terapistle konuşmanızda fayda
  var; pek çok kişi bu tür hatırlatıcıları tedavinin yerine değil, ona yardımcı bir ek olarak
  kullanıyor.

## Platform desteği

| | Windows | macOS | Linux X11 | Linux Wayland |
|---|:---:|:---:|:---:|:---:|
| Algılama ve alarmlar | ✅ | ⚠️ | ⚠️ | ⚠️ |
| Ekran perdesi | ✅ | ⚠️ | ⚠️ | ❌¹ |
| Sesli uyarı | ✅ | ✅ (`say`) | ⚠️ (`spd-say` ya da `espeak`) | ⚠️ |

✅ Windows 11'de gerçek bir kamerayla geliştirildi ve kullanıldı. ⚠️ bu sistem için yazıldı: CI,
paketleri üç sistemde derliyor ve paketlerden `habit-guard selftest` çalıştırıyor (modeller,
görüntü kodu, sesler ve pencereler); ama yazar gerçek bir kamerayla henüz denemedi. Denemeleriniz
ve geri bildirimleriniz çok değerli.
¹ Bazı Wayland masaüstleri tıklamaların içinden geçmesine izin veren pencereleri yok sayar; bu
durumda perde tıklamaları engelleyebilir. Böyle olursa ekran perdesini uyarı ayarlarından kapatın.

## Belgeler

[Bölgeler ve ayar](docs/zones.md) · [Yapılandırma](docs/configuration.md) ·
[Derleme](docs/building.md) · [Mimari](docs/architecture.md) · [Gizlilik](docs/privacy.md) ·
[Sorun giderme](docs/troubleshooting.md) · [Katkıda bulunma](CONTRIBUTING.md) ·
[Değişiklik günlüğü](CHANGELOG.md)

## Teşekkürler

Habit Guard şunların üzerine kurulu: [OpenCV](https://opencv.org/)'nin DNN modülü, Google'ın
[MediaPipe](https://ai.google.dev/edge/mediapipe) el modellerinin
[OpenCV Zoo](https://github.com/opencv/opencv_zoo) tarafından hazırlanmış ONNX dönüşümleri
(Apache-2.0), YuNet yüz algılayıcısı (MIT) ve [Qt for Python](https://doc.qt.io/qtforpython-6/).
Lisanslar ve kaynaklar: [`NOTICE.md`](src/habit_guard/vision/models/NOTICE.md).
[Eye Tracker](https://github.com/bugraskl/eye-tracker) ile aynı yaklaşımla yapıldı.

## Lisans

[MIT](LICENSE)

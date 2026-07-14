# Pisicevir

Pisicevir, Debian ikili paketlerini (`.deb`) incelenmiş PISI paket tariflerine dönüştürmeye yardımcı olur. **Evrensel bir paket dönüştürücü değildir**; mevcut uygulama Debian'dan PISI'ye dönüştürme iş akışına odaklanır.

Araç bir `.deb` dosyasını inceler, bir dönüştürme planı oluşturur ve onaylanan plandan bir PISI tarif dizini üretir. Debian paketini kurmaz, bakım betiklerini çalıştırmaz veya insan incelemesi olmadan yayıma hazır bir PISI paketi üretmez.

Bu ad, aynı adı taşıyan [önceki aracın](https://github.com/pars-linux/pisicevir) mirasını sürdürmek amacıyla seçilmiştir.

Depo, erken aşamadaki bir uygulamadır. Oluşturulan dönüştürme planları açık inceleme ve onay gerektirir. Oluşturulan PISI tarifleri de kullanılmadan önce gerçek bir PISI derleme ve kurulum testinden geçirilmelidir.

> PISI paketleme hakkında daha fazla bilgi için [PISI Linux Developer](https://developer.pisilinux.org/) sayfasına bakınız.

![Pisicevir CLI](/assets/cli.png)

![Pisicevir GUI](/assets/gui.png)

## Ne yapar?

Pisicevir, inceleme öncelikli bir Debian'dan PISI'ye tarif oluşturma iş akışı sunar:

1. Debian ikili paketini inceler;
2. paket üst verilerini ve içeriğini sınıflandırır;
3. düzenlenebilir bir dönüştürme planı oluşturur;
4. onaylanmış plandan bir PISI tarifi üretir;
5. oluşturulan tarifi lint ve doğrulama denetimlerinden geçirir.

Oluşturulan tarif, PISI paketleme için bir başlangıç noktasıdır; paketleyici incelemesinin yerine geçmez.

## Güvenlik modeli

Pisicevir, her Debian paketini güvenilmeyen girdi olarak değerlendirir. Debian arşivleri, konak dosya sistemine çıkarılmadan okunur. Adaptör dış arşivi doğrular, güvenli olmayan yolları ve arşiv dışına çıkan bağlantıları reddeder, paket içeriğinin sahiplik ve erişim kiplerini kaydeder, normal dosyaların özetlerini hesaplar ve bakım betiklerini elle yaşam döngüsü incelemesi yapılabilmesi için görünür hâle getirir.

Plan aşağıdakileri içermediği sürece tarif oluşturma işlemi engellenir:

- `approved: true`;
- kaynağın tam SHA-256 özeti;
- incelenmiş lisans bilgileri;
- paketleyici kimliği;
- bir ana sayfa;
- açıkça tanımlanmış kurulum işlemleri.

## Komutlar

Bir Debian paketi dönüşümünü inceleyin ve planlayın:

```bash
pisicevir --help
pisicevir inspect package.deb --format json
pisicevir classify package.deb
pisicevir plan package.deb --output plan.yaml
```

`plan.yaml` dosyasını elle güncelleyin. Zorunlu alanlar için [Güvenlik modeli](#güvenlik-modeli) bölümüne bakın.

PISI tarifini oluşturun ve denetleyin:

```bash
pisicevir generate package.deb --plan plan.yaml --output recipe/
pisicevir lint recipe/ --strict
pisicevir validate recipe/ --format json
```

Bir APT paketinin `apt-get` çağrılmadan önce systemd içermeyen bir hedefe kurulup kurulamayacağını denetleyin:

```bash
pisicevir install package-name --dry-run
```

Kurulum ilke denetimi, paketin `Depends` ve `Pre-Depends` kapanışını `apt-cache depends --no-recommends --no-suggests` ile çözer. İstenen paket ya da zorunlu bağımlılıklarından herhangi birinin adı `*systemd*` kalıbıyla eşleşirse (örneğin `systemd`, `libsystemd0` veya `libpam-systemd`), Pisicevir kurulumu engeller ve bakımcıların systemd içermeyen bir Debian yeniden derlemesi ya da başka bir paket seçebilmesi için bağımlılık yolunu yazdırır. `--dry-run` kullanılmadığında da aynı denetim önce çalışır ve `apt-get install package-name` yalnızca ilke geçerse çağrılır.

Oluşturulan plan kasıtlı olarak onaylanmamış durumdadır. `approved: true` ayarını yapmadan önce planı inceleyin ve düzenleyin. `pisicevir plan` bir Debian sisteminde çalıştırıldığında, `dpkg-query` verilerine göre önceden kurulmuş olan ve anlamı belirsiz olmayan bağımlılıklar, mimari niteleyicileri olmadan Debian paket adı kullanılarak `dependencies.map` içine önceden yazılır (örneğin `python3:any`, `python3` olarak eşlenir). Özellikle hedef PISI dağıtımında farklı paket adları kullanılıyorsa, oluşturma işleminden önce bu eşlemeleri inceleyin.

## Geliştirme

Bir sanal ortam oluşturun ve kilitlenmiş CI bağımlılıklarını kurun:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements/ci.lock
python -m pip install --no-deps --no-build-isolation -e .
python -m pytest -ra
```

İsteğe bağlı grafik çalışma ortamı, kilitlenmiş test ortamına dahildir ve aşağıdaki komutla başlatılabilir:

```bash
pisicevir-gui
```

## Debian sürümleri

Debian paketleme dosyaları depoda saklanmaz. Elle çalıştırılan GitHub release iş akışı, bu dosyaları Python kaynak sürümünden ve önceki SemVer etiketinden bu yana yapılan commit'lerden oluşturur.

Bir etiket uzak depoya gönderilmeden önceki iş akışı:

1. kaynak sürümünün erişilebilen en son etiketten daha yeni olduğunu doğrular;
2. sürüm notlarını ve Debian değişiklik günlüğünü oluşturur;
3. kilitlenmiş Python testlerini çalıştırır;
4. birbirinden yalıtılmış iki kaynak anlık görüntüsü oluşturur;
5. her iki anlık görüntüde Debian paketleme dosyalarını oluşturur;
6. her iki paket kümesini derler;
7. `.deb` dosyalarının bayt düzeyinde aynı olmasını zorunlu kılar;
8. Lintian ve paket içeriği sızıntısı denetimlerini çalıştırır;
9. her iki paketi kurar ve temel işlev testlerini gerçekleştirir;
10. sürüm kanıtlarını yükler, etiketi oluşturur ve GitHub Release'i yayımlar.

Yerel paketleme talimatları için [DEBIAN-BUILD.md](DEBIAN-BUILD.md) dosyasına bakın.

## Sürümleme

Yetkili yazılım sürümü aşağıdaki değerdir:

```python
src/pisicevir/__init__.py::__version__
```

Git etiketleri, Debian sürümleri, eser adları, sürüm notları ve Debian değişiklik günlüğü bu değerden türetilir.

## Lisans

Pisicevir, GPL-3.0-or-later kapsamında lisanslanmıştır. Ayrıntılar için [LICENSE](LICENSE) dosyasına bakın.

## Ticari Marka ve Logo Atfı

**pisicevir**, topluluk tarafından geliştirilen bağımsız bir yardımcı araçtır.

- **Ticari Markalar:** **PISI**, **PISI Linux Topluluğu** adına tescilli bir ticari markadır. Bu proje, **PISI** projesi veya topluluğu ile bağlantılı değildir; onlar tarafından onaylanmamakta veya desteklenmemektedir.
- **Logo:** Bu depoda kullanılan **PISI** logosu, **PISI Linux Topluluğu** mülkiyetindedir. Logo burada yalnızca yazılımlarıyla uyumluluğu belirtmek amacıyla, bilgilendirme ve atıf kapsamında kullanılmaktadır.

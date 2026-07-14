# Pisicevir

Pisicevir, politika odaklı bir harici paket içe aktarıcısı ve PISI'ye özgü tarif oluşturucusudur. İlk kaynak bağdaştırıcısı, Debian ikili paketlerini kurmadan veya bakımcı betiklerini çalıştırmadan inceler.

Depo, erken aşamadaki bir uygulamadır. Oluşturulan dönüştürme planları açık inceleme ve onay gerektirir. Oluşturulan PISI tarifleri de kullanılmadan önce gerçek bir PISI derleme ve kurulum testinden geçirilmelidir.

> Daha fazla bilgi için [PISI Linux  Developer](https://developer.pisilinux.org/) sayfasına başvurunuz.

## Güvenlik modeli

Pisicevir, her harici paketi güvenilmeyen girdi olarak değerlendirir. Debian arşivleri, ana sistemin dosya sistemine çıkarılmadan okunur. Bağdaştırıcı dış arşivi doğrular, güvenli olmayan yolları ve arşiv dışına çıkan bağlantıları reddeder, paket içeriğinin sahiplik ve erişim kiplerini kaydeder, normal dosyaların özetlerini hesaplar ve bakımcı betiklerini elle yaşam döngüsü incelemesi yapılabilmesi için görünür hâle getirir.

Plan aşağıdakileri içermediği sürece tarif oluşturma işlemi engellenir:

- `approved: true`;
- kaynağın tam SHA-256 özeti;
- incelenmiş lisans bilgileri;
- paketleyici kimliği;
- bir ana sayfa;
- açıkça tanımlanmış kurulum işlemleri.

## Komutlar

```bash
pisicevir --help
pisicevir inspect package.deb --format json
pisicevir classify package.deb
pisicevir plan package.deb --output plan.yaml
```

`plan.yaml` dosyasını elle güncelleyin. Zorunlu değişiklikler için [Güvenlik modeli](#güvenlik-modeli) bölümüne bakın.

```bash
pisicevir generate package.deb --plan plan.yaml --output recipe/
pisicevir lint recipe/ --strict
pisicevir validate recipe/ --format json
```

Oluşturulan plan kasıtlı olarak onaylanmamış durumdadır. `approved: true` ayarını yapmadan önce planı inceleyin ve düzenleyin.
`pisicevir plan` bir Debian sisteminde çalıştırıldığında, `dpkg-query` verilerine göre
önceden kurulmuş olan ve anlamı belirsiz olmayan bağımlılıklar, mimari niteleyicileri
olmadan Debian paket adı kullanılarak `dependencies.map` içine önceden yazılır
(örneğin `python3:any`, `python3` olarak eşlenir). Özellikle hedef PISI dağıtımında
farklı paket adları kullanılıyorsa, oluşturma işleminden önce bu eşlemeleri inceleyin.

## Geliştirme

Bir sanal ortam oluşturun ve kilitlenmiş CI bağımlılık kümesini kurun:

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

Debian paketleme dosyaları depoda saklanmaz. Elle çalıştırılan GitHub sürüm iş akışı, bu dosyaları Python kaynak sürümünden ve önceki SemVer etiketinden bu yana yapılan commit'lerden oluşturur.

Bir etiket uzak depoya gönderilmeden önce iş akışı:

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

# Debian paketlerini yerel olarak oluşturma

Pisicevir, statik bir `debian/` dizini tutmaz. Sürüm, değişiklik günlüğü, ana sayfa, bakımcı kimliği, paket ayrımı ve temel işlev testlerinin birbirinden bağımsız biçimde sapmaması için paketleme meta verileri sürüm girdilerinden oluşturulur.

## Ön koşullar

Ubuntu veya Debian uyumlu bir derleme sunucusunda aşağıdaki paketleri kurun:

```bash
sudo apt update
sudo apt install -y \
  binutils build-essential debhelper devscripts dh-python dpkg-dev fakeroot \
  libegl1 libgl1 libxkbcommon-x11-0 lintian pybuild-plugin-pyproject \
  python3-all python3-build python3-pydantic python3-pyqt5 python3-pytest \
  python3-pytestqt python3-setuptools python3-wheel python3-yaml \
  python3-zstandard
```

Kilitlenmiş Python test ortamını ayrıca kurun:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements/ci.lock
python -m pip install --no-deps --no-build-isolation -e .
python -m pytest -ra
```

## Sürüm meta verilerini oluşturma

Yazılım sürümü `src/pisicevir/__init__.py` dosyasından alınır. Normal sürüm iş akışı, meta verileri Git etiketlerinden oluşturur. Yerel bir test derlemesi için geçici bir değişiklik günlüğünü açıkça oluşturun:

```bash
mkdir -p dist
cat > dist/debian-changelog <<'EOF'
pisicevir (0.1.0-1) noble; urgency=medium

  * Local test build.

 -- Zafer Balkan <zafer@zaferbalkan.com>  Thu, 01 Jan 1970 00:00:00 +0000
EOF
```

Paketleme dizinini oluşturun:

```bash
python tools/generate_debian_packaging.py \
  --changelog dist/debian-changelog \
  --maintainer-name "Zafer Balkan" \
  --maintainer-email "zafer@zaferbalkan.com" \
  --homepage "https://github.com/zbalkan/pisicevir"
```

Oluşturulan `debian/` dizini Git tarafından yok sayılır.

## Derleme

Oluşturulan Debian kuralları dosyası, `pybuild` aracının dağıtımın Python yorumlayıcısını ve modüllerini kullanması için `PATH` değişkenini sistem dizinlerine sıfırlar. Bu işlem, paket derlemeleri sırasında eksik hazırlanmış bir sanal ortamın (örneğin `.venv/bin/python3.12`) yanlışlıkla kullanılmasını önler.

Kararlı bir derleme zaman damgası ayarlayın ve ikili paketleri oluşturun:

```bash
export SOURCE_DATE_EPOCH="$(git show -s --format=%ct HEAD)"
export TZ=UTC
export LC_ALL=C.UTF-8
export PYTHONHASHSEED=0
export DEB_BUILD_OPTIONS='noautodbgsym reproducible=+fixfilepath'
export DEB_BUILD_MAINT_OPTIONS='hardening=+all reproducible=+fixfilepath'

dpkg-buildpackage --build=binary --unsigned-source --unsigned-changes
```

Paketler üst dizine yazılır.

## Doğrulama

```bash
lintian --fail-on error ../pisicevir_*.changes
python tools/verify_debian_artifacts.py ../pisicevir_*.deb ../pisicevir-gui_*.deb
sudo apt install -y ../pisicevir_*.deb ../pisicevir-gui_*.deb
/usr/bin/pisicevir --version
QT_QPA_PLATFORM=offscreen /usr/bin/python3 -c \
  'from pisicevir.gui import PisicevirGUI; print(PisicevirGUI)'
sudo apt purge -y pisicevir-gui pisicevir
```

## Yeniden üretilebilirlik denetimi

Tek bir başarılı derleme, bir sürümün kabul edilmesi için yeterli değildir. Aynı commit'i, aynı `SOURCE_DATE_EPOCH` değeriyle yalıtılmış iki dizinde derleyin ve ardından paket dosyalarını doğrudan karşılaştırın:

```bash
cmp first/pisicevir_0.1.0-1_all.deb second/pisicevir_0.1.0-1_all.deb
cmp first/pisicevir-gui_0.1.0-1_all.deb second/pisicevir-gui_0.1.0-1_all.deb
```

Elle çalıştırılan GitHub sürüm iş akışı, sürüm etiketini oluşturmadan veya uzak depoya göndermeden önce bu denetimi otomatik olarak gerçekleştirir.

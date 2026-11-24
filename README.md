# Localzet OS

Российский desktop-дистрибутив с собственным интерфейсом Aurora на базе
Ubuntu 26.04 LTS, GNOME 50 и Wayland. Русский язык — первый класс;
базовые возможности не требуют облачной учётной записи.

**Статус: проверенный Live Desktop и экспериментальная установка в QEMU.
Стабильного релиза для физического SSD пока нет.**

## Реализовано и проверено

- Aurora Shell: поиск приложений, панель, постоянный dock, оригинальные обои.
- Localzet Settings: нативное GTK4/libadwaita приложение.
- Localzet Connect: точки входа для NectarLink и проверка закреплённого DEB
  (сопряжение с Android и включение клиента в образ ещё не проверены).
- Windows Runtime: запуск доверенных EXE/MSI через отдельные Wine-профили;
  64-битная тестовая программа Wine успешно выполнена в CI.
- Сборка системного DEB, Ubuntu rootfs, Casper Live ISO, GRUB BIOS/UEFI.
- Проверенные загрузки Live GNOME Wayland в обоих режимах.
- Установка на виртуальный SSD в UEFI, неизменность второго диска и загрузка
  установленной системы без ISO; пока отдельный VM-only тестовый образ.

## Текущий визуальный инкремент

В коде добавлены масштабируемая тема значков Localzet с fallback Adwaita/hicolor
и страница Appearance с Blue/Purple/Black и восстановлением сохранённых
пользовательских параметров. `make test` проходит (109 тестов и 8 манифестов),
DEB и shell bundle собираются. После фикса GTK-процесс проходит в GNOME 50.1
DevKit/Xvfb на 1536×1024 и 1920×1080 без JavaScript-ошибок. CI artifact
показывает только ограниченный Shell/overview smoke, а не полноценную сессию.
Скриншоты Nautilus, Appearance, Quick Settings, launcher и сравнение с PNG
остаются NOT TESTED.

Интерфейсный этап в текущей ветке ещё не прошёл runtime-приёмку GNOME 50.
См. [дизайн-приёмку](docs/DESIGN_ACCEPTANCE.ru.md); browser/preview-изображения
не считаются скриншотами GNOME.

## Разработка

```bash
make test
make desktop-deb
make extension-zip
PYTHONPATH=src python3 -m localzet.cli list
```

Сборка ISO выполняется только в отдельной VM; инструкции:
[ISO build and smoke tests](docs/ISO-SMOKE.md).
[UEFI installation test](docs/UEFI-INSTALL-TEST.md) описывает проверенный
виртуальный путь. Тестовый автоматический установщик не предназначен для
физических дисков.

## Границы проекта

Wine-профили не являются песочницей, а поддержка всех Windows-приложений и игр
не гарантируется. Proton, игровой профиль, телефонное сопряжение, обновления,
восстановление, широкая аппаратная совместимость и Secure Boot ещё требуют
проверки. Российское происхождение продукта не означает полностью отечественную
кодовую базу, официальную регистрацию или сертификацию.

[Архитектура](docs/ARCHITECTURE.md) · [Продукт](docs/PRODUCT.md) ·
[Roadmap](docs/ROADMAP.md) · [Безопасность](docs/SECURITY.md) ·
[Миграция](docs/MIGRATION.md)

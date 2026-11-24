# Приёмка Aurora: нативный интерфейс

## Цель и контракт

Целевые темы — Aurora Blue по умолчанию, Aurora Purple и Aurora Black. Их
цветовые значения зафиксированы в `assets/design-tokens.json` по утверждённой
дизайн-системе. Селектор находится только в **Settings → Appearance**. В
верхней панели его нет.

Три оригинальных owner-approved PNG Blue/Purple/Black просмотрены из закрытого
архива; в публичный репозиторий они не копировались. Это концепт-board, а не
скриншоты работающей GNOME. Локальные WebP-варианты хэнд-оффа также просмотрены.
В реализацию перенесены только first-party SVG и горные WebP-обои. Ни один
значок не имитирует сторонний бренд.

## Текущие изменения

- Тема значков `Localzet` объявляет восемь scalable-контекстов freedesktop,
  диапазон 16–256 px и fallback `Adwaita,hicolor`.
- Desktop entries Localzet Settings/Connect/Windows Runtime используют
  собственные `Icon=` и AppStream metadata.
- Localzet Appearance применяет обои, тёмную цветовую схему, тему значков и
  акцент Localzet Shell. До первого применения сохраняется исходный снимок в
  пользовательском state-каталоге; восстановление не удаляет снимок при ошибке.
- Dock использует сохранённый список desktop IDs, пропускает отсутствующие
  приложения и показывает индикатор запущенного приложения. Текущий размер
  Dock — 70 logical px; app glyphs — 38 px.
- Top bar оставлен без selector; размер status glyphs CSS установлен в 18 px.
- В Shell используется прозрачная заливка, тонкая граница и тень. St CSS не
  поддерживает browser `backdrop-filter`; реальное размытие не заявляется.

## Доказательства и открытые gates

| Gate | Статус | Что требуется |
| --- | --- | --- |
| Baseline до изменений | PASS | `make test`: 84 исходных теста и 8 валидных манифестов |
| Изменённая ветка | PASS | `make test`: 109 тестов и 8 валидных манифестов |
| Approved PNG источники | PASS (visual review) | Все три оригинальных PNG Blue/Purple/Black просмотрены из закрытого архива; это концепт-board, не GNOME captures |
| SVG, index и размеры 16/20/24/32/48/64/128/256 px | PASS | `make test`: все 120 масштабируемых SVG растеризуются через GdkPixbuf во всех восьми размерах |
| Первая оптическая проверка иконок | PARTIAL PASS | Contact sheet всех 120 glyph осмотрен; 18 app/status SVG просмотрены при 16/24/32/48 px на Blue/Purple/Black фонах; side-by-side с реальной GNOME UI остаётся открытым |
| DEB, icon cache и GSettings schema | PASS | `make desktop-deb`; package распакован во временный каталог, icon cache/schema скомпилированы там же |
| Shell extension bundle | PASS | `make extension-zip`; архив проверен вместе с `dock.js` и schema |
| Desktop и AppStream metadata | PASS | `desktop-file-validate`; `appstreamcli validate --strict --no-net` |
| Appearance apply/rollback/restore | PASS (unit) | Apply, rollback, восстановление и ошибки файлового снимка покрыты тестами; GTK/GNOME runtime не подтверждён |
| GTK Settings screenshot | PARTIAL PASS | CI снял окно приложения 1280×800 под Xvfb; это стартовая страница, не Appearance |
| GTK Settings host launch | PARTIAL PASS | Приложение оставалось запущенным в GNOME Wayland 50.1; GNOME Shell отклонил D-Bus screenshot вызов, поэтому визуальный снимок не получен |
| User Themes отсутствует | NOT TESTED (runtime) | Реализация не вызывает User Themes; отказ/отсутствие Shell extension покрыт unit-тестами |
| Dock: focus/Tab, запущенные окна, размеры | NOT TESTED | Пройти реальные мышь/клавиатуру и масштабы 100/125/150/200% |
| Nautilus, Quick Settings, launcher, notifications, lock screen | NOT TESTED | Снять и проверить реальные GNOME 50 экраны |
| Сравнение реальных GNOME экранов с PNG | NOT TESTED | Сделать side-by-side пары с явными подписями источника и фиксировать конкретные расхождения |
| GNOME Shell devkit smoke | PARTIAL PASS | Ubuntu 26.04.1 / GNOME Shell 50.1; extension включён, три значения appearance выставлены на 1536×1024 и 1920×1080, после commit `5b0cdef` в логе нет `JS ERROR`. Артефакт: [run 45324219667](https://github.com/localzet/os/actions/runs/45324219667). Скриншоты ограничены Shell/overview и не заменяют полную сессию |
| QEMU Live BIOS/UEFI boot-marker smoke | PASS (автоматический CI) | Существующий `live-iso` workflow выполнился до добавления draft-gate; прошёл boot-marker smoke, но это не тест установки и не дизайн-приёмка |
| QEMU UEFI installation gate | NOT RUN | Запустить отдельный VM-only сценарий после визуальной приёмки |

Фактическая рабочая машина сообщает Ubuntu 26.04.1 и GNOME Shell 50.1, но
GNOME запретил screenshot API в настоящей Wayland-сессии. CI GTK-снимок показывает
нативное окно приложения; DevKit smoke подтвердил загрузку Shell extension и
отсутствие JS ошибок после исправления, но захватил ограниченный overview
контекст. Концепт-board PNG просмотрены, однако side-by-side с реальным desktop
пока не выполнен; pixel-perfect соответствие не заявляется.

## Воспроизводимые локальные проверки

```sh
make test
make desktop-deb
make extension-zip
```

Runtime сценарий и provenance записываются по
[`GNOME-50-SMOKE.md`](GNOME-50-SMOKE.md). Package/compile успех не заменяет
проверку работающего Shell и приложений.
